# Patch System

Chango ships an air-gapped patch system for swapping a component's JAR files and / or its admin-UI bundle on a running cluster without going through the full install / configure cycle. Patches are jar / UI **only** — they never touch operator-edited configuration (`conf/*`), per-instance install metadata, RocksDB state, or component data. The control plane treats a patch as an immutable, signed-by-sha256 artifact that flows from `chango-pack patch` on the build host, through the operator's browser (upload), into the chango master's patch library, and out to every host that runs an instance of the target component.

## What problem it solves

A managed component (Ontul, kiok, ShannonStore, …) has a hotfix you want to deploy across the fleet:

- Without the patch system, the operator either re-runs the full ansible install (overwrites configuration, restages tarballs) or hand-edits `lib/*.jar` on every host (no audit, no rollback, easy to skew across hosts).
- With the patch system, the operator builds a tarball once with `chango-pack patch`, uploads it once to the admin UI, and clicks **Apply** — the leader fans out per-host swap + restart with automatic backup and one-click rollback.

## Component coverage

Patch v1 supports the first-party components:

| Component | Type |
|---|---|
| Ontul          | `jar`, `ui`, `both` |
| kiok           | `jar`, `ui`, `both` |
| ItdaStream     | `jar`, `ui`, `both` |
| ShannonStore   | `jar`, `ui`, `both` |
| NeoRunBase     | `jar`, `ui`, `both` |
| Mium           | `jar`, `ui`, `both` |

