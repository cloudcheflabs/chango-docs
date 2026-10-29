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
| `GET    /admin/api/<comp>/<clusterId>` | Cluster details (settings + per-instance pid / status). The cluster `status` is **derived from its instances** — `RUNNING` when all are running, `STOPPED` when none is, `DEGRADED` in between (`PROVISIONING` passes through) — not the stored value, which only moves on install / start / stop and stayed `RUNNING` after a host reboot killed every process |
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
| `DELETE /admin/api/<comp>/<clusterId>` | Stop + delete every instance + remove install dirs. `?purgeData=true` also removes the data directories the component keeps outside its install dir |

Mutating routes are **leader-only**. A follower replies `421 Misdirected Request` with the leader's address in the body; clients should follow that and retry against the leader.

PostgreSQL is the exception — it is provisioned per-instance, not per-cluster (`POST /admin/api/postgres` takes a single `instanceId` + `nodeId`).

## Install a cluster

The provisioner shape is component-specific but every payload includes at minimum:

- `clusterId` — optional; auto-generated `<comp>-<8hex>` when blank.
- The node lists per role (`coordinatorNodes`, `workerNodes`, `masterNodes`, `serverNodes`, …) — each entry is an NM nodeId. Repeat the same nodeId twice to land two instances on the same host.

Optional install-time tuning, shared by every component:

- **`properties`** — `Map<String,String>` of overrides applied to the component's main config file at install time. Keys not present here fall back to the packaged default (the same defaults the `install-defaults` endpoint surfaces). Per-instance keys (ports, discovery URI, node id) are owned by the provisioner and cannot be overridden here.
- **Per-role `JvmConfig`** — `{heapMin, heapMax, extra[]}` blocks keyed by role: `coordinatorJvm`/`workerJvm` for Trino, `masterJvm`/`workerJvm` for Ontul, `apiJvm`/`dataJvm` for ShannonStore, `serverJvm` for Polaris, `gatewayJvm` for Trino Gateway, etc. Each block is optional; missing fields keep the packaged JVM defaults. `extra[]` carries additional `-X…` / `-D…` flags appended verbatim to the JVM command line.

Optional integrations are auto-discovered. For Trino, Spark, and Flink, **no token is needed**: when the install does not carry `ontulAuthzToken`, chango uses the service token (OTOK) it minted for the first RUNNING Ontul cluster — the same resolution the Trino Gateway already used — and wires that cluster's admin port as the authz endpoint. An explicit `ontulAuthzToken` still wins, for a deployment that issues a dedicated principal. If no token can be found at all the install is refused with `no IAM service token available for the authz endpoint … chango issues one itself a few tens of seconds after the IAM engine starts — check that the IAM engine is RUNNING and retry`; right after an Ontul start that is the normal window, not a missing setup step. (It used to say `ontulAuthzToken is required … Generate one via ontul: POST /admin/iam/keys`, i.e. mint a second principal for a secret chango already held — and once the cluster JSON stopped returning secrets, the documented way to read the token returned nothing.) For Polaris and the Trino resource-group manager, supplying a `pgInstanceId` (chango-installed PostgreSQL) is enough — chango fills host / port / superuser from its own records.

Some combinations are refused at install rather than accepted and left to fail at start:

- **Trino** with `exchangeManagerEnabled: true` and an empty `exchangeBaseDirectory` — Trino will not start with an empty `exchange.base-directories` while the S3 keys are present, every coordinator and worker reads that file, and the cluster used to install, report RUNNING, then turn STOPPED with no stated reason. The refusal gives an example (`"s3://query-exchange/trino"`) and notes the field is `exchangeBaseDirectory`, not `exchangeBaseDirs`.
- **Spark** with an event-log location whose prefix chango cannot create: `could not create the event log prefix <uri>: …`. Without the prefix the history server refuses to start and every job dies in the driver with `No such file or directory` — minutes after an install that answered 200. The message lists the causes to check — endpoint, credentials, and for an HTTPS endpoint with a private-CA certificate, whether **the control plane** trusts that CA (it creates the prefix itself; see [Trust Store](../features/trust-store.md)) — and the `mc cp /dev/null <alias>/<bucket>/<prefix>` command to create it by hand.

