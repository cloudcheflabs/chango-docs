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

The path inside `logs/` is component-specific (`server.log` for Trino, `master.log` for Spark, …). The admin UI's "Logs" panel knows the right path per component type and shows a tail in the browser.

## Tailing from the admin UI

Every component page in the admin UI has a "Logs" button per instance. Click it and the master opens a streaming tail over the internal NIO protocol against the NM that hosts the instance. The tail is read-only — you can scroll, search, and copy, but not write.

The chango master itself can also be tailed from the admin UI's Master log page (driven by an in-memory `RingBufferAppender` that holds the last N log lines).

## REST surface

| Endpoint | Returns |
|---|---|
| `GET /admin/api/components/<instanceId>/logs?lines=N` | Last N lines of the given component instance |
| `GET /admin/api/nodes/logs?nodeId=<id>&which=master&lines=N` | Last N lines of `chango-master.log` on a master node (or `which=nm` for the NM log) |

Both routes stream the tail via internal NIO from the relevant host (master or NM), so the leader does not need to live on the same disk as the log file.

## What is *not* in chango logs

- **Component data-plane logs** that the component does not write to the install dir. Trino's query history is in Trino's metastore. Spark application logs from a finished job live in the configured event log directory (typically on S3 / ShannonStore).
- **System logs** (`journalctl`, `dmesg`). The chango master + NM services do log to journald via their systemd units; chango does not re-shove those into the admin UI. Use `journalctl -u chango-master` directly when you need them.

## Log level

The default level is `INFO`. To raise (or quiet) a specific logger, edit `conf/logback.xml`:

```xml
<logger name="com.cloudcheflabs.chango.master.component.ShannonStoreClusterService" level="DEBUG"/>
```

Reload the logback config without restart with `kill -HUP <chango-master pid>` (logback's `<jmxConfigurator/>` is on) or by re-touching the file (logback's `scanPeriod` is 30 s).

## Shipping logs out

The admin UI is a debugging surface, not a log lake. For real log aggregation, point a customer agent (Vector, Fluent Bit, …) at `/var/log/chango/` and `/opt/components/*/logs/` on every host. Chango does not bundle one — operators typically already have their own.
