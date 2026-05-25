# Phase 4 — Iceberg table maintenance (Ontul's Maintenance scheduler)

By the end of Phase 3 the lakehouse holds a handful of Iceberg tables written by Trino, by Spark in cluster mode, and by kiok-scheduled `spark-submit`. Every write produced a new **snapshot** and at least one new **data file**, plus one or more **manifest files** that point at them. Long-running tables accumulate this metadata until queries pay a noticeable planning tax and the underlying object storage grows with files no live snapshot references any more.

Iceberg ships three procedures to address that bloat:

| Procedure | What it does | What it does *not* do |
|---|---|---|
| `expire_snapshots` | drops snapshot metadata older than a retention window | does *not* delete the data files; just makes them eligible for removal |
| `rewrite_data_files` (a.k.a. `optimize`) | rewrites many small Parquet files into fewer files at a target size, then commits a new snapshot referencing the consolidated set | does *not* touch the now-unreferenced inputs |
| `rewrite_manifests` | re-shards the manifest tree for better partition pruning on planning | does not change row data |

Plus a fourth that complements the first three:

| `remove_orphan_files` | scans the table's storage prefix and deletes any file no live manifest references (and that is older than a safety threshold) |

**Ontul** ships a Maintenance scheduler that runs the first three on a configurable cadence (default every 6 hours, leader-only), keeps a per-table opt-out + tuning store, and records every job in a 30-day RocksDB history. The fourth (`remove_orphan_files`) is not on the auto-cycle — operators run it ad-hoc through Ontul SQL, on demand or via kiok.

This phase walks both surfaces end-to-end against the Iceberg catalog Phase 0 set up in Polaris.

## Topology

Foundation only — Phase 4 does **not** need Trino, Spark, Flink, or kiok. Ontul's maintenance executes inside the Ontul master JVM and reads/writes via the Polaris REST catalog + the same S3-compatible bucket on ShannonStore.

| Component | Why |
|---|---|
| Ontul (master + worker) | the scheduler + Iceberg connector + admin UI Maintenance page live here |
| Polaris | REST catalog Ontul reads schema/snapshot metadata from |
| ShannonStore (S3) | the actual data + manifest + manifest-list files Ontul rewrites |
| PostgreSQL | Polaris's metastore |

## Pre-stop the heavies (single-host lab)

Before continuing on a single-host test cluster, free the RAM Phase 2/3 left behind:

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/kiok/kiok-main/stop  || true
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/spark/spark-main/stop || true
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/trino/trino-main/stop || true
```

The Trino Gateway can stay up — it is small and useful once Phase 4 finishes. ShannonStore, Polaris, PostgreSQL, and Ontul must stay up.

## Variables carried over

```bash
BASE=http://<master-host>:8080
TOK=<chango admin token>

# From Phase 0 — Ontul admin endpoint + admin token (OTOK)
ONTUL_HOST=<chango-n1>
ONTUL_PORT=<ontul-master adminPort, e.g. 18180>
OTOK=<Ontul admin user OTOK>

# From Phase 0 — ShannonStore S3 credentials
SS_AK=<access key>
SS_SK=<secret key>
SS_ENDPOINT=http://chango-n2.chango.private:8080

# From Phase 1 — Polaris connection
POLARIS_REST=http://chango-n2.chango.private:8180/api/catalog
CLIENT_SECRET=<polaris-root client secret from /admin/api/polaris/polaris-main/credentials>
```

If you skipped Phase 0/1 and only want to exercise Phase 4, mint a fresh OTOK now — Ontul rotates the admin token on every login:

```bash
OTOK=$(curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"<ontul-admin-pw>\"}" | jq -r .accessToken)
```

## 1. Register the Polaris catalog in Ontul

Trino registered the Polaris-backed Iceberg catalog at `iceberg` in Phase 1, but Ontul has its **own** catalog registry — the Maintenance scheduler iterates `catalogService.getRegisteredCatalogNames()` and only sees what Ontul knows about. Register the same `lakehouse` warehouse inside Ontul with the matching short name `iceberg`:

### Via the Ontul admin UI

1. Open `http://$ONTUL_HOST:$ONTUL_PORT/admin/` and log in.
2. **Catalogs** in the sidebar → **Register catalog**.
3. **Catalog name** — `iceberg`.
4. **Type** — `Iceberg (REST)`.
5. Fill the REST + S3 panel:
    - **REST URI** — `http://chango-n2.chango.private:8180/api/catalog` (`$POLARIS_REST`)
    - **Warehouse** — `lakehouse`
    - **Flavor** — `polaris` (sets `scope=PRINCIPAL_ROLE:ALL` and disables Iceberg credential vending so Ontul reads S3 directly)
    - **Client ID** — `polaris-root`
    - **Client Secret** — paste `$CLIENT_SECRET`
    - **S3 endpoint** — `$SS_ENDPOINT`
    - **S3 access key / secret key** — `$SS_AK` / `$SS_SK`
    - **Path style** — on
    - **Region** — `us-east-1`
