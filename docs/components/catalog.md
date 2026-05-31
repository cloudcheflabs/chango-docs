# Component Catalog

Chango installs, starts, scales, and observes every component below from the same admin UI and REST API. Each component is a first-party Cloud Chef Labs product or a curated open-source engine — chango ships the package, the provisioner, the lifecycle scripts, and the admin UI page for every one of them.

## Data Engine

### Ontul
Cloud Chef Labs' unified distributed engine — batch, streaming, and SQL under one runtime, plus a built-in IAM that other layers (Trino, Spark, Flink, UI Proxy) authenticate against.

- Topology: ZooKeeper + Master + Worker, multi-instance.
- Native IAM surface — users, groups, policies, access keys. Other chango components delegate authorization to Ontul.
- Arrow Flight SQL endpoint alongside the admin REST API.

## Workflow

### kiok
Distributed workflow orchestrator with YAML, Python, and Java job definitions.

- Topology: ZooKeeper + Master + Worker.
- Web UI for job graphs, history, and audit.

## Object Storage

### ShannonStore
S3-compatible erasure-coded object storage. Multi-disk, multi-host, KMS-encrypted at rest, with a built-in admin UI and S3 protocol surface.

- Topology: ZooKeeper + API Server (N) + Data Node (N), erasure-coding `k+m` configurable per cluster.
- Used by other chango layers as the default object store target (Iceberg, Spark event log, Trino exchange manager, ItdaStream tiered storage).

## Streaming

### ItdaStream
Kafka-compatible streaming broker with S3 tiered storage — hot data on local disk, cold data offloaded to an object store (typically ShannonStore).

- Topology: ZooKeeper + Broker + Schema Registry.
- Wire-compatible with existing Kafka clients.

### Kafka (bundled open source)
Vanilla Apache Kafka for teams that want the upstream broker rather than ItdaStream. Same provisioner shape (ZK + broker + Schema Registry).

### Schema Registry (bundled open source)
Confluent Schema Registry, used by both ItdaStream and Kafka clusters.

## Lakebase

### NeoRunBase
PostgreSQL-wire-compatible distributed database that combines OLTP + vector + full-text + graph in one SQL engine.

- Topology: ZooKeeper + Coordinator + DataNode.
- Coordinator stores its catalog in a PostgreSQL instance — chango can resolve this from a chango-installed PG (recommended) or from an external PG.
- Pgwire on the front, internal NIO between coordinator and data nodes.

### PostgreSQL (native dependency)
First-class PostgreSQL provisioner. Chango can install vanilla PostgreSQL as a managed component, stash the superuser password, and reuse the same instance for any component that needs a PG (Polaris metastore, Trino resource groups, NeoRunBase coordinator catalog).

## Agent

### Mium
Cloud Chef Labs' sovereign multi-agent platform. Mium is the Agent layer of the platform — it talks to every other layer natively (Iceberg tables via Trino/Spark, vector + graph via NeoRunBase, streaming via ItdaStream, S3 via ShannonStore, workflows via kiok) without external integration glue.

- Topology: Master + Worker, with a memory backend backed by NeoRunBase.

## Iceberg Catalog

### Polaris
Apache Polaris — the Iceberg REST catalog used by Spark, Trino, and Flink to discover and write Iceberg tables.

- Backed by a PostgreSQL metastore. Chango can resolve this from a chango-installed PG instance (recommended) or point at an external PG.
- Configurable per cluster: PG instance pick · catalog body schema · default S3 storage credentials.
- Single server role; scale by running multiple Polaris instances against the same metastore.

## Query / Compute (open source)

### Spark
Apache Spark, standalone mode. Chango ships a small first-party plugin (`chango-spark-authz`) that authorizes Spark SQL queries against Ontul IAM at table level.

- Topology: Master + Worker.
- Optional: ontul authz wiring, S3-backed event log (history server).

### Trino
Trino distributed SQL. Chango ships a `SystemAccessControl` plugin (`chango-trino-authz`) that enforces Ontul IAM policies on every query — table allow / deny, column masking, row filters.

- Topology: Coordinator + Worker.
- Optional: fault-tolerant exchange manager on ShannonStore S3, PostgreSQL-backed resource groups, ontul authz.

### Trino Gateway
The HTTP gateway in front of one or more Trino clusters — for blue / green upgrades and routing.

### Flink
Apache Flink standalone session cluster, with a first-party `chango-flink-authz` plugin that wires the same Ontul authz model into Flink SQL.

- Topology: JobManager + TaskManager.

## Edge

### UI Proxy
Ontul-authenticated reverse proxy in front of component web UIs (Spark Master, Trino, Trino Gateway, Flink JobManager, Polaris). Component UIs are not exposed directly — UI Proxy is the only entry point, and it delegates login to Ontul before forwarding requests.

- Topology: Proxy x N.
- Auto-discovers upstream Web UIs from running chango components.

## Patch eligibility

The first-party components are eligible for the [Patch System](../features/patch-system.md) — `chango-pack patch` builds an air-gapped jar / UI tarball; the admin UI's Settings → Patches page applies it across every host. Patches never touch `conf/` or component data.

| Component | Patch v1 | Notes |
|---|---|---|
| Ontul, kiok, ShannonStore, NeoRunBase, ItdaStream, Mium | yes | `jar`, `ui`, `both` types supported. |
| Chango itself | v2 (on `branch-3.0.0` only) | 3-phase fan-out via detached helper, sticky-leader reclaims after restart. |
| Trino, Spark, Flink, Kafka, Postgres, Polaris, Trino Gateway, Schema Registry, UI Proxy | no | Upgrade via blue / green — see [Upgrade](../operations/upgrade.md). |

## What chango does NOT do

- **Run your data queries** — that's Trino, Spark, Flink, Ontul.
- **Store your data** — that's ShannonStore (objects), Kafka / ItdaStream (streams), NeoRunBase / PostgreSQL (rows / vectors / graphs).
- **Author SQL or workflows** — that's the data engines and kiok.

Chango installs and observes all of them.
