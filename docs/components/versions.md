# Versions

The Chango 3.0.0 release ships the following component versions out of the box. These are the defaults that the admin UI populates when you provision a new cluster; you can override `packageFile` in the REST payload to install a different version that's been staged under the master's `components/` directory.

## Chango itself

| Artifact | Version |
|---|---|
| Chango master + node manager | **3.0.0** |
| Bundled ZooKeeper | 3.9.1 |
| Admin UI (React + Vite) | 3.0.0 |

## JDKs

Installed on every host by [`ansible install.yml`](../installation/automated.md), or by hand if you went the [manual install](../installation/manual.md) path. Both JDKs land under `/opt/` and are referenced via `JAVA_HOME` — not added to the system `PATH`.

| Runtime | Version |
|---|---|
| Java 11 | OpenLogic OpenJDK 11.0.27+6 — used by Spark and Livy |
| Java 17 | OpenLogic OpenJDK 17.0.7+7 — used by chango itself and most components |
| Java 25 | OpenLogic OpenJDK 25.0.3+9 — used by Trino |

Three, not two. Livy 0.8 was built against Java 8/11 and breaks on the Java 17
module system, and Spark 3.5 standalone is most stable on the same runtime — so
they keep their own JDK rather than being forced onto chango's.

## Cloud Chef Labs components

| Layer | Component | Version |
|---|---|---|
| Data Engine | Ontul | 1.0.0 |
| Workflow | kiok | 1.0.0 |
| Object Storage | ShannonStore | 1.0.0 |
| Streaming | ItdaStream | 1.0.0 |
| Lakebase | NeoRunBase | 1.0.0 |
| Agent | Mium | 1.0.0 |
| Edge | UI Proxy | 1.0.0 |
| Query Gateway | Trino Gateway | 3.0.0 |

## Open-source engines

| Component | Version | Notes |
|---|---|---|
| Trino | 479 | Java 25 |
| Spark | 3.5.8 | Scala 2.12, with Hadoop 3 |
| Flink | 1.19.3 | Scala 2.12 |
| Kafka | 3.7.2 | Scala 2.12 |
| Schema Registry | 7.7.1 | Confluent Community |
| PostgreSQL | 16 | Rocky 9 native packages |
| Polaris (Apache) | 1.4.1 | Iceberg Catalog |
| Livy (Apache) | 0.8.0-incubating | Spark REST job submission; Scala 2.12, Java 11 |

## Libraries bundled alongside the engines

Vanilla Spark and Flink ship without S3A and Iceberg support, and an air-gapped
host cannot reach Maven Central to add them. These travel in the bundle and are
dropped into each install's `jars/` (Spark) or `lib/` (Flink) directory.

| Library | Version | Used by |
|---|---|---|
| iceberg-spark-runtime-3.5_2.12 | 1.6.1 | Spark |
| iceberg-flink-runtime-1.19 | 1.6.1 | Flink |
| iceberg-aws-bundle | 1.6.1 | Spark, Flink |
| hadoop-aws | 3.3.4 | Spark — S3A filesystem |
| hadoop-client-api / hadoop-client-runtime | 3.3.4 | Spark |
| aws-java-sdk-bundle | 1.12.262 | Spark — S3A's AWS SDK |
| flink-sql-connector-kafka | 3.2.0-1.19 | Flink |

## First-party plugins shipped with engines

| Plugin | Version | Wired into |
|---|---|---|
| chango-trino-authz | 3.0.0 | Trino — Ontul-backed `SystemAccessControl` |
| chango-spark-authz | 3.0.0 | Spark — Ontul-backed `SparkSessionExtensions` |
| chango-flink-authz | 3.0.0 | Flink — Ontul-backed table-level authz |

## Operating system

Chango is tested on **Rocky Linux 9.x** (the install bundle ships ansible RPMs for Rocky 9). Other RHEL-compatible distributions (Alma, RHEL 9) work but are not the validated target. See [Node Preparation](../installation/node-preparation.md) for OS-level prep.

## Overriding the default version

To install a different version of a component (for example, Trino 478):

1. Drop the alternative package tarball into the master's `components/<componentType>/` directory.
2. POST the cluster install request with an explicit `packageFile` field:

```bash
curl -X POST -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{
  "clusterId": "trino-blue",
  "version": "478",
  "packageFile": "trino/trino-server-478.tar.gz",
  "coordinatorNodes": ["..."],
  "workerNodes": ["..."]
}' $BASE/admin/api/trino
```

Chango does not enforce compatibility across versions — older or newer engine versions may or may not work with the first-party authz plugins shipped at this release. The defaults above are the validated combination.

## The authoritative list

This page is written for reading. The machine-readable version is generated from
the bundle itself and carries a digest and a licence for every artifact:

```bash
column -t -s$'\t' chango-bundle-3.0.0/component-inventory.tsv
```

If the two ever disagree, the inventory is right — it is produced from the files
being shipped, while this page is maintained by hand. See
[Checksums & Bill of Materials](../installation/bill-of-materials.md).
