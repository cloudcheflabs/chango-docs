# Control Plane

The chango master is the control plane. It does not store user data and does not execute queries — its job is to know what components exist, where they live, how they should be configured, and how to install / start / stop / observe them. Everything in the admin UI is a thin client of the same REST API the master exposes.

## What the control plane knows

The master holds three authoritative pieces of state, all in local RocksDB on the master host:

| Store | Default path | What it contains |
|---|---|---|
| IAM | `<install_dir>/data/master/iam` | Users · groups · policies · access keys |
| KMS | `<install_dir>/data/master/kms` | KEKs that wrap component DEKs |
| Metadata | `<install_dir>/data/master/metadata` | Component inventory · per-cluster settings · nginx state · gateway topology |

ZooKeeper holds **ephemeral** topology — who is alive right now — under `/chango/nodes/{masters,node-managers}/<nodeId>`.

An ephemeral znode belongs to a ZooKeeper session, and a session can expire
while the process lives on — a long GC pause, a short network cut, memory
pressure; the default session timeout is 30 s. Curator reconnects, but the new
session has no ephemeral node, so the node used to stay **missing from the
registry for the rest of its life** while it kept running. Everything the leader
does to the rest of the cluster — component dispatch, patch fan-out, cluster
sync, `/etc/hosts` sync, the topology screen — walks that registry and skips an
absent node without an error. A node manager in that state answered component
calls with `400 no registered node manager with id: …` although all its
instances were RUNNING.

Each master and node manager now checks on every reconnect whether its own node
exists and re-creates it with the registration it remembers, logging
`Re-registered … — the previous ZooKeeper session expired …`. The ready flag is
restored as it was, so a node that was not ready before stays outside the
cluster until it is.

Alongside the ephemeral node, each node manager writes its address to a
**persistent** `node-addresses/<nodeId>` znode. When a node manager is briefly
absent — restarting during a patch, for instance — calls that only need its
address use the last known one instead of putting the node id where a host name
belongs (`http://nm-host3-19998:19320` was refused as `unsupported URI`, and a
catalog listing or a Flink job lookup failed with a message that did not point
at the restart). Installs and scale-outs still require the node to be
registered.

## Leader election

When more than one chango master is running, exactly one is elected leader. Only the leader:

- Writes to IAM / KMS / metadata RocksDB. Followers serve reads from their own cached copy and pull updates from the leader on every change.
- Drives component install / start / stop / restart. Followers refuse mutating REST routes with HTTP `421 Misdirected Request` and the leader's address in the body — clients can follow that to retry against the leader.
- Pulls per-component CPU / memory samples from every node manager on a fixed interval.
- Runs the periodic nginx reconciler that re-applies component nginx configs after instance changes.
- Sweeps the managed products' admin credentials: rotates the default password, stashes the result KMS-encrypted, and mints the service token where the product offers one.

!!! warning "The credential sweep is leader-only on purpose"
    Two masters sweeping the same product rotate its admin password
    **concurrently, each with its own random value**. The product applies both
    ("Password changed for user: admin" twice, milliseconds apart) and chango's
    metadata keeps whichever write landed last — which is not necessarily the
    one the product ended up with. The stashed password is then wrong and
    nobody can log into that product; recovery needs the product's own CLI
    (`bin/*-cli.sh iam:reset-password`) followed by
    `POST /<component>/<id>/credentials` to register the new value.

!!! note "A rotation whose answer was lost is still recovered"
    The new password is recorded as `adminPasswordPending` **before** it is sent.
    If the product applies the change but the answer never arrives — the product
    restarting at that moment, which is exactly what a Trust Store **Apply &
    Restart** right after install does — the next sweep logs in with the pending
    value, confirms it and keeps it (`admin password rotation confirmed from the
    pending value`). Earlier builds recorded the password only after a success
    answer; in that case nothing was kept and the product's admin password was
    known to no one.

    The credential fields (`adminPassword`, `adminOtok`, the pending value) are
    also protected from long-running operations that rewrite the whole cluster
    record from a copy read before the sweep ran: such a write keeps the newer
    credentials rather than the ones in its copy.