6. Click **Register**. The card lands with a table count — `iceberg` should show the tables Phase 1/2/3 left behind (`sales.orders`, `test.yaml_dag_smoke`, …).

### Via REST

```bash
cat > /tmp/iceberg-catalog.json <<EOF
{
  "catalogName": "iceberg",
  "config": {
    "catalog.type":              "rest",
    "catalog.warehouse":         "lakehouse",
    "catalog.name":              "lakehouse",
    "catalog.rest.uri":          "$POLARIS_REST",
    "catalog.rest.client_id":    "polaris-root",
    "catalog.rest.client_secret":"$CLIENT_SECRET",
    "catalog.rest.flavor":       "polaris",
    "s3.endpoint":               "$SS_ENDPOINT",
    "s3.accessKey":              "$SS_AK",
    "s3.secretKey":              "$SS_SK",
    "s3.pathStyle":              "true",
    "s3.region":                 "us-east-1"
  }
}
EOF

curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/catalogs \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  --data @/tmp/iceberg-catalog.json
# { "status":"ok", "catalogName":"iceberg", "tableCount": 5 }
```

> **Why the duplicate registration?** Trino's `etc/catalog/iceberg.properties` lives on the Trino coordinator/workers and is read by Trino only. Ontul's registry lives in Ontul's `MetadataStore` (RocksDB) and is read by Ontul's connector pool. Polaris is the single source of truth for the schemas + tables themselves — both engines pull from there.

## 2. Generate a dirty state for the demo

Phase 3 left three tables behind, each with only three rows and ~one snapshot — too clean to compact. Build a small demo table and dirty it on purpose. Ontul's SQL endpoint is `POST /admin/query/execute`:

```bash
SQL=$(cat <<'EOF'
CREATE TABLE IF NOT EXISTS iceberg.test.maint_demo (
  id      BIGINT,
  payload VARCHAR
);
EOF
)
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d "{\"sql\":$(jq -Rs <<<"$SQL")}"
```

Now generate 30 single-row inserts. Every insert produces its own snapshot + at least one small Parquet file:

```bash
for i in $(seq 1 30); do
  curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
    -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
    -d "{\"sql\":\"INSERT INTO iceberg.test.maint_demo VALUES ($i, 'row-$i')\"}" \
    | jq -r '.commandTag // .error'
done | sort | uniq -c
#   30 INSERT 0 1
```

Inspect the resulting clutter — Ontul exposes Iceberg metadata tables with the standard `$` suffix:

```bash
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT COUNT(*) FROM \"iceberg.test.maint_demo$snapshots\""}' \
  | jq -r '.rows[0][0]'
# 30

curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT COUNT(*), SUM(file_size_in_bytes) FROM \"iceberg.test.maint_demo$files\""}' \
  | jq -r '.rows[0] | "files=\(.[0]) total_bytes=\(.[1])"'
# files=30 total_bytes=...    # 30 tiny Parquet files
```

You now have a table that genuinely benefits from maintenance.

## 3. The Maintenance page — UI walkthrough

Open the Ontul admin UI's **Iceberg Maintenance** sidebar entry. The page has three panels.

### 3.1 Manual Trigger

A wildcard pattern + operation dropdown + a **Run Now** button.

| Pattern | Matches |
|---|---|
| `iceberg.*.*` | every Iceberg table in catalog `iceberg` |
| `iceberg.test.*` | every table in schema `test` |
| `iceberg.test.maint_demo` | exactly that table |
| `iceberg.*.maint*` | every table whose name starts with `maint`, across every schema |
| `iceberg.test.user?` | single-char wildcard — matches `user1`, `userA`, … |