**Flink** ships `state.checkpoints.dir` and `state.savepoints.dir` **commented out** in `config.yaml`, with the `s3a://` form and the S3 credential keys next to them. They used to be written as empty strings with checkpointing on, and Flink parses an empty value as a path — `Can not create a Path from an empty string` — so every job that checkpoints failed at submission with `HTTP 400 Could not execute application`. With the keys absent Flink keeps checkpoints on the JobManager, which does not survive the node; set an `s3a://` location before production.

The admin UI Create panel is the same shape as Configure: tabs for *Install*, the main `*.properties` file, and *JVM* per role, prefilled from `install-defaults`. Operators can ship a fully tuned cluster on first install without a follow-up Configure pass.

## Start / stop / restart

All three are idempotent. Calling `start` on an already-RUNNING cluster is a no-op (per-instance). Calling `restart` walks the cluster in `START_ORDER` reverse for the stop pass, then in `START_ORDER` forward for the start pass — Trino: workers stop first, coordinator stops last, coordinator starts first, workers start last.

## Configure

Most components have a Configure panel in the admin UI with multiple tabs:

- **Properties** — operator-tunable keys in the component's main config file (e.g. Trino's `config.properties`). Per-instance keys (`http-server.http.port`, `discovery.uri`) are filtered out — those are owned by the provisioner. The table lists the keys of the product's shipped example file, which is only part of what the product reads (Kafka reads hundreds of keys, its example file names about 20), so under the table **Add a key that is not listed** takes any key and value — `default.replication.factor`, `taskmanager.numberOfTaskSlots`, `query.max-run-time`. A name already in the table edits that row instead. Key names are not validated: the key space belongs to the product and moves with its version, and a typo reaches the product and is answered in the product's own words. The same table is used in the Create drawer.
- **JVM** — per-role JVM tuning (`heapMin`, `heapMax`, extra `-X` flags).
- **Component-specific tabs** — Trino has *Exchange Manager*, *Resource Group DB*, *Ontul Authz*; Spark has *Ontul Authz*, *S3 Credentials*, *Job Log Storage*; Polaris has *S3 Credentials*; NeoRunBase has *PG Connection*. Each tab updates a narrowly-scoped slice of the cluster's config without touching the others.

Apply triggers a config re-render on every instance and a full cluster restart. Trino's exchange-manager tab instead rewrites `etc/exchange-manager.properties` on every instance.

When a key already exists in a file, the rewrite replaces that line in place, whatever its separator — `=`, `:`, a space or a tab — and keeps the original separator and indentation; a key that is absent is appended as `key=value`. Spark's `spark-defaults.conf` is space-separated, and an update used to look only for `=`, miss the line, and append a second one — `spark.chango.authz.ontul.token  OTOK-old` above `spark.chango.authz.ontul.token=OTOK-new`, one more on every token rotation. Files that already carry such duplicates get the new value on every copy.

### Ontul Authz — leave a field blank to keep it

