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
Vanilla Apache Kafka for teams that want the upstream broker rather than ItdaStream. Provisioner shape: ZK + broker + Schema Registry + **Kafka Connect**.

Connect is a role of the Kafka cluster rather than a component of its own — one Connect cluster per Kafka cluster, with its plugins managed from the console and Debezium 2.6.2.Final bundled for air-gapped installs. Topics are listed, created and deleted from the same page. See [Kafka Connect & Topics](../features/kafka-connect.md).

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

- Installed from a Rocky 9 RPM bundle rather than a tarball, offline via `dnf`, then `initdb`'d per instance. One instance per node-manager host.
- **RPMs the host already has at an equal-or-newer version are dropped from the install set.** The bundle's dependency closure is resolved on whatever Rocky 9 minor the bundle was built on, so it carries base-OS packages (`libacl`, `libattr`, …) at that minor's versions. Install those on a newer host and `dnf` refuses the whole transaction with a file conflict — and chango's own ansible run is itself enough to cause it, because installing `rsync` pulls a newer `libacl`. Each bundled RPM is tested with `rpm -U --test` and skipped when the host is already at or above it, which is what makes one bundle work across Rocky 9.7 and 9.8 without a per-minor build.
- `--auth-local=peer`, so the `postgres` OS user is the local superuser; remote clients use scram-sha-256.
- The only managed component whose **data** chango backs up — see [PostgreSQL Backup & Restore](../features/postgres-backup.md). Polaris keeps its metastore here, and that metastore is the only record of where Iceberg table metadata lives.

## Agent

### Mium
Cloud Chef Labs' sovereign multi-agent platform. Mium is the Agent layer of the platform — it talks to every other layer natively (Iceberg tables via Trino/Spark, vector + graph via NeoRunBase, streaming via ItdaStream, S3 via ShannonStore, workflows via kiok) without external integration glue.

- Topology: Master + Worker, with a memory backend backed by NeoRunBase.

## Iceberg Catalog

### Polaris
Apache Polaris — the Iceberg REST catalog used by Spark, Trino, and Flink to discover and write Iceberg tables.

- Backed by a PostgreSQL metastore. Chango can resolve this from a chango-installed PG instance (recommended) or point at an external PG.
- Configurable per cluster: PG instance pick · catalog body schema · fallback S3 credentials (Configure → **S3 Credentials**).
- Single server role; scale by running multiple Polaris instances against the same metastore.

**Credential vending is deliberately off.** Every catalog is created with
`stsUnavailable: true`, so Polaris never calls `AssumeRole` to mint short-lived
credentials for an engine. It cannot: the object stores chango installs against —
ShannonStore, MinIO — have no STS endpoint, and a Polaris that tries to vend
against them fails the request rather than falling back. With vending off, Polaris
uses the static key directly and engines authenticate with their own configured
credentials.

**Each catalog carries its own S3 credentials**, written as `table-default.s3.*`
properties on the catalog. That is what lets one Polaris cluster serve catalogs on
different object stores — a ShannonStore catalog and a MinIO catalog side by side.
The cluster-level key in the *S3 Credentials* tab is only the fallback for a catalog
that does not set its own.

!!! note "Why only the `table-default.` prefix works"
    A bare `s3.access-key-id` on a catalog is accepted by Polaris and then ignored:
    it never reaches the FileIO that actually talks to the object store. Only
    properties under `table-default.` are handed down. Chango writes the prefixed
    form and translates bare keys on the way in, so a catalog edited through the
    console cannot end up with credentials that look set and do nothing.

## Query / Compute (open source)

### Spark
Apache Spark, standalone mode. Chango ships a small first-party plugin (`chango-spark-authz`) that authorizes Spark SQL queries against Ontul IAM at table level.

- Topology: Master + Worker.
- Optional: ontul authz wiring, cluster-wide S3 credentials (Configure → **S3 Credentials**), S3-backed event log (history server).

The S3 credentials are the cluster's default for every `s3a://` path its nodes
touch — not only the history server's event logs. They are configured, and
rotated, independently of whether an event log is enabled at all: a cluster with
no history server still needs a key to fetch a cluster-mode driver's uberjar.

### Livy (bundled open source)
Apache Livy, the REST front end for Spark job submission — used by the kiok tutorials to launch Spark work without an SSH hop to the Spark master.

- Installed alongside a Spark cluster rather than as its own component type.
- Runs on **Java 11**: Livy 0.8 was built against Java 8/11 and breaks on the Java 17 module system. That is why the bundle carries three JDKs.

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
| Trino, Spark, Flink, Kafka (broker / registry / Connect), Postgres, Polaris, Trino Gateway, UI Proxy | no | Upgrade via blue / green — see [Upgrade](../operations/upgrade.md). Connect *plugins* are a separate matter: they are replaced from the console at any time, see [Kafka Connect & Topics](../features/kafka-connect.md). |

## What chango does NOT do

- **Run your data queries** — that's Trino, Spark, Flink, Ontul.
- **Store your data** — that's ShannonStore (objects), Kafka / ItdaStream (streams), NeoRunBase / PostgreSQL (rows / vectors / graphs).
- **Author SQL or workflows** — that's the data engines and kiok.

Chango installs and observes all of them.
