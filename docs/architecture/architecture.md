# Architecture

Chango is the **control plane** of a self-hosted Agentic AI Data Platform. It does not store data and does not execute queries itself — it installs, starts, scales, observes, and tears down every other component (object storage, streaming, data engines, OLTP / vector / graph store, workflow, agents) on a fleet of Rocky 9 hosts, through a single admin UI and REST API.

The cluster is composed of three logical tiers — a control tier, an agent tier, and a coordination tier — each scalable independently.

## Chango Cluster

### Control Tier (Master)

Chango Masters are the brain of the cluster. They expose the admin UI / REST API, hold the authoritative cluster metadata, and drive every install / start / stop / scale operation.

- **Admin UI + REST API** — Netty HTTP server on `chango.master.admin.port` (default `8080`). The single-page React UI is served from the same port (`/admin/`); programmatic clients hit `/admin/api/*`.
- **Leader election** — masters elect a single leader via the bundled ZooKeeper (Curator `LeaderSelector`). Only the leader writes IAM / KMS / component metadata; followers serve reads. A previous leader prefers to reclaim its slot on restart (sticky leader) so component state does not move on rolling restarts.
- **Internal NIO server** — masters talk to node managers and to each other over a custom binary protocol (`InternalMessage` + `OpCode`) on `chango.master.internal.port` (default `19999`). The protocol is KMS-envelope-encrypted in flight.
- **Cluster-wide secrets at rest** — IAM, KMS, component inventory, and per-cluster settings live in local RocksDB stores. Cluster-wide secrets (component master keys, service tokens, S3 credentials) are envelope-encrypted with a cluster-wide master secret that the operator owns.

Masters are **multi-per-host** — you can run more than one master on the same host as long as the admin ports differ. A master may also co-locate with a node manager on the same host.

### Agent Tier (Node Manager)

Node Managers are the host agents. One per host. They receive install / start / stop / metrics requests from the leader and run the actual component processes.

- **Install** — the master pushes a component package (tarball) over the internal NIO protocol, the NM extracts it under the install path (default `/opt/components/<instanceId>`), writes the per-instance config files, and hands the install directory to the component's run-as user.
- **Lifecycle** — start / stop / restart go through component-supplied shell commands (`bin/start-X.sh` / `bin/stop-X.sh` patterns). The NM tracks each component's pid via the component's own pidfile, with a `sudo cat` fallback for components that keep their pidfile in a 0700 directory (Trino, ZooKeeper).
- **Metrics** — CPU% and resident memory of every managed process is sampled via `ps -p`. The leader pulls samples from every NM on a fixed interval and keeps a short in-memory history that backs the admin UI charts.
- **Component user model** — each component runs as its own system user (`trino`, `spark`, `postgres`, …) with passwordless sudo. The NM (running as `chango`) drops install directories to the component user via `chown`.

Node managers are **singleton-per-host** — exactly one NM per host. The NM may co-locate with one or more masters on the same host.

### Coordination Tier (ZooKeeper)

ZooKeeper is bundled inside chango and runs on every chango master host. It provides cluster membership and leader election.

- **Node registry** — masters and node managers register themselves under `/chango/nodes/{masters,node-managers}/<nodeId>` as ephemeral znodes. A node disappearing automatically de-registers from the registry, which the leader watches to drive nginx reconciliation.
- **Sticky leader election** — `/chango/master-leader` is a Curator `LeaderSelector` znode. The last leader's `nodeId` is recorded under `/chango/master-leader-id` so a restarted master can defer long enough for its predecessor to reclaim leadership.
- **No "outside" coordination** — the chango ZooKeeper is for chango itself only. Components that need their own ZooKeeper (Ontul, ItdaStream, NeoRunBase, …) bring their own bundled ZK; the chango ZK never carries component state.

## What Chango installs

Chango is **product-aware** — it ships a first-party provisioner for every Cloud Chef Labs layer plus the open-source engines used alongside them. The components it manages are:

| Layer | Component | What it provides |
|---|---|---|
| Data Engine | **Ontul** | Unified batch · streaming · SQL engine |
| Workflow | **kiok** | Distributed workflow orchestration |
| Object Storage | **ShannonStore** | S3-compatible erasure-coded object store |
| Streaming | **ItdaStream**, **Kafka**, **Schema Registry** | Streaming + schema management |
| Lakebase | **NeoRunBase**, **PostgreSQL** | OLTP · vector · full-text · graph |
| Agent | **Mium** | Sovereign multi-agent runtime |
| Query / Compute | **Spark**, **Trino**, **Trino Gateway**, **Flink** | Distributed query and compute |
| Edge | **UI Proxy** | Ontul-authenticated external access to component web UIs |

See [Component Catalog](../components/catalog.md) for per-component details.

## Architectural Properties

- **Component orchestrator, not a query engine** — chango is the install / start / stop / observe layer. Every actual data plane (storage, catalog, query, streaming, OLTP, agents) lives in a separately-packaged chango component.
- **Independent scaling** — masters scale for admin-UI / API throughput and HA; node managers scale with the host fleet; components scale per their own topology rules. Adding a host means adding one NM; that NM becomes a target for component instances.
- **Air-gapped friendly** — the install bundle (`chango-with-comps-<ver>.tar.gz`) ships every component package, every required JDK, and the ansible RPMs needed to install ansible itself on the master. No internet access is required after the bundle reaches the cluster.
- **One source of truth** — every cluster-wide secret and every component-inventory record lives in the leader's RocksDB stores. Followers and NMs pull from the leader on every restart and on every change at runtime — local state on a non-leader is always a cached copy.
- **External access is auth-gated** — component web UIs (Spark, Trino, Flink, …) are never exposed directly. The chango UI Proxy fronts them and delegates login to Ontul IAM; chango itself does not synthesize a public domain unless your hostnames are not real FQDNs.

## Where to next

- [Component Lifecycle](component-lifecycle.md) — how install / start / stop / scale actually move bytes and processes.
- [Internal Protocol](internal-protocol.md) — the binary protocol masters and NMs speak to each other.
- [Component Catalog](../components/catalog.md) — the components chango installs and manages.
- [Node Preparation](../installation/node-preparation.md) — host-level prep (SELinux, ulimit) before installing chango.