The **Ontul Authz** tab (Trino, Spark, Flink; the Trino Gateway's equivalent is **IAM Service Token**) takes an endpoint and a token, and **Update Ontul Authz & Restart** needs only one of them: a blank field keeps the stored value, as the placeholders say. Spark and Flink prefill the stored endpoint like Trino. The server refuses only when a field is blank **and** nothing is stored to keep. It used to refuse a blank endpoint and overwrite the token with a blank one — which broke authorization silently — and the Spark and Flink buttons stayed disabled until both fields were filled.

After an Ontul cluster is re-created, chango issues a new service token and logs, by name, every cluster still holding the old one (`ontul cluster <id> has a NEW admin OTOK — these clusters still hold the previous one …`), including Trino Gateways. Update each from this tab. See [IAM](../features/iam.md#when-the-iam-engine-is-re-created).

### S3 credentials are their own tab

On **Spark** these are the cluster-wide default for every `s3a://` access the nodes make — rendered into `conf/core-site.xml` with `fs.s3a.aws.credentials.provider` pinned to `SimpleAWSCredentialsProvider`, so they cover the history server's event logs *and* a cluster-mode driver fetching its uberjar. A job that sets its own credentials still overrides them.

They used to be reachable only through *Job Log Storage*, which meant a cluster running no history server had no way to rotate its S3 key at all. *Job Log Storage* now carries only the event-log directory and depends on the credentials above.

On **Polaris** the tab sets the server-wide `-Daws.*` that every Polaris server runs with. That is the **fallback**, not the whole story: a catalog that carries its own credentials uses those instead, which is what lets catalogs on different object stores coexist on one Polaris cluster. Per-catalog credentials live on the Iceberg Catalogs screen.

Changing either restarts the cluster. Polaris reads its system properties into the AWS SDK's provider chain at startup only, so rewriting them without a restart would leave the cluster running the old key while the console showed the new one.

## Scale

Add an instance by listing its target NM. The provisioner allocates fresh ports, installs the package, and starts the new instance, joining it to the existing cluster (worker → existing master URL, broker → existing kafka cluster, …). Removing an instance walks the inverse path.

Components that require an odd quorum (ZooKeeper, NeoRunBase ZK) refuse a scale request that would leave the cluster with an even count.

A new instance is numbered **after the highest number in use**, not after the
count. With `worker-1` and `worker-2`, scaling in `worker-1` and then out again
used to hand out `worker-2` a second time and fail with `component instance
already exists: trino-1-worker-2` — permanently, until every worker was removed.
For ZooKeeper the number is also the ensemble `myid`, and for Kafka the
`broker.id`, where a duplicate fails silently rather than loudly. The stored
`<role>Count` settings are recounted from the instances after a scale rather
than predicted, so a scale that failed halfway does not record the count it
intended.

### What a new instance inherits

A scale-out does not just install the package. Between installing and
starting, the provisioner seeds the new instance with everything the cluster
has accumulated since it was created:

- the properties saved on the cluster from earlier Configure calls;
- for Trino, every catalog registered with `POST /<comp>/<clusterId>/catalogs`
  — the package only ships the three built-in ones (`tpch`, `tpcds`, `jmx`).

That ordering — install, seed, start — matters, and it collided with the rule
that a config change requires a running instance. The rule exists so an
operator's config call cannot report success while the process reads something
else; applied to provisioning it rejected every seed write, the service logged
the rejection and carried on, and the instance joined without them.

The resulting failure is worth recognising, because it does not look like a
missing file. A Trino worker without `etc/catalog/iceberg.properties` answers
`SHOW CATALOGS` and `SHOW TABLES` normally, since metadata resolves on the
coordinator, and `SELECT`, `UPDATE` and `DELETE` keep working. `MERGE` into a
*partitioned* table fails with Trino's `No catalog 'iceberg'` — a partitioned
write puts a fragment on every worker, so it is the first statement whose plan
reaches the one node missing the file. The error names a catalog that plainly
exists.

If you are on a build that predates the fix, the master log says so plainly:

```
Cluster trino-1 scale — could NOT replay catalog iceberg to trino-1-worker-3:
  instance 'trino-1-worker-3' is INSTALLED — settings that are written into
  the instance's own config files need it running …
```

and the two-minute way to confirm it on any cluster is to compare the
directory across instances:

```bash
for d in /opt/components/trino-1-*; do
  echo "$(basename $d): $(ls $d/etc/catalog 2>/dev/null | tr '\n' ' ')"
done
```

### New instances start on their own

A scale-out starts what it installed, in the component's role order, after the
instances are seeded. It used to leave them `INSTALLED`: the console showed the
new Spark worker or Flink TaskManager in the list and the cluster as
`DEGRADED`, and the master UI (`/json` for Spark, `/taskmanagers` for Flink)
never showed it. Check the master UI, not only the console, after a scale-out.

## Trino catalogs are verified against the coordinator

Adding or changing a catalog (`POST /admin/api/trino/<clusterId>/catalogs`, or
the Catalogs screen) restarts the cluster and then reads the coordinator's
`server.log` for that start. If Trino refused to start — an unknown property,
a missing connector setting — chango puts the previous catalog file back,
restarts again, and answers `400` with Trino's own sentence:

```
Trino refused to start with catalog 'bad': <Trino's error line> — the change was rolled back and the
cluster restarted with the previous catalogs. Fix the properties and <add|update> again.
```

Before this, the catalog was saved, the coordinator stayed down, and the screen
reported success.

## Polaris catalogs carry the engine grants

When chango creates a Polaris catalog, or saves its properties, it makes sure
the catalog's `catalog_admin` role holds `TABLE_WRITE_DATA` and
`TABLE_READ_DATA` in addition to the management privileges. Without them every
query engine could create and write tables, but `DROP TABLE` and the engines'
commit metrics report were refused with `403` — the coordinator logged
`Failed to report metrics` on every write. The grant is idempotent; saving an
existing catalog once repairs one created by an older build.

## ZooKeeper that ships with a component

Kafka, ShannonStore, ItdaStream, Mium, kiok, NeoRunBase and Ontul each run a
ZooKeeper that chango starts, and chango writes its `zoo.cfg` from the start
command. That file now carries
`4lw.commands.whitelist=srvr,conf,ruok,stat,mntr` — read-only four-letter words,
not `*`, which would also open `kill` and `stmk`. From ZooKeeper 3.5 the default
whitelist is `srvr` alone, so the products' topology probe — which sends `conf`
to read each server's id and `server.N` lines and warns about a duplicated
`myid` — got its connection dropped, treated the answer as "cannot tell", and
that warning could never fire on a chango-installed ZooKeeper. (chango's own
control-plane ZooKeeper is rendered by ansible with `*` and was not affected.)

The start command is stored at install and replayed on every start, so a fix to
it would otherwise reach only new installs and scale-outs. Starting a cluster now
rebuilds its ZooKeeper members' start command from the current code, reusing the
stored `myid` and ports, so the existing ensemble line is kept and only what the
current code adds is added. A rebuild that fails is logged and does not block
the start. The change applies when that ZooKeeper restarts.

## Logs

Every component page has a Logs panel per instance — the master streams a tail over the internal NIO protocol from the NM hosting the instance. See [Logging](../features/logging.md) for the file locations and the REST endpoint.

## Nginx

Several components (ShannonStore, Ontul, NeoRunBase, Polaris, Itdastream Schema Registry, Kafka Schema Registry, Mium, kiok, UI Proxy) ship a per-cluster nginx reverse proxy you can opt into from the admin UI. See [Nginx Reverse Proxy](nginx-proxy.md).

Spark / Trino / Flink intentionally do **not** ship a per-cluster nginx — their UIs are exposed through the UI Proxy instead, with Ontul-based authentication.

## Deleting

Delete is destructive — the component's install dir is removed:

```bash
curl -X DELETE -H "Authorization: Bearer $TOK" \
  $BASE/admin/api/trino/trino-prod
```

Directories the component declares **outside** its install dir — a product's RocksDB, its key store, embedded ZooKeeper snapshots, topic data — are removed only when asked: `DELETE …?purgeData=true`, or in the console the delete confirmation's **Also purge data directories outside the install path** toggle (off by default; 14 component pages). Leave it off and those directories stay: a reinstall on the same paths inherits state encrypted with a master key that no longer exists, and nothing reports an error. Before the toggle existed the console never sent `purgeData`, so an operator working only in the UI could not remove that data at all.

Data that is not on the component's hosts (Iceberg files on S3) is never removed — chango does not own data-plane state.

**Polaris re-created under the same id.** chango creates a PostgreSQL login role per catalog cluster (`polaris_<cluster>`) and records a fresh random password each time. If the role already exists — a deleted cluster re-created under the same id — chango now sets the role's password to the new value (`ALTER ROLE`) instead of keeping the old role and failing with `Could not pre-check Polaris PG state … password authentication failed for user "polaris_<cluster>"`. A metastore schema left in the database is still refused, with the `DROP SCHEMA` command in the message, because Polaris bootstraps a metastore only once.

The deleted clusterId is free to reuse immediately.
