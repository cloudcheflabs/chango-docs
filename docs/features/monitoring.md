# Monitoring & Metrics

Chango samples CPU% and resident memory of every host and every managed component process and keeps a short in-memory history that backs the admin UI's CPU / memory charts. The metrics layer is built in — no Prometheus / Grafana / external agent is required to see the cluster's resource usage.

## What is sampled

| Sample | Source | Cadence |
|---|---|---|
| Node CPU / memory | `/proc/loadavg`, `/proc/meminfo`, `/proc/stat` on each NM | Pulled by the leader from each NM every `chango.metrics.collect.interval.seconds` (default 10 s) |
| Component CPU / memory | `ps -p <pid> -o %cpu=,rss=` on the NM that hosts the instance | Same cadence; one `ps` per managed process |
| Component alive | `ProcessHandle.of(pid).isAlive()` | Same cadence |

For components whose pid file lives in a 0700 directory (Trino's `var/var/run/launcher.pid`, ZooKeeper sometimes), the NM falls back to `sudo cat` to read it. The pid that ends up in the metric record is the one the chango master tracks for stop / restart.

## How the data flows

Every master runs the `ComponentMetricsCollector` thread on a fixed interval. What it does depends on whether the master is the elected leader:

1. **Leader path** — for each managed `ComponentInstance`, the leader resolves which NM hosts it and sends `OpCode.COMPONENT_METRICS_REQ` over the internal NIO protocol.
2. **NM response** — the NM runs `ps` against the instance's pid and returns `{ cpu, memRss, alive }` as JSON.
3. **Leader ring** — the leader appends a `Sample` (`ts, instanceId, cpu, memRss`) to an in-memory circular buffer (`localHistory`). Older samples past `chango.metrics.retention.seconds` (default 3600 s) are evicted.
4. **Follower path** — every non-leader master calls the leader over `OpCode.COMPONENT_METRICS_HISTORY_REQ` and replaces its own `leaderHistory` ring with the leader's snapshot. This means a follower can serve the per-cluster metrics endpoint without having to re-poll any NM — and after a leader failover, the new leader's own samples come up within one interval while the previous leader's snapshot is still being served on the surviving followers.
5. **Admin UI** polls `/admin/api/<component>/<clusterId>/metrics` (per-cluster line charts) and `/admin/api/monitoring/hosts` (Dashboard host roll-up) every 5 s.

The ring that backs `history(ids)` is `localHistory` on the leader and `leaderHistory` on followers — admin endpoints never see an empty answer just because the call landed on the wrong master.

## In-memory only

The metric history is held only in the leader's JVM heap. A master restart resets the chart back to zero. There is **no on-disk persistence** of metric samples and no external Prometheus shipping (out of the box). This is a deliberate tradeoff — metric stores are an entirely separate operational layer, and most teams already have one. What chango provides is the admin-UI dashboard.

To ship metrics to a real time-series database, run a node_exporter / process_exporter alongside chango and scrape per host. The chango master also exposes the same JSON the UI uses, so a small adapter can scrape `/admin/api/.../metrics` directly.

## What the admin UI shows

### Cluster Dashboard

The Dashboard ("Cluster Dashboard" sidebar entry) is the single landing page for the chango control plane's own usage:

- **Stat cards** — master count, NM count, average daemon CPU, total daemon heap in use.
- **Hosts section** — one collapsible card per host with:
    - role chips (`MASTER` / `LEADER` / `NM`)
    - OS-wide 1-minute load average and core count, host physical memory used / total
    - sum of CPU% and resident memory across every RUNNING chango daemon on the host
    - sum of CPU% and resident memory across every RUNNING component instance pinned to the host
- **Expand the card** to see the breakdown: per-daemon table (master/NM with reachable / ready / leader status, heap usage) and per-instance component table (component type, cluster id, instance id, role, CPU%, mem RSS — sorted descending by CPU).
- **Daemon line charts** under the host section render the last hour of CPU% and heap in MB per daemon (the same series chango has always shown).

The host roll-up is served by `GET /admin/api/monitoring/hosts`. The payload shape:

```json
[
  {
    "host": "172.31.11.169",
    "hasMaster": true,
    "hasNodeManager": true,
    "isLeader": true,
    "ready": true,
    "daemons": [ {"nodeId":"...","role":"master","cpu":0.3,"memUsed":...,"memMax":...}, ... ],
    "os": { "load1m": 0.13, "cpuCores": 2, "memTotal": 8042622976, "memFree": 1825447936 },
    "componentTotals": { "instances": 10, "cpu": 5.0, "memRss": 2932228096 },
    "components": [ {"instanceId":"trino-v-coordinator-1","componentType":"trino","clusterId":"trino-v","role":"coordinator","cpu":3.6,"memRss":1283457024,"ts":1234567890}, ... ]
  }
]
```

OS metrics (`os.load1m / cpuCores / memTotal / memFree`) are sourced from the NM's `NodeMetrics.local()` response, which now reports the host's `OperatingSystemMXBean` values in addition to the JVM heap and process CPU. When a host's NM jar is older than the master's, the OS row falls back to `0` — refresh the NM's `chango-common.jar` to repopulate.

### Per-cluster pages

Per cluster page (Trino cluster, Spark cluster, …) carries two charts:

- **CPU%** — one line per instance in the cluster, last hour.
- **Memory (RSS, MB)** — one line per instance in the cluster, last hour.

## Process health

Beyond CPU / memory, every component instance carries a textual status (`STARTING / RUNNING / STOPPING / STOPPED / ERROR`). Chango derives that from:

- The last lifecycle action it issued (`start` → STARTING, `stop` → STOPPING).
- The NM's liveness signal (the `ps` and `ProcessHandle.isAlive()` checks above).
- A successful pid read after start (no pid file → ERROR).

If a component process dies outside of chango's control (OOM, segfault, manual kill), the next metrics interval flips it to "alive = false" and the chango master moves the status to `ERROR`. The cluster page surfaces the failure within ~10 s.

## Tuning

| Knob | Default | Purpose |
|---|---|---|
| `chango.metrics.collect.interval.seconds` | 10 | How often the leader walks every component and asks each NM for samples |
| `chango.metrics.retention.seconds` | 3600 | How long the in-memory history is kept |
| `chango.component.op.timeout.ms` | 120000 | Timeout for individual `COMPONENT_METRICS_REQ` to a slow NM — keep high enough to not race |

Increasing the interval lowers admin-side overhead at the cost of chart resolution; raising the retention buys longer history at the cost of leader JVM heap (each sample is ~64 bytes).
