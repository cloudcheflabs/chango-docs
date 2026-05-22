# Versions

The Chango 3.0.0 release ships the following component versions out of the box. These are the defaults that the admin UI populates when you provision a new cluster; you can override `packageFile` in the REST payload to install a different version that's been staged under the master's `components/` directory.

## Chango itself

| Artifact | Version |
|---|---|
| Chango master + node manager | **3.0.0** |
| Bundled ZooKeeper | 3.9.1 |
| Admin UI (React + Vite) | 3.0.0 |

## JDKs (installed by ansible)

| Runtime | Version |
|---|---|
| Java 17 | OpenLogic OpenJDK 17.0.7+7 — used by chango itself and most components |
| Java 25 | OpenLogic OpenJDK 25.0.3+9 — used by Trino |

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
