# Component Operations

Day-2 operations for managed components — install, start / stop / restart, scale, configure, delete. Every action is available in the admin UI and as a REST call.

## The model

Every component is a **cluster** of one or more **instances**. A cluster is the unit the operator works with (a Trino cluster, a Spark cluster, a ShannonStore cluster). Each instance is one process on one host. The same component can run several clusters in parallel — `trino-blue` and `trino-green` for a rolling upgrade, `shannonstore-prod` and `shannonstore-dev` on the same fleet.

## REST endpoints by action

For every component type (`trino`, `spark`, `flink`, `ontul`, `shannonstore`, `polaris`, `kiok`, `mium`, `neorunbase`, `itdastream`, `kafka`, `schema-registry`, `ui-proxy`, `trino-gateway`, `postgres`) the same shape applies (replace `<comp>` with the component type):

| Endpoint | Action |
|---|---|
| `GET    /admin/api/<comp>` | List all clusters of this component |
| `GET    /admin/api/<comp>/install-defaults` | Static install-form defaults — the component's packaged properties surface (every editable key + its default), the set of per-instance keys the form must mark read-only, and any per-role JVM defaults. Drives the Configure-style Create panel. |
| `POST   /admin/api/<comp>` | Provision a new cluster (install) |
| `GET    /admin/api/<comp>/<clusterId>` | Cluster details (settings + per-instance pid / status) |
| `POST   /admin/api/<comp>/<clusterId>/start` | Start every instance |
| `POST   /admin/api/<comp>/<clusterId>/stop` | Stop every instance |
| `POST   /admin/api/<comp>/<clusterId>/restart` | Stop then start, in the right order |
| `POST   /admin/api/<comp>/<clusterId>/scale` | Add instances (body: list of NM nodeIds) |
| `POST   /admin/api/<comp>/<clusterId>/unscale` | Remove instances (body: list of instanceIds) |
| `GET    /admin/api/<comp>/<clusterId>/config` | Current configuration (per-instance files + cluster settings) |
| `POST   /admin/api/<comp>/<clusterId>/config` | Update configuration (re-renders files on every instance, restarts the cluster) |
| `GET    /admin/api/<comp>/<clusterId>/metrics` | CPU / memory history for every instance |
| `GET    /admin/api/<comp>/<clusterId>/nginx` | Current component-nginx state (where applicable) |
| `POST   /admin/api/<comp>/<clusterId>/nginx` | Apply a component-nginx config |
| `DELETE /admin/api/<comp>/<clusterId>` | Stop + delete every instance + remove install dirs |

Mutating routes are **leader-only**. A follower replies `421 Misdirected Request` with the leader's address in the body; clients should follow that and retry against the leader.

PostgreSQL is the exception — it is provisioned per-instance, not per-cluster (`POST /admin/api/postgres` takes a single `instanceId` + `nodeId`).

## Install a cluster

The provisioner shape is component-specific but every payload includes at minimum:

- `clusterId` — optional; auto-generated `<comp>-<8hex>` when blank.
- The node lists per role (`coordinatorNodes`, `workerNodes`, `masterNodes`, `serverNodes`, …) — each entry is an NM nodeId. Repeat the same nodeId twice to land two instances on the same host.

Optional install-time tuning, shared by every component:

- **`properties`** — `Map<String,String>` of overrides applied to the component's main config file at install time. Keys not present here fall back to the packaged default (the same defaults the `install-defaults` endpoint surfaces). Per-instance keys (ports, discovery URI, node id) are owned by the provisioner and cannot be overridden here.
- **Per-role `JvmConfig`** — `{heapMin, heapMax, extra[]}` blocks keyed by role: `coordinatorJvm`/`workerJvm` for Trino, `masterJvm`/`workerJvm` for Ontul, `apiJvm`/`dataJvm` for ShannonStore, `serverJvm` for Polaris, `gatewayJvm` for Trino Gateway, etc. Each block is optional; missing fields keep the packaged JVM defaults. `extra[]` carries additional `-X…` / `-D…` flags appended verbatim to the JVM command line.

Optional integrations are auto-discovered. For Trino, Spark, and Flink, supplying just an `ontulAuthzToken` is enough — chango finds the first running Ontul cluster and wires its admin port as the authz endpoint. For Polaris and the Trino resource-group manager, supplying a `pgInstanceId` (chango-installed PostgreSQL) is enough — chango fills host / port / superuser from its own records.

The admin UI Create panel is the same shape as Configure: tabs for *Install*, the main `*.properties` file, and *JVM* per role, prefilled from `install-defaults`. Operators can ship a fully tuned cluster on first install without a follow-up Configure pass.

## Start / stop / restart

All three are idempotent. Calling `start` on an already-RUNNING cluster is a no-op (per-instance). Calling `restart` walks the cluster in `START_ORDER` reverse for the stop pass, then in `START_ORDER` forward for the start pass — Trino: workers stop first, coordinator stops last, coordinator starts first, workers start last.

## Configure

Most components have a Configure panel in the admin UI with multiple tabs:

- **Properties** — operator-tunable keys in the component's main config file (e.g. Trino's `config.properties`). Per-instance keys (`http-server.http.port`, `discovery.uri`) are filtered out — those are owned by the provisioner.
- **JVM** — per-role JVM tuning (`heapMin`, `heapMax`, extra `-X` flags).
- **Component-specific tabs** — Trino has *Exchange Manager*, *Resource Group DB*, *Ontul Authz*; Spark has *Ontul Authz*, *Job Log Storage*; NeoRunBase has *PG Connection*. Each tab updates a narrowly-scoped slice of the cluster's config without touching the others.

Apply triggers a config re-render on every instance and a full cluster restart. The exception is Configure → "Job Log Storage" on Spark, which re-renders `spark-defaults.conf` and restarts the cluster, and the exchange-manager tab on Trino, which rewrites `etc/exchange-manager.properties` on every instance.

## Scale

Add an instance by listing its target NM. The provisioner allocates fresh ports, installs the package, and starts the new instance, joining it to the existing cluster (worker → existing master URL, broker → existing kafka cluster, …). Removing an instance walks the inverse path.

Components that require an odd quorum (ZooKeeper, NeoRunBase ZK) refuse a scale request that would leave the cluster with an even count.

## Logs

Every component page has a Logs panel per instance — the master streams a tail over the internal NIO protocol from the NM hosting the instance. See [Logging](../features/logging.md) for the file locations and the REST endpoint.

## Nginx

Several components (ShannonStore, Ontul, NeoRunBase, Polaris, Itdastream Schema Registry, Kafka Schema Registry, Mium, kiok, UI Proxy) ship a per-cluster nginx reverse proxy you can opt into from the admin UI. See [Nginx Reverse Proxy](nginx-proxy.md).

Spark / Trino / Flink intentionally do **not** ship a per-cluster nginx — their UIs are exposed through the UI Proxy instead, with Ontul-based authentication.

## Deleting

Delete is destructive — the component's install dir and any chango-owned data dir is removed:

```bash
curl -X DELETE -H "Authorization: Bearer $TOK" \
  $BASE/admin/api/trino/trino-prod
```

Component data **outside** the install dir (Iceberg files on S3, NeoRunBase data dirs, Kafka log segments) is **not** removed — chango does not own data-plane state. Clean that up at the data-plane layer if you need a full reset.

The deleted clusterId is free to reuse immediately.
