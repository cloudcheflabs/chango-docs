# Logging

Chango's own logs and every managed component's logs are accessible from the admin UI and from disk. Chango itself uses logback; managed components keep their own log frameworks and chango exposes their log files for tailing without changing what they write.

## Where chango writes its own logs

`/var/log/chango/` on every chango host (`chango.log.path` in `chango.properties`). The master and the node manager each write their own files:

| File | Source |
|---|---|
| `/var/log/chango/chango-master.log` | Chango master JVM (rolling) |
| `/var/log/chango/chango-nodemanager.log` | Chango node manager JVM (rolling) |
| `/var/log/chango/chango-zk.log` | Bundled ZooKeeper on master hosts |
| `/var/log/chango/_ops.log` | Per-NM ops log — every shell command the NM ran on behalf of an install / start / stop, with exit codes |

Rolling is logback's default policy — daily, with `.gz` retention. Tune in `conf/logback.xml`.

## Where managed component logs live

Each component writes under its own install dir:

```
/opt/components/<instanceId>/logs/...
```

The path inside `logs/` is component-specific (`server.log` for Trino,
`master.log` for Spark, …).

Chango does **not** keep a table of those paths. The node manager scans two
directories and tails the newest `*.log` / `*.out` it finds there, skipping GC
logs and the `data/` tree:

1. the log directory configured for the instance, if one was set;
2. the install directory.

In that order, and the first one that yields anything wins. The order is the
whole point. When logs have been moved off the install disk, what is left
under the install directory is the launcher's own stdout capture — whose last
line is literally `Output redirected to /data1/log/...`. Scanning the install
directory first showed that line as "the log" for ontul, kiok, Flink, Polaris
and PostgreSQL, and for the Trino gateway, which leaves nothing behind at all,
the panel came up empty while an 8 KB log sat in the configured directory.

The configured directory is read from the variables the platform itself sets
on the instance — `CHANGO_PREPARE_LOG_DIR` for every component, and
`<PRODUCT>_LOG_PATH` for the first-party ones that read their own variable.

### Set it at install — the first start already writes somewhere

Every component's install request takes `logDir`, and the install drawer has a
**Log Directory** tab next to *Install*. Setting it there means the first
process ever started writes to the volume you chose.

Doing it afterwards works too, but it costs a restart, and until then the logs
are on the disk the platform itself runs on — which is the disk the move exists
to protect.

### Move it off the platform disk — every component, right after install

That default puts logs on whatever filesystem the install directory lives on.
A streaming job or a busy broker fills it, and when it fills, the component and
everything sharing that disk stop. Set a log directory on a volume sized for it.

Every component page in the admin UI has a **Log Directory** tab (chango's own
logs are the exception — those are set in the ansible variables before install).

```bash
curl -sS -X POST $BASE/admin/api/<component>/<clusterId>/config \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"logDir":"/data1/log"}'
```

chango creates `<logDir>/<instanceId>` as the component's own account and
replaces the install dir's `logs` with a symlink to it, so the paths above keep
working and the admin UI tail is unaffected:

```bash
ls -ld /opt/components/trino-1-coordinator-1/logs
#   … -> /data1/log/trino-1-coordinator-1
```

The mechanism differs per component — launcher flags, `SPARK_LOG_DIR`,
`env.log.dir`, `LOG_DIR`, a `-D` property, a redirect — and chango applies the
right one. Scale-out reuses the setting, so new instances land in the same
place.

!!! warning "Messaging has **two** directories, and the big one is not the logs"
    Application logs (`server.log`, `controller.log`) and **topic data** are
    different things that both say "log". Topic data is the messages
    themselves, sized by retention × ingest, and it defaults to the install
    directory.

    ```bash
    curl -sS -X POST $BASE/admin/api/kafka/<clusterId>/config \
      -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
      -d '{"logDir":"/data1/log","dataDir":"/data2/kafka-data"}'
    ```

    `dataDir` is a **root**; each broker gets `<root>/<instanceId>`, because two
    brokers can share a host and two brokers writing one `log.dirs` corrupt
    each other's partitions. Setting `log.dirs` directly through `properties`
    is dropped on purpose — it has to differ per broker.

    Moving it does **not** move the data: the broker starts empty at the new
    path. Replicated topics re-replicate from their leaders, but moving all
    brokers at once leaves nowhere to replicate from. Set it at install time, or
    move one broker at a time and confirm replication in between.

## Tailing from the admin UI

Every component page in the admin UI has a "Logs" button per instance. Click
it and the master opens a streaming tail over the internal NIO protocol
against the NM that hosts the instance. The tail is read-only — you can
scroll, search, and copy, but not write.

If the panel shows a handful of lines that look like installation output
(`tar: Ignoring unknown extended header keyword …`) rather than the component
running, the instance is on a build from before the scan order above was
fixed. The same symptom with an *empty* panel means the component writes
nothing under its install directory.

The chango master itself can also be tailed from the admin UI's Master log page (driven by an in-memory `RingBufferAppender` that holds the last N log lines).

## REST surface

| Endpoint | Returns |
|---|---|
| `GET /admin/api/components/<instanceId>/logs?lines=N` | Last N lines of the given component instance |
| `GET /admin/api/nodes/logs?nodeId=<id>&which=master&lines=N` | Last N lines of `chango-master.log` on a master node (or `which=nm` for the NM log) |

Both routes stream the tail via internal NIO from the relevant host (master or NM), so the leader does not need to live on the same disk as the log file.

## What is *not* in chango logs

- **Component data-plane logs** that the component does not write to the install dir. Trino's query history is in Trino's metastore. Spark application logs from a finished job live in the configured event log directory (typically on S3 / ShannonStore).
- **System logs** (`dmesg`, the OS journal). Chango ships **no** systemd units — the master and NM are started by `bin/start-master.sh` / `bin/start-node-manager.sh`, which redirect stdout/stderr to `<chango.log.path>/master.out` and `nodemanager.out`. `journalctl -u chango-master` returns nothing; read those `.out` files (and `chango.log`) instead.

## Log level

The default level is `INFO`. To raise (or quiet) a specific logger, edit `conf/logback.xml`:

```xml
<logger name="com.cloudcheflabs.chango.master.component.ShannonStoreClusterService" level="DEBUG"/>
```

Reload the logback config without restart with `kill -HUP <chango-master pid>` (logback's `<jmxConfigurator/>` is on) or by re-touching the file (logback's `scanPeriod` is 30 s).

## Shipping logs out

The admin UI is a debugging surface, not a log lake. For real log aggregation, point a customer agent (Vector, Fluent Bit, …) at `/var/log/chango/` and `/opt/components/*/logs/` on every host. Chango does not bundle one — operators typically already have their own.
