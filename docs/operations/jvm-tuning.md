# JVM & Heap Tuning

Nearly every component chango manages is a JVM process, and on a chango cluster **several of them usually share a host**. That is the single fact that drives chango's JVM defaults: a component must never size itself as if it owned the machine. This page covers where JVM settings live, what chango's defaults are, how an operator override is merged, and how to verify the result on the host.

## Where JVM settings come from

| Layer | What it is |
|---|---|
| **Packaged default** | Whatever the upstream distribution ships. Chango overwrites this for components where the upstream default is unsafe in a co-located layout. |
| **Chango default** | The `jvm.conf` / `jvm.config` chango renders at install time. Marked `# Managed by chango — edit via the admin UI (Configure Cluster).` |
| **Operator override** | A per-role `JvmConfig` block — `{heapMin, heapMax, extra}` — supplied on the **Create** panel's *JVM* tab at install, or on **Configure** afterwards. |

The override is **per role**, not per cluster: `coordinatorJvm` / `workerJvm` for Trino, `masterJvm` / `workerJvm` for Ontul, `apiJvm` / `dataJvm` for ShannonStore, `serverJvm` for Polaris, `gatewayJvm` for Trino Gateway, and so on. A coordinator and a worker on the same host can therefore be sized completely differently — which is normally what you want, since only the workers do the heavy lifting.

Because it is available on the **Create** panel, a fully tuned cluster can be installed in one pass; there is no need to install first and Configure second. See [Component Operations](component-operations.md) for the install-request shape.

## Rendering rules

`JvmConfig` renders one JVM option per line:

- `heapMin` → `-Xms<value>`; `heapMax` → `-Xmx<value>`. Blank means "omit the line", not "zero".
- Each `extra` entry becomes one line. A **blank value** yields a bare switch (`-XX:+UseG1GC`); a **non-blank value** yields `key=value` (`-XX:MaxMetaspaceSize=256m`).
- The rendered file always starts with the `# Managed by chango` comment, so an operator reading the host can tell at a glance which file chango owns.

Values are passed through verbatim after trimming — chango does not validate that `-Xmx3g` is achievable on the node. A heap larger than physical RAM produces a JVM that fails to start, and the component lands in `FAILED` with the JVM's own error in the component log.

## Several launchers never read `jvm.conf`

This is the part that costs time. For a number of components the rendered file is
**a record for the operator, not the mechanism** — the launcher reads an
environment variable and nothing else. Writing only the file produces a setting
that is stored, replayed on scale-out and shown in the UI while the process runs
on the launcher's default.

| Component / role | What actually applies |
|---|---|
| Trino (all roles) | `etc/jvm.config` — the file *is* the mechanism |
| Spark master / worker / history server | `SPARK_DAEMON_MEMORY` + `SPARK_DAEMON_JAVA_OPTS` in `conf/spark-env.sh` |
| Livy | `LIVY_SERVER_JAVA_OPTS` |
| Kafka broker | `KAFKA_HEAP_OPTS` in a `kafka-env.sh` the start command sources |
| Schema Registry (standalone **and** the one co-located with Kafka) | `SCHEMA_REGISTRY_HEAP_OPTS` |
| UI Proxy | `CHANGO_UI_PROXY_OPTS` |
| Polaris | `POLARIS_JAVA_OPTS` — the same variable carries the `-D` server settings, so every rewrite (Configure, S3 credentials, scale-out) writes the heap with them |
| Flink | `<role>.memory.process.size` in `config.yaml` — Flink *derives* `-Xmx` from it |
| First-party products (Ontul, kiok, …) | `conf/jvm.conf` |

Two consequences worth knowing:

- **Flink's `-Xmx` will not equal what you set.** You set a process size; Flink
  subtracts metaspace, network and managed memory and derives the heap. Setting
  `1536m` on a TaskManager produced `-Xmx436207608` (≈416 MB). That is correct,
  not a bug.
- **Polaris: check the running JVM, not the screen.** One variable carries both
  the server settings and the heap, and the S3-credentials path used to rebuild
  it without the heap — after one **Configure → Apply & Restart** both servers
  ran with the JVM default (a quarter of host memory) and logged to the install
  directory, while the console still showed the install-time `768m`. Confirm
  with `jcmd <pid> VM.flags | tr ' ' '\n' | grep MaxHeapSize`.
- **The heap you give at install is the process size Flink starts with.** It
  used to lose to the packaged default `memory.process.size` (1728m /
  1600m), so whatever heap was entered at install, every TaskManager ran the
  default. Check with `grep process.size conf/config.yaml` on the instance, not
  only the console's record.
- **The env path is a chango record, so it can be written while the instance is
  stopped.** That is deliberate: the case that matters is a heap too large for
  the host, where the process is already dead. Config *files* can now be
  written on a stopped or failed instance as well (only `STARTING`/`STOPPING`
  is refused — see [Config Change Gate](../features/config-runtime-only.md)).