Operation:

| Value | What it does |
|---|---|
| `All Operations` | runs `expire_snapshots` + `rewrite_data_files` + `rewrite_manifests` in sequence per matched table |
| `Expire Snapshots` | only the snapshot retention pass |
| `Rewrite Data Files` | only compaction (target = the table's configured `targetFileSizeMB`, default 128 MB) |
| `Rewrite Manifests` | only the manifest re-shard |

For the demo table:

1. **Pattern** — `iceberg.test.maint_demo`
2. **Operation** — `All Operations`
3. Click **Run Now**

The banner reads `Triggered on 1 table` with a chip listing the matched key. Jobs run on a cached thread pool in the background — the page does not block.

### 3.2 Table Configuration

The dropdown is populated from `tableKey`s that have appeared in **Job History**. Pick `iceberg.test.maint_demo` (it shows up after the Manual Trigger run above), and the panel reveals:

| Field | Default | Effect |
|---|---|---|
| **Enabled** toggle | `Enabled` | when off, the scheduled cycle skips this table; manual trigger still works |
| **Snapshot Retention (hours)** | `168` (7 days) | snapshots older than this are dropped by `expire_snapshots` |
| **Target File Size (MB)** | `128` | `rewrite_data_files` compacts everything smaller than this; rewrites no-op when files are already at target |

Click **Save Configuration**. Ontul persists the override under MetadataStore key `maintenance.<tableKey>`; the next scheduled cycle picks it up.

### 3.3 Job History

A 100-row, newest-first list of every operation Ontul ran — manual or scheduled — across every table. Columns: **Time**, **Table**, **Operation**, **Status** (`OK` / `Error`), **Duration**, **Details**. Click **Refresh** to re-pull. After the Manual Trigger from §3.1 you should see three rows for `iceberg.test.maint_demo`:

| operation | details |
|---|---|
| `expire_snapshots` | `retention=168h` |
| `rewrite_data_files` | (rewrite output line — e.g. file count + bytes rewritten) |
| `rewrite_manifests` | (no details — Iceberg API does not surface stats) |

Retention is 30 days by default — older rows are reaped by the daemon's 6-hour cleanup loop.

## 4. The Maintenance page — REST equivalents

The UI is a wrapper around four admin endpoints. Use these from kiok DAGs, oncall runbooks, or alert-driven automation.

### 4.1 Manual trigger

```bash
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/maintenance/run \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"tableKey":"iceberg.test.*","operation":"all"}'
# { "status":"ok", "matchedCount": 4,
#   "tables":["iceberg.test.maint_demo","iceberg.test.yaml_dag_smoke",
#             "iceberg.test.py_dag_smoke","iceberg.test.java_dag_smoke"] }
```

`operation` accepts `all`, `expire_snapshots`, `rewrite_data_files`, `rewrite_manifests`.

### 4.2 Read job history

```bash
# all jobs, newest first, up to 100
curl -sS "http://$ONTUL_HOST:$ONTUL_PORT/admin/maintenance/history" \
  -H "Authorization: Bearer $OTOK" | jq '.[0:5]'

# filter by table
curl -sS "http://$ONTUL_HOST:$ONTUL_PORT/admin/maintenance/history?tableKey=iceberg.test.maint_demo" \
  -H "Authorization: Bearer $OTOK" | jq .
```

Each entry shape:

```json
{
  "jobId":     "ec6e…",
  "tableKey":  "iceberg.test.maint_demo",
  "operation": "rewrite_data_files",
  "status":    "ok",
  "timestamp": 1716620400000,
  "elapsedMs": 4231,
  "details":   "compaction: rewrote 30 files -> 1 file",
  "error":     null
}
```

### 4.3 Per-table config — read & write

```bash
# READ
curl -sS http://$ONTUL_HOST:$ONTUL_PORT/admin/maintenance/config \
  -H "Authorization: Bearer $OTOK" \
  -H 'X-Table-Key: iceberg.test.maint_demo'
# { "enabled": true, "snapshotRetentionHours": 168,
#   "targetFileSizeMB": 128, "compactionIntervalHours": 6 }

# WRITE — tighten the demo table's retention to 24h, leave everything else at default
curl -sS -X PUT http://$ONTUL_HOST:$ONTUL_PORT/admin/maintenance/config \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"tableKey":"iceberg.test.maint_demo",
       "config":{"enabled":true,"snapshotRetentionHours":24,
                 "targetFileSizeMB":128,"compactionIntervalHours":6}}'
# { "status":"ok" }
```

## 5. The scheduled cycle

`IcebergMaintenanceService` starts on **leader-only** when Ontul master comes up. Its loop:

1. Sleep for the configured interval (default **6 hours**, first tick after 60 s).
2. For every registered catalog whose connector is `IcebergConnector`:
    - List schemas; list tables in each schema.
    - For each `<catalog>.<schema>.<table>`, read the per-table `MaintenanceConfig` from MetadataStore.
    - If `enabled=false`, skip.
    - Otherwise submit to the `maintenance-task` cached pool: run `expire_snapshots` → `rewrite_data_files` → `rewrite_manifests` in sequence.

Two consequences worth knowing:

- The cycle is **not** synchronized with writes. Heavy ingestion plus a 128 MB target threshold can mean a fresh batch of small files lands during compaction and gets caught on the *next* cycle, not this one.
- The scheduler **does not** run `remove_orphan_files`. Orphans accumulate until you explicitly run §6 below or wire it into a kiok DAG.

Tuning (set in `ontul.properties` or via chango's Ontul **Configure** card):

| Property | Default | Notes |
|---|---|---|
| `ontul.maintenance.interval.ms` | `21600000` (6h) | Time between cycle starts. Keep ≥ one ingest cycle. |
| `ontul.maintenance.history.retention.days` | `30` | RocksDB job-history TTL. |
| Per-table `snapshotRetentionHours` | `168` (7d) | Don't drop below your time-travel SLA. |
| Per-table `targetFileSizeMB` | `128` | Lower if your downstream readers prefer many small files; raise for fewer larger files. |

Verify the leader is the one running it (the JVM log line is the source of truth):

```bash
grep 'IcebergMaintenanceService started' /var/log/chango/components/ontul-main-master-*/logs/ontul-master.log
# Should appear exactly once, on the elected leader's host.
```

## 6. Orphan file cleanup (Ontul SQL)

Orphan removal is a separate procedure because it touches the storage layer directly — it lists every object under the table's prefix and deletes anything not referenced by any live manifest. Mistuned, it can race against in-flight writers and remove valid files. The default safety threshold is **3 days** — files newer than that are ignored even if unreferenced.

```bash
# Default retention (3 days)
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"sql":"REMOVE ORPHAN FILES iceberg.test.maint_demo"}'

# Or with explicit threshold
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d "{\"sql\":\"REMOVE ORPHAN FILES iceberg.test.maint_demo OLDER THAN '2026-05-20'\"}"
```

Response shape on success:

```json
{
  "queryId":   "9b3c…",
  "elapsedMs": 1820,
  "commandTag":"REMOVE ORPHAN FILES iceberg.test.maint_demo: scanned=42 deleted=29 bytesFreed=1834567"
}
```

If you ran `expire_snapshots` first (which dropped 29 snapshots and made their data files unreachable from any live manifest), the `deleted` count above is how many of those got physically removed from S3. The ones the scheduler can't reach are now actually gone.

> **Production rule of thumb** — chain the three in this order, on cadence, per table: `expire_snapshots` (cuts metadata) → wait at least one Ontul `maintenance.interval.ms` tick (so `rewrite_data_files` from a parallel cycle does not race) → `remove_orphan_files` with `older_than` ≥ the longest possible writer transaction.

## 7. Verify the dirty state shrank

Re-run the inspection queries from §2 against `maint_demo`. After a successful `All Operations` trigger you should see something close to:

```bash
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT COUNT(*) FROM \"iceberg.test.maint_demo$snapshots\""}' \
  | jq -r '.rows[0][0]'
# small number — typically 2-3 (the retention default keeps recent snapshots)

curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT COUNT(*) FROM \"iceberg.test.maint_demo$files\""}' \
  | jq -r '.rows[0][0]'
# 1 (the compaction collapsed all 30 micro-files into one ~128 MB-or-less file)
```

And the row count is unchanged:

```bash
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/query/execute \
  -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT COUNT(*) FROM iceberg.test.maint_demo"}' \
  | jq -r '.rows[0][0]'
# 30
```

## 8. (Optional) Schedule the full cycle from kiok

Phase 3's kiok cluster can carry this — register one DAG that hits Ontul's REST on a daily cron, looping over the table patterns you care about. Sketch (YAML):

```yaml
name: iceberg-maintenance-daily
schedule: "0 3 * * *"   # 03:00 every day
tasks:
  - id: full-maintenance
    type: shell
    command: |
      curl -sSf -X POST "$ONTUL/admin/maintenance/run" \
        -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
        -d '{"tableKey":"iceberg.*.*","operation":"all"}'
  - id: orphan-cleanup
    type: shell
    depends_on: [full-maintenance]
    command: |
      for t in iceberg.test.maint_demo iceberg.sales.orders; do
        curl -sSf -X POST "$ONTUL/admin/query/execute" \
          -H "Authorization: Bearer $OTOK" -H 'Content-Type: application/json' \
          -d "{\"sql\":\"REMOVE ORPHAN FILES $t\"}"
      done
```

Pull `ONTUL` + `OTOK` from a kiok **Connection** (the same `polaris-rest`-style pattern Phase 3 used) so the values are not baked into the bundle. The Ontul scheduler still runs its own 6-hour cycle — this DAG is an **explicit ceiling** on bloat for tables that are not happy at the 6h cadence, plus the place to put orphan cleanup, which the scheduler does not cover.

## Phase 4 exit checklist

- [ ] `GET http://$ONTUL_HOST:$ONTUL_PORT/admin/catalogs | jq` lists `iceberg` with a non-zero `tableCount`.
- [ ] `POST /admin/maintenance/run` with `iceberg.test.maint_demo` + `all` returns `matchedCount: 1` and `Job History` records three OK rows within ~60 seconds.
- [ ] `SELECT COUNT(*) FROM "iceberg.test.maint_demo$snapshots"` shrinks; `$files` collapses to ≤ ceil(total_bytes / targetFileSizeMB).
- [ ] `REMOVE ORPHAN FILES iceberg.test.maint_demo` returns a non-error `commandTag` with `deleted>0` on a freshly-expired table.
- [ ] Per-table `PUT /admin/maintenance/config` persists across an Ontul leader restart (re-`GET` to confirm).
- [ ] (If you wired §8) the kiok daily run shows up green every morning, and an audit of `Job History` shows one batch around 03:00 from kiok plus four from Ontul's 6h cycle.

## Troubleshooting

- **Maintenance page is empty after registering the catalog.** Job History only populates after at least one operation has run. Click **Run Now** with `iceberg.*.*` once, wait ~30 s, refresh.
- **`Triggered on 0 tables`** — your wildcard does not match anything. List what Ontul sees: `GET http://$ONTUL_HOST:$ONTUL_PORT/admin/catalogs` and the per-catalog `tables` endpoint, or run `SHOW TABLES FROM iceberg.test` through `/admin/query/execute`.
- **`rewrite_data_files` history row says `No compaction needed`.** Files are already at or above the target size. Lower `targetFileSizeMB` to force a rewrite, or accept that there is nothing to do.
- **`REMOVE ORPHAN FILES` deletes zero files but you expected some.** The 3-day default safety threshold is rejecting files newer than that. Use the explicit `OLDER THAN '<ts>'` form, but never set it tighter than the longest active write transaction or you risk pulling a file out from under a writer.
- **Scheduler log says `IcebergMaintenanceService started` on more than one host.** Two Ontul masters both think they are leader — investigate Curator / ZooKeeper before letting the next cycle run. Both leaders will conflict on `commit()`.
- **`ALTER TABLE … EXECUTE remove_orphan_files(…)` returned `Orphan file removal triggered (check maintenance history)` but nothing changed.** The `ALTER … EXECUTE` form is a placeholder; use the dedicated `REMOVE ORPHAN FILES <table>` statement from §6 instead.

## Next

[Phase 5 — Kafka → Flink → Iceberg streaming](#) brings Flink up and points it at the same Iceberg catalog. Pre-stop: nothing — Ontul, Polaris, ShannonStore, PostgreSQL stay up exactly as they are now; the maintenance scheduler stays useful for Phase 5's streaming output too.