Election uses Curator's `LeaderSelector` against `/chango/master-leader`. The last leader's `nodeId` is recorded under `/chango/master-leader-id` (persistent znode) so a restarted master can defer briefly and let its predecessor reclaim leadership — this is the "sticky leader" pattern. It prevents flap during a rolling restart.

## Followers

Followers exist for HA — they hold a hot copy of every store and can take over leadership in sub-second. They serve read-only REST routes (auth, list, status, metrics) at full speed; they refuse mutating routes with `421`.

A single-master cluster is fine for many environments — a master restart costs ~10 s of admin-API unavailability, and component processes keep running. Add more masters when admin-UI uptime matters more than the cost of two more JVMs.

## Admin HTTP server

The admin UI and the REST API are served from the same Netty HTTP server on `chango.master.admin.port` (default `8080`):

- `GET  /admin/…` — static UI assets (React SPA built into `admin-ui/dist/`).
- `GET/POST /admin/api/…` — REST API surface.
- `GET  /admin/api/auth/{login,refresh}` — only routes that do not require a Bearer token.

Long-running admin operations — component install / start / stop, NIO log tail, patch upload and apply, backup, trust-store changes — run on a dedicated worker thread pool (`chango.master.admin.worker.threads`, default 8) so package I/O, fan-out to every node manager and object-storage calls do not stall other admin-API requests on the Netty event loop.

### Unknown request fields are reported, not rejected

A request body bound to a typed request whose fields include a name the endpoint
does not know is **accepted** — the field is dropped — and a successful JSON
object response carries the names it dropped:

```json
{
  "clusterId": "trino-1",
  "…": "…",
  "ignoredFields": ["exchangeBaseDirs"],
  "ignoredFieldsNote": "These request fields are not part of this endpoint and were discarded. A misspelled field is silently dropped, so a value you meant to set may be missing — check the names against the endpoint's request fields."
}
```

Before this, a misspelled field vanished and the call answered `200` with
nothing to say so — `exchangeBaseDirs` for `exchangeBaseDirectory` installed a
Trino whose coordinator and workers never started, `endpoints` for
`gatewayInstanceIds` removed a proxy instead of applying it, `registryNodes` for
`schemaRegistryNodes` never installed the registry. Rejecting with `400` would
be stricter, but the browser bundle and the server are patched separately, so a
newer console sending a field an older server does not know is a normal
combination. The field is added only to `2xx` object responses — not to arrays
(listings) and not to errors — so a client that does not look for it sees the
same body as before. Treat a non-empty `ignoredFields` as a failed request.

Two endpoints that take free-form key maps report the same thing their own way:
`POST /admin/api/postgres/backup-config` answers `ignored` + `hint` (see
[PostgreSQL Backup](postgres-backup.md#configuration)).

A login with `username` or `password` missing answers `400 username and password
are required` — it used to be a `500`.

## Cluster readiness gate

On startup the master refuses admin REST traffic until:

- It has either acquired leadership or pulled a fresh KMS + IAM + metadata snapshot from the current leader.
- The bundled ZooKeeper quorum is reachable.

Until then, every REST request returns `503` and the admin UI shows a "cluster starting" screen. This guards against the case where a master serves stale (or, on a wiped node, empty) IAM and silently accepts the wrong credentials.

## Bootstrap defaults

On the very first start of a fresh cluster, the leader creates exactly one user / group / policy:

- User `admin`, default password `admin` (forced-change on first login).
- Group `admin-group` with the `AdministratorAccess` policy attached.

If the leader's IAM RocksDB ever looks empty on a non-first boot, chango **refuses to recreate the defaults**. Your real IAM cannot be silently reset to `admin/admin` by a disk wipe or a botched restore. Restore from backup instead.

## Internal NIO protocol

Masters talk to node managers and to each other over a custom binary protocol on `chango.master.internal.port` (default `19999`). See [Internal Protocol](../architecture/internal-protocol.md) for the wire format and opcodes.

## Config

Every knob lives in `chango.properties` (also overridable via system properties and environment variables, in that order of precedence). See `conf/chango.properties` in the install bundle for the full list with defaults — the values you typically touch are the ports above, the data / log directories, and the metrics / sync intervals.