### Roles that can be tuned

Every role chango runs as a long-lived JVM accepts a `JvmConfig`. Two were
missing until recently and are called out because an older install will not
offer them:

- **Spark History Server.** Its heap follows the size of the event logs it
  renders, not the size of the cluster, and the launcher default is a flat 1 GB.
  It is usually the first daemon to die of OOM on a busy lakehouse, and what the
  operator sees is "the history UI is down".
- **Schema Registry.** Its heap follows the number of subjects and versions it
  holds. The co-located one had no setting at all.

!!! warning "A post-install change must be persisted, or a scale-out undoes it"
    chango stores the changed `JvmConfig` in cluster settings so a later
    scale-out installs the new instance with it. Without that the new instance
    comes up on the **install-time** heap and the cluster quietly runs two
    different sizes. If you are auditing an older install, compare a scaled-out
    instance's actual `-Xmx` against the others rather than against the UI.

## Trino: the RAM-percentage default

Trino is the one component whose heap default has a real history, because Trino's own packaged `jvm.config` assumes a dedicated node.

Chango's rendered `etc/jvm.config` sets:

```
-XX:InitialRAMPercentage=30
-XX:MaxRAMPercentage=30
```

Rather than a fixed `-Xmx`. The reasoning, in order:

- **80% (the value chango shipped earlier) is wrong here.** It is right for a dedicated Trino node and badly wrong on a chango host that also runs Ontul, ShannonStore data nodes, a Kafka broker, and a node manager. Trino would claim almost the whole machine and starve its neighbours.
- **A fixed `-Xmx` is wrong as a *default*.** It is correct only for the node size the author had in mind and silently over- or under-commits every other machine in the fleet.
- **Leaving heap unset is also wrong.** The JVM's implicit default (roughly 25% of RAM) varies by JVM version, so the cluster's memory behaviour would change under a JDK upgrade with nothing in the config to explain it.

30% is bounded, node-proportional, scales predictably across heterogeneous hosts, and is version-stable. An operator who *does* have a dedicated Trino node should raise it — either with a higher `MaxRAMPercentage` via `extra`, or with an explicit `-Xmx`.

### The heap floor

Trino refuses to start if the heap is below `query.max-memory-per-node + memory.heap-headroom-per-node`. Chango's defaults are `1GB` and `512MB`, so the floor is **1.5 GB** — meaning 30% of RAM clears it on a node of roughly 5 GB or more. On a smaller node you must either lower those two properties on the *Properties* tab or set an explicit `-Xmx` above the floor. A Trino instance that dies immediately after `start` with a memory-configuration error is almost always this.

### How an explicit heap override is merged

When you set `heapMin` and/or `heapMax` for Trino, chango does **not** simply append your lines to the default file. It merges, with three rules:

1. **The two `RAMPercentage` knobs are dropped.** They are mutually exclusive with an explicit heap. Crucially this applies even to a *min-only* override — otherwise `MaxRAMPercentage` would survive and cap max heap at the percentage regardless of what you asked for.
2. **Every other flag Trino needs is preserved.** `-XX:G1HeapRegionSize`, `-XX:+ExitOnOutOfMemoryError`, `-Djdk.attach.allowAttachSelf`, `-XX:+EnableDynamicAgentLoading`, and the rest of the required set stay exactly as chango wrote them. Overriding heap must never silently drop a flag Trino needs to run.
3. **Lines are deduped by flag key.** `-XX:MaxRAMPercentage=80` and `-XX:MaxRAMPercentage=30` are the *same* key; `-Xms512m` and `-Xms2g` are both `-Xms`. Insertion order follows the chango default; an `extra` entry that names an existing flag replaces its value in place, and a genuinely new flag is appended.

Rule 3 exists because the admin UI's Configure panel loads the on-disk `jvm.config` and echoes **every** line back as `extra` when you save. Without dedup, each save appended the whole default set again — the file grew without bound on every edit, and re-introduced the very `RAMPercentage` lines a heap override was supposed to remove. Heap is owned by `heapMin` / `heapMax`: an `-Xms` / `-Xmx` typed into `extra` is ignored rather than fighting the dedicated fields.

## Applying a change

JVM configuration is not hot-reloadable — the JVM reads it once at process start.

1. Open the cluster in the admin UI → **Configure** → *JVM* tab (per role).
2. Set `heapMin` / `heapMax`, add any `extra` flags, Save.
3. **Restart** the affected instances. Chango rewrites the config file on save but does not bounce the process for you; a rolling restart, role by role, keeps the cluster serving.

The edit is refused only while an instance is `STARTING` or `STOPPING`; a stopped or failed cluster accepts it and reads it at the next start — see [Config Change Gate](../features/config-runtime-only.md).

## Verifying on the host

Read the rendered file:

```bash
# Trino
sudo cat /opt/components/<instanceId>/etc/jvm.config
# Most other components
sudo cat /opt/components/<instanceId>/conf/jvm.conf
```

