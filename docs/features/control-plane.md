# Control Plane

The chango master is the control plane. It does not store user data and does not execute queries — its job is to know what components exist, where they live, how they should be configured, and how to install / start / stop / observe them. Everything in the admin UI is a thin client of the same REST API the master exposes.

## What the control plane knows

The master holds three authoritative pieces of state, all in local RocksDB on the master host:

| Store | Default path | What it contains |
|---|---|---|
| IAM | `/var/lib/chango/iam/` | Users · groups · policies · access keys |
| KMS | `/var/lib/chango/kms/` | KEKs that wrap component DEKs |
| Metadata | `/var/lib/chango/metadata/` | Component inventory · per-cluster settings · nginx state · gateway topology |

ZooKeeper holds **ephemeral** topology — who is alive right now — under `/chango/nodes/{masters,node-managers}/<nodeId>`. Persistent state never lives in ZooKeeper.

## Leader election

When more than one chango master is running, exactly one is elected leader. Only the leader:

- Writes to IAM / KMS / metadata RocksDB. Followers serve reads from their own cached copy and pull updates from the leader on every change.
- Drives component install / start / stop / restart. Followers refuse mutating REST routes with HTTP `421 Misdirected Request` and the leader's address in the body — clients can follow that to retry against the leader.
- Pulls per-component CPU / memory samples from every node manager on a fixed interval.
- Runs the periodic nginx reconciler that re-applies component nginx configs after instance changes.

Election uses Curator's `LeaderSelector` against `/chango/master-leader`. The last leader's `nodeId` is recorded under `/chango/master-leader-id` (persistent znode) so a restarted master can defer briefly and let its predecessor reclaim leadership — this is the "sticky leader" pattern. It prevents flap during a rolling restart.

## Followers

Followers exist for HA — they hold a hot copy of every store and can take over leadership in sub-second. They serve read-only REST routes (auth, list, status, metrics) at full speed; they refuse mutating routes with `421`.

A single-master cluster is fine for many environments — a master restart costs ~10 s of admin-API unavailability, and component processes keep running. Add more masters when admin-UI uptime matters more than the cost of two more JVMs.

## Admin HTTP server

The admin UI and the REST API are served from the same Netty HTTP server on `chango.master.admin.port` (default `8080`):

- `GET  /admin/…` — static UI assets (React SPA built into `admin-ui/dist/`).
- `GET/POST /admin/api/…` — REST API surface.
- `GET  /admin/api/auth/{login,refresh}` — only routes that do not require a Bearer token.

Long-running admin operations (component install, cluster start, NIO log tail) run on a dedicated worker thread pool (`chango.master.admin.worker.threads`, default 8) so package I/O does not stall other admin-API requests on the Netty event loop.

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