Patch v2 (only on `branch-3.0.0` of chango itself) additionally supports patching chango itself — the chango master JARs and the chango admin UI bundle. See the [Chango self-patch (v2)](#chango-self-patch-v2) section below.

A patch built for any other component (open-source engines — Trino, Spark, Flink, Kafka, Postgres, Polaris, Trino Gateway, UI Proxy, Schema Registry) is rejected at upload time. Upgrade those via [Blue / Green Upgrade](../operations/upgrade.md) — chango does not own their lifecycle the way it does the first-party stack.

## Building a patch — `chango-pack patch`

`chango-pack` is the air-gapped tooling shipped inside the chango release tarball. The `patch` sub-command builds the upload-ready tarball from a directory of jars and / or a directory of admin-UI dist files:

```bash
# Java-only patch
/opt/chango/bin/chango-pack patch \
    --component ontul \
    --version   3.0.0-SNAPSHOT \
    --type      jar \
    --jars      /path/to/ontul/lib \
    --out       dist/ontul-patch-3.0.0-SNAPSHOT.tgz

# admin-UI-only hot patch (no restart needed)
/opt/chango/bin/chango-pack patch \
    --component kiok \
    --version   3.0.0 \
    --type      ui \
    --admin-ui  /path/to/kiok/admin-ui/dist \
    --notes     "fix DAG status colors" \
    --out       dist/kiok-patch-3.0.0-ui.tgz

# combined jar + UI
/opt/chango/bin/chango-pack patch \
    --component shannonstore \
    --version   3.0.0 \
    --type      both \
    --jars      /path/to/shannonstore/lib \
    --admin-ui  /path/to/shannonstore/admin-ui/dist \
    --out       dist/shannonstore-patch-3.0.0.tgz
```

The output is a `tgz` whose layout is **strictly**:

```
manifest.json              ← {component, version, type, files[].sha256, builtAt, builtBy, ...}
lib/*.jar                  ← required when --type is jar or both
admin-ui/dist/**           ← required when --type is ui  or both
```

Any other top-level entry, or any path outside this whitelist, is rejected at upload time. No `conf/`, no scripts, no full install tree.

The tooling only needs `tar`, `sha256sum`, `find`, and a POSIX shell — it ships inside `/opt/chango/bin/` so the same chango release can rebuild patches in-place on the build host.

## REST surface

| Endpoint | Purpose |
|---|---|
| `POST /admin/api/patch/upload` | Raw tarball (`Content-Type: application/gzip`) → leader validates whitelist + sha256, stores under `data/master/patches/`. |
| `GET  /admin/api/patch/library` | Lists every uploaded patch. Optional `?component=ontul` filter. |
| `GET  /admin/api/patch/<patchId>/raw` | Authenticated download of the original tarball (used by node managers when the master orchestrates an apply). |
| `POST /admin/api/patch/<patchId>/apply` | Body `{clusterId, restartMode: "rolling"|"parallel"}` — fans out per-host swap + restart. |
| `POST /admin/api/patch/rollback` | Body `{component, clusterId, to: "lastBackup"|patchId}` — restores `lib/` and `admin-ui/` from `.bak/`. |
| `GET  /admin/api/patch/history?component=&clusterId=` | Per-cluster applied-patch history (read-only fan-out to each NM's `.bak/*` dirs). |

All mutating routes are admin-only (Stage-1 RBAC) and leader-only. Followers transparently forward to the leader.

### Upload

```bash
TOK=$(curl -s $BASE/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<pw>"}' | jq -r .accessToken)

curl -X POST -H "Authorization: Bearer $TOK" \
     -H 'Content-Type: application/gzip' \
     --data-binary @dist/ontul-patch-3.0.0-SNAPSHOT.tgz \
     $BASE/admin/api/patch/upload
```

Response:

```json
{
  "patchId":   "ontul-3.0.0-SNAPSHOT-20260530-1f3a",
  "component": "ontul",
  "version":   "3.0.0-SNAPSHOT",
  "type":      "jar",
  "size":      18234567,
  "sha256":    "…",
  "uploadedAt":"2026-05-30T12:34:56Z"
}
```

### Apply

```bash
curl -X POST -H "Authorization: Bearer $TOK" \
     -H 'Content-Type: application/json' \
     -d '{"clusterId":"ontul-main","restartMode":"rolling"}' \
     $BASE/admin/api/patch/ontul-3.0.0-SNAPSHOT-20260530-1f3a/apply
```

The leader resolves `(component, clusterId)` to the set of NMs that host an instance, then sends each NM a `PATCH_APPLY` (`OpCode 235`) carrying the manifest + a master-side `/raw` download URL + the explicit `instanceIds` to swap on that host (the NM has no `clusterId`/role context of its own). The NM:

1. **Downloads** the tarball from the master via the authenticated `/raw` route.
2. **Backs up** the current `lib/` (and `admin-ui/dist/` if `type == ui|both`) of every targeted instance into `<install-dir>/.bak/<patchId>/` — unconditional, every apply.
3. **Overlays** the patch contents on top of the live install dir — `lib/*.jar` replaces matching jars, `admin-ui/dist/**` overlays the bundle. No file outside the whitelist is touched.
4. **Restarts** the instance with the component's existing `bin/stop-*.sh` + `bin/start-*.sh` (only when `type == jar|both` — a UI-only patch needs no restart). `JAVA_HOME` and the original `-Dchango.*` system properties are preserved from the live pid's `/proc/<pid>/cmdline`.

`restartMode: "rolling"` does this one host at a time and waits for the instance to report RUNNING again before moving on; `parallel` fires every host together — faster, but expects all instances to tolerate a simultaneous restart.

The response aggregates per-host results:

```json
{
  "patchId":   "ontul-3.0.0-SNAPSHOT-20260530-1f3a",
  "clusterId": "ontul-main",
  "status":    "applied",
  "hosts": [
    {"nodeId":"nm-host1-…", "instanceIds":["ontul-main-master"],  "status":"applied"},
    {"nodeId":"nm-host2-…", "instanceIds":["ontul-main-worker-1"],"status":"applied"},
    {"nodeId":"nm-host3-…", "instanceIds":["ontul-main-worker-2"],"status":"applied"}
  ]
}
```

### Rollback

```bash
curl -X POST -H "Authorization: Bearer $TOK" \
     -H 'Content-Type: application/json' \
     -d '{"component":"ontul","clusterId":"ontul-main","to":"lastBackup"}' \
     $BASE/admin/api/patch/rollback
```

Rollback is the inverse of apply: each NM restores `lib/` and `admin-ui/dist/` from the requested `.bak/<patchId>/` directory and restarts the instance. `to: "lastBackup"` rolls back to the most recent apply; `to: "<patchId>"` rolls back to a specific past patch. Rollback also writes a fresh `.bak/<rollbackId>/` so a re-roll-forward stays possible.

Because `.bak/` lives **inside the instance install dir**, rollback only sees patches that were applied to that host — not the master's global library. If you wiped `/opt/components/<instanceId>/.bak/` by hand, the corresponding rollback target is gone.

### History

```bash
curl -s -H "Authorization: Bearer $TOK" \
     "$BASE/admin/api/patch/history?component=ontul&clusterId=ontul-main" | jq .
```

Returns the list of patches whose `.bak/` is still present on the cluster — applied in newest-first order, one row per `(patchId, host)`. The admin UI uses this to drive the PatchHistoryCard on each component page.

## On-disk layout

```
<install_dir>/data/master/patches/
    <patchId>.tgz                ← the raw uploaded tarball
    <patchId>.json               ← parsed manifest + sha256

/opt/components/<instanceId>/
    lib/                         ← live jars  (overlaid by patch apply)
    admin-ui/dist/               ← live UI    (overlaid by patch apply)
    .bak/
        <patchId>/
            lib.tgz              ← pre-apply backup
            admin-ui.tgz         ← pre-apply backup (when applicable)
            manifest.json        ← copy of the applied manifest
```

The leader keeps the master library; each NM keeps the per-instance backups. Two different chango clusters never share a `.bak/`.

## Non-leader catch-up (PR 5)

Followers and node managers must not call out to the leader's HTTP API on every PATCH_APPLY — that would couple every NM's apply path to the leader's admin port. Instead, the patch library is treated like any other chango cluster state: replicated lazily over the internal NIO protocol.

- **OpCode `PATCH_INDEX_REQ` / `PATCH_INDEX_RES`** — leader returns a JSON array of every patchId + sha256 currently in its library.
- **OpCode `PATCH_FETCH_REQ` / `PATCH_FETCH_RES`** — body is the patchId as UTF-8; leader streams the tarball back.

A non-leader master runs `PeriodicLeaderPull` every 30 s: pull the index, compare with the local `patches/` dir, fetch any missing tarballs. The same pull runs immediately when this master **loses** leadership so a brand-new follower never serves a stale library.

This is also what makes the patch system survive a backup / restore: when a fresh chango cluster restores from a backup tarball, the leader's `data/master/patches/` directory is included (see below), and every newly-elected follower pulls from it on startup.

## Backup inclusion

`BackupService.packTarball` includes `data/master/patches/` in the cluster-state backup whenever the directory exists. The manifest reflects this:

```json
{
  "backupId":       "20260530-…",
  "patchesDir":     "/opt/chango/data/master/patches",
  "patchesIncluded": true,
  ...
}
```

Restoring the backup re-populates the patch library on the new master; followers then catch up via PATCH_INDEX / PATCH_FETCH.

## Admin UI

### Settings → Patches

Sidebar → **Settings → Patches** opens the cluster-wide patch console:

- **Upload** — drag-and-drop dropzone. POSTs the raw `.tgz` body to `/admin/api/patch/upload` with the operator's bearer token. On success the new patch shows up at the top of the Library.
- **Library** — every uploaded patch, newest first, grouped by component. Each row shows `version`, `type`, `size`, `sha256` (truncated, click to copy), `uploadedAt`, `notes`, and an **Apply** button that opens the Apply modal.
- **Apply modal** — pick a cluster (autopopulated from the existing instances of the patch's component), pick `rolling` or `parallel`, confirm. The modal streams the leader's response and surfaces per-host status as it lands. Above the restart choice it shows the selected cluster's **installed version** and **patch level**, with every recorded patch id, and warns when this patch would be a downgrade or crosses a major version.

### Patch History card on each component page

Every component's detail page (Ontul, kiok, ShannonStore, NeoRunBase, ItdaStream, Mium) shows a `PatchHistoryCard` in the right-hand panel listing the patches applied to the current cluster — one row per patch with **Rollback** buttons (`lastBackup` or "rollback to this specific patch").

### Non-admin readonly

Non-admin users (members of any group that does **not** hold the `AdministratorAccess` policy) see the Patches page in read-only mode — the Library is visible, but **Upload**, **Apply**, **Rollback** buttons are hidden, and the dropzone is disabled. The backend enforces the same gate.

## Patch level, and what a scale-out does with it

A patch does not change the cluster's **version**. That field names the component
package the cluster was installed from — `ontul/ontul-1.0.0.tar.gz` — and a patch
replaces jars inside an install without touching the package on the master. The
two facts are reported separately:

```
GET /admin/api/patch/level?clusterId=<id>
→ { "clusterId": "...", "patchLevel": "1.0.1",
    "appliedPatches": [ { "patchId": "ontul-1.0.1-ab12cd34ef56", "version": "1.0.1", "type": "jar" } ] }
```

The Apply drawer shows both, because the difference is the thing an operator has
to understand before clicking: *installed version* is what a scale-out or a
reinstall installs from, *patch level* is what is running now.

### A scale-out replays the cluster's patches

Applying a patch records its id on the cluster. When a scale-out adds instances,
the patches recorded for that cluster are replayed onto the new instances before
the call returns — in the order they were applied, since a later patch may
overwrite a file an earlier one also carried.

Without that, a scale-out installed the new instance from the cluster's stored
`packageFile` and nothing else: it came up running pre-patch code while every one
of its peers ran the patch. Nothing reported an error, the Patches page showed the
patch as applied, and the divergence surfaced only once work happened to land on
the new instance.

!!! note "The replay does not start anything"
    A jar patch normally restarts the instance it lands on, because the JVM has
    the old jars open. A scale-out instance has not been started yet, so a
    restart there would be a *start* — and chango keeps install and start
    separate everywhere else. The node manager therefore restarts only instances
    that are actually up and simply swaps the jars of the rest; a stopped
    instance picks them up whenever it is started. The ack reports both what the
    manifest demanded (`restarted`) and what happened (`restartedInstances`).

**Rollback un-records it.** Otherwise the next scale-out would replay the patch
the operator just removed, and the new instance would be the only one carrying it
— the original bug, reversed.

**A reinstall does not replay.** The record lives in the cluster's own settings,
so deleting the cluster drops it. That is deliberate: a reinstall is a fresh
install from the component package, and silently re-applying patches to what the
operator asked to be new would be a different product than the one they asked
for. Re-apply from the Library afterwards — the tarball never GCs, so it is still
there.

!!! warning "A patch deleted from the library cannot be replayed"
    If a recorded patch is no longer in the library, the scale-out logs it and
    the new instances stay at the package level. `appliedPatches` marks that
    entry `"missing": true` rather than hiding it: the cluster claims a level it
    can no longer reproduce, and only the operator can resolve that.

### Versions are reported, not enforced

Nothing refuses a patch whose version does not match the cluster's. Applying an
ontul 1.0.1 patch to a 1.0.0 cluster is the ordinary case; applying 0.9.5 to it
is a downgrade, and applying a 2.x patch to a 1.x cluster will not migrate state
or config for you. The Apply drawer says so for the last two and then lets you
proceed — an operator rolling back to a known-good build at 3am is doing
something legitimate, and a hard refusal there is worse than a warning.

## Invariants

The patch system is deliberately narrower than "in-place upgrade":

- **Configuration is never touched.** The whitelist excludes `conf/`. Operator-edited properties files survive every apply / rollback.
- **State is never touched.** `data/`, `logs/`, RocksDB stores under the component's install dir are untouched. Iceberg files, Kafka logs, NeoRunBase tables are unaffected.
- **Backups are unconditional.** Every apply writes a fresh `.bak/<patchId>/` before overlaying anything. The operator does not have to opt in.
- **Patches are immutable.** `patchId` is a content-derived id; the same tarball uploaded twice deduplicates.
- **A scale-out stays level with the cluster.** Patches recorded on a cluster are replayed onto instances a scale-out adds. A reinstall is not — see [Patch level](#patch-level-and-what-a-scale-out-does-with-it).
- **The version field keeps meaning "which package".** A patch never rewrites it, because a scale-out and a reinstall both resolve their package from it.
- **First-party only (v1).** Open-source engines (Trino, Spark, Flink, …) are not patchable through this system; chango itself is patchable only via [v2](#chango-self-patch-v2) on `branch-3.0.0`.

## Chango self-patch (v2)

The patch system is also able to patch **chango itself** — the chango master JARs and the chango admin UI — but only on `branch-3.0.0` of chango (the v2 codepath ships there, not yet on `master`). Conceptually the contract is identical:

```bash
/opt/chango/bin/chango-pack patch \
    --component chango \
    --version   3.0.0 \
    --type      both \
    --jars      /path/to/chango/lib \
    --admin-ui  /path/to/chango/admin-ui/dist \
    --out       dist/chango-patch-3.0.0.tgz
```

What differs is the execution model — chango is patching itself, so it can not be the process that overlays its own running JARs. Apply runs a **3-phase fan-out** through a detached helper:

1. Node managers first.
2. Follower masters next.
3. Leader self last.

On every target host the master forks a `setsid`-detached helper that does `sleep 3 && download && backup .bak/<patchId>/{lib,admin-ui}.tgz && overlay && stop-master.sh / stop-node-manager.sh && start-…sh`. The helper preserves `CHANGO_MASTER_KEY`, `JAVA_HOME`, and the original `-Dchango.*` system properties from the running process's `/proc/<pid>/cmdline`.

Because the leader writes a `master-leader-preferred:<expiresAt>` hint to ZooKeeper just before its graceful stop, the **sticky-leader** mechanism (see [Sticky Leader Election](sticky-leader.md)) reclaims leadership for the same nodeId once the helper finishes the restart — no leadership toggle, no double KMS / IAM init.

Self-patch rollback follows the same 3-phase fan-out but the helper restores `lib/` and `admin-ui/dist/` from the requested `.bak/<patchId>/` before restarting. The rollback branch ships in `branch-3.0.0` only — on `master` the rollback codepath is still v1-only (apply lands without rollback on the chango self side).