Then confirm the running process actually picked it up — the file on disk is what chango *intends*, the command line is what the JVM *got*:

```bash
ps -eo comm,args --no-headers | awk '$1=="java"' | grep -F "<instanceId>" \
  | tr ' ' '\n' | grep -E '^-X'
```

!!! tip "Filter to `java` first"
    A bare `ps -ef | grep <instanceId>` also matches **the grep itself and the
    shell command you are running** — including an ssh command line that happens
    to contain the instance id. That has produced "the process is not running"
    and "the restart did not happen" conclusions that were simply wrong.
    Filtering on the command name removes the whole class.

And check the heap the JVM resolved, which is the only number that settles a `RAMPercentage` question:

```bash
# JDK 25 is extracted under /opt by the java25 ansible role —
# /opt/openlogic-openjdk-25.0.3+9-linux-x64 for the shipped build.
sudo -u trino /opt/openlogic-openjdk-25*/bin/jcmd <pid> VM.flags \
  | tr ' ' '\n' | grep -E 'MaxHeapSize|InitialHeapSize'
```

`MaxHeapSize` is in bytes — divide by 1024³ for GB. On a 16 GB node with the 30% default you should see roughly 4.8 GB.

## Sizing guidance

There is no universal answer, but a workable starting point on a shared chango host:

| Component role | Starting heap | Notes |
|---|---|---|
| Trino coordinator | 30% (default) | Planning and coordination, not data. Rarely the bottleneck. |
| Trino worker | 30% (default), raise on a dedicated node | Raise `query.max-memory-per-node` together with the heap, or the extra heap goes unused. |
| Ontul master | 1–2 GB | Metadata, IAM, audit ingest. |
| Ontul worker | Scale with query concurrency | The Arrow-native execution path is largely off-heap; do not equate heap with query capacity. |
| ShannonStore data node | 1–2 GB | Storage path is I/O-bound; heap is not the lever. |
| ShannonStore API server | 1–2 GB | Raise under heavy concurrent S3 traffic. |
| Kafka broker | 1–4 GB | Kafka relies on the OS page cache — leave RAM *unallocated* rather than growing the heap. |

Reserve headroom for the OS page cache on every host. Component processes that do bulk I/O (Kafka, ShannonStore, anything reading Parquet) get more from free page cache than from a larger heap.

## Remote JMX is off on the Kafka family

Kafka's launcher, `kafka-run-class.sh`, fills an empty `KAFKA_JMX_OPTS` with
`-Dcom.sun.management.jmxremote` and authentication and SSL **off**, and without
a `jmxremote.port` the JVM opens its RMI registry on a random high port, on every
interface. A 3-node install had six such listeners — broker, ZooKeeper, Connect
and Schema Registry processes — that nobody asked for: unauthenticated remote
management, and ports the [Port Allocator](../features/port-allocator.md) cannot
see (one sat two numbers outside the UI Proxy band; on a busier host it lands
inside somebody's band and that component "will not start" with no holder
named).

chango now sets the launcher's JMX variable to a single space in the **instance
environment** of every Kafka-family role — `KAFKA_JMX_OPTS` for the broker,
ZooKeeper and Connect, `SCHEMA_REGISTRY_JMX_OPTS` for the Schema Registry
(standalone or co-located). A space, not an empty string: the launchers test
`[ -z "$…_JMX_OPTS" ]`, and an empty value brings the default back. The
environment rather than `kafka-env.sh`, because the Confluent registry package
has no `config/` directory and reads a different variable anyway. **Apply &
Restart** rewrites every role, so a cluster installed earlier is closed on its
next restart; until then it keeps its random ports (the numbers change on each
restart, which is easy to misread as "closed").

This closes a default; it does not decide monitoring. To expose JMX, add
`-Dcom.sun.management.jmxremote.port=<port>` — with the authentication flags
that belong with it — to that role's JVM **extra** options. The port is then a
value someone chose, and it shows in the console.

## Troubleshooting

- **Component `FAILED` right after start, log shows an OOM or heap-configuration error.** Compare the heap in the rendered file against the node's RAM and, for Trino, against the heap floor above.
- **Your `-Xmx` seems to be ignored on Trino.** Confirm you set it in the *JVM* tab's `heapMax` field, not as an `extra` entry — `extra` deliberately ignores `-Xms` / `-Xmx`.
- **`jvm.config` keeps growing with duplicate lines.** That was the pre-dedup behaviour. Upgrade the master (see [Upgrade](upgrade.md) or the [Patch System](../features/patch-system.md)); the merge is fixed at the render layer, so the next Configure save produces a clean file.
- **Heap changed but nothing happened.** The process was not restarted. Check the process start time against the file mtime.

## Related

- [Component Operations](component-operations.md) — the install / configure request shape these blocks live in.
- [Config Change Gate](../features/config-runtime-only.md) — which instance states accept a config change, and why.
- [Cluster Operations](cluster-operations.md) — rolling restarts and scale-out.
