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

1. The leader (and only the leader) runs the `ComponentMetricsCollector` thread on a fixed interval.
2. For each managed `ComponentInstance`, the leader resolves which NM hosts it and sends `OpCode.COMPONENT_METRICS_REQ` over the internal NIO protocol.
3. The NM runs `ps` against the instance's pid and returns `{ cpu, memRss, alive }` as JSON.
4. The leader appends a `Sample` (`ts, instanceId, cpu, memRss`) to an in-memory circular buffer. Older samples past `chango.metrics.retention.seconds` (default 3600 s) are evicted.
5. The admin UI's per-cluster page polls `/admin/api/<component>/<clusterId>/metrics` every 5 s and renders the recharts line chart from the returned series.

Followers do not collect — they do not have authoritative inventory. After a leader change the new leader's history is empty for the first interval, then populates.

## In-memory only

The metric history is held only in the leader's JVM heap. A master restart resets the chart back to zero. There is **no on-disk persistence** of metric samples and no external Prometheus shipping (out of the box). This is a deliberate tradeoff — metric stores are an entirely separate operational layer, and most teams already have one. What chango provides is the admin-UI dashboard.

To ship metrics to a real time-series database, run a node_exporter / process_exporter alongside chango and scrape per host. The chango master also exposes the same JSON the UI uses, so a small adapter can scrape `/admin/api/.../metrics` directly.

## What the admin UI shows

Per cluster page (Trino cluster, Spark cluster, …) carries two charts:

- **CPU%** — one line per instance in the cluster, last hour.
- **Memory (RSS, MB)** — one line per instance in the cluster, last hour.

Per chango-cluster page also shows node-level CPU / memory across every NM in the fleet.

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
