# Configuration Reference

Every setting chango reads from `chango.properties`, with its default and what changing it does.

Some settings are deliberately **not** here — the S3 backup destination, the gateway topology, per-component settings. Those live in the replicated metadata store and are edited from the admin UI, so that a value is the same on every master and survives a reinstall. See [Config Runtime-Only Policy](../features/config-runtime-only.md) for where the line falls and why.

## Resolution order

Highest priority first:

1. `-Dkey=value` — a JVM system property on the start command
2. `KEY_WITH_UNDERSCORES` — an environment variable (`chango.master.admin.port` → `CHANGO_MASTER_ADMIN_PORT`)
3. `conf/chango.properties`
4. Built-in defaults in `ChangoConfig`

Values may reference other keys with `${other.key}`, which is how the RocksDB paths are all derived from `chango.base.data.dir`.

The start scripts do **not** persist the `-D` arguments they were given. A master restarted without them falls back to the file, which is why [Backup & Restore](../features/backup.md#restoring) tells you to re-pass the same arguments the cluster was first started with.

## Base

| Key | Default | Notes |
|---|---|---|
| `chango.base.data.dir` | `./data` | Root of every RocksDB store and staged package |
| `chango.log.path` | `./logs` | |
| `chango.log.level` | `INFO` | |
| `chango.log.mode` | `ASYNC_FILE` | `ASYNC_FILE`, `FILE`, `CONSOLE` |

## ZooKeeper

| Key | Default | Notes |
|---|---|---|
| `chango.zk.serverList` | `localhost:2181` | **Must be set for any multi-host install.** The default is right for a single-box dev setup and wrong everywhere else — a node manager left on it retries forever and never registers, and the master then reports "no registered node manager" when a component is installed. `start-node-manager.sh` refuses to launch rather than let that happen silently |
| `chango.zk.rootPath` | `/chango` | Chroot for all chango znodes |
| `chango.zk.sessionTimeoutMs` | `30000` | |
| `chango.zk.connectionTimeoutMs` | `10000` | |

## Master

| Key | Default | Notes |
|---|---|---|
| `chango.master.nodeId` | *(derived)* | `master-<hostname>-<adminPort>`. Sticky-leader election needs it stable across restarts — set it explicitly only if the hostname is not |
| `chango.master.host` | `0.0.0.0` | |
| `chango.master.admin.port` | `8080` | Admin UI + REST API |
| `chango.master.internal.port` | `19999` | Internal NIO protocol |
| `chango.master.zk.client.port` | `2181` | Control-plane ZK. Also fed to the [port allocator](../features/port-allocator.md) so a component-bundled ZK on the same host does not get the same default |
| `chango.master.zk.peer.port` | `2888` | |
| `chango.master.zk.leader.port` | `3888` | |
| `chango.master.admin.worker.threads` | `8` | Pool for blocking admin handlers (component install / start / stop), kept off the Netty event loop so package I/O does not stall other requests |
| `chango.master.admin.ui.static.path` | `./chango-admin-ui/dist` | |
| `chango.master.admin.ui.context.path` | `/admin` | Set to `/` to serve at the root. **Must match the UI build's `CHANGO_ADMIN_UI_BASE`** — the SPA is compiled with its base path |
| `chango.master.leader.deference.window.ms` | `3000` | How long a starting master waits for the previous incumbent to reclaim leadership. See [Sticky Leader Election](../features/sticky-leader.md) |
| `chango.master.components.dir` | `./components` | Where component packages are read from before being pushed to node managers |
| `chango.master.component.install.timeout.ms` | `600000` | Must cover transferring a multi-hundred-MB package |
| `chango.master.component.op.timeout.ms` | `120000` | Start / stop / restart / delete |
| `chango.master.component.transfer.chunk.bytes` | `4194304` | Streaming frame size, so neither side buffers a whole package |

## Node manager

| Key | Default | Notes |
|---|---|---|
| `chango.nodemanager.nodeId` | *(derived)* | `nm-<hostname>-<internalPort>` |
| `chango.nodemanager.host` | `0.0.0.0` | |
| `chango.nodemanager.internal.port` | `19998` | |
| `chango.nodemanager.components.state.dir` | `./data/components` | Component metadata, staged packages, process logs |
| `chango.nodemanager.component.java.homes` | *(three JDKs)* | `<version>:<home>` pairs. Spark and Livy get Java 11, most components Java 17, Trino Java 25 — see [Versions](../components/versions.md#jdks) |
| `chango.nodemanager.component.op.timeout.ms` | `120000` | A start command that does not exit within this window is treated as a foreground process and left running |
| `chango.nodemanager.health.check.interval.ms` | `10000` | |
| `chango.nodemanager.health.check.timeout.ms` | `5000` | |
| `chango.nodemanager.health.max.consecutive.failures` | `3` | Failures before the node is marked unhealthy |
| `chango.nodemanager.shutdown.drain.timeout.seconds` | `60` | |

## Component port bands

Each band has a `.base` and a `.range`, both overridable:

```properties
chango.component.port.<band>.base  = 19200
chango.component.port.<band>.range = 200
```

Defaults are the allocator's built-ins — `200` for every range. The full band list and the firewall implications are in [Port Allocator](../features/port-allocator.md).

## KMS

Master and a co-located node manager keep separate sub-trees so they do not contend for RocksDB's single-writer `LOCK`.

| Key | Default | Notes |
|---|---|---|
| `chango.kms.enabled` | `true` | |
| `chango.master.kms.rocksdb.path` | `${chango.base.data.dir}/master/kms` | |
| `chango.nm.kms.rocksdb.path` | `${chango.base.data.dir}/nm/kms` | |
| `chango.kms.master.key.env` | `CHANGO_MASTER_KEY` | The environment variable the master key is read from. Chango never persists the key itself |
| `chango.kms.master.key.previous.env` | `CHANGO_MASTER_KEY_PREVIOUS` | Retired keys still accepted **for reading**, comma-separated, so a rotation rolls through the cluster without downtime and archives sealed under an older key stay restorable. Writes always use the current key |
| `chango.kms.pbkdf2.iterations` | `200000` | |
| `chango.kms.encrypt.internal.protocol` | `true` | Encrypts internal-protocol payloads — which is what protects credentials in transit to a node manager |
| `chango.kms.internal.protocol.key.id` | `internal-protocol` | |
| `chango.kms.fetch.max.retries` | `60` | A starting node manager waits for the leader's keystore |
| `chango.kms.fetch.retry.interval.ms` | `1000` | |

## IAM

| Key | Default | Notes |
|---|---|---|
| `chango.master.iam.rocksdb.path` | `${chango.base.data.dir}/master/iam` | |
| `chango.nm.iam.rocksdb.path` | `${chango.base.data.dir}/nm/iam` | |
| `chango.iam.admin.user` | `admin` | |
| `chango.iam.admin.password` | `admin` | The bootstrap password only. Chango **blocks every non-auth route** until it is rotated, so this value stops working on first login |
| `chango.iam.audit.dir` | `${chango.base.data.dir}/master/iam-audit` | Operator audit log — currently only `iam:reset-password` writes here |

## Admin recovery socket

A local Unix domain socket (mode `600`) for out-of-band operator commands. Authentication is OS-level: only a process sharing the master's filesystem identity can connect, and there is no network surface. See [Admin Password Recovery](../features/admin-password-recovery.md).

| Key | Default |
|---|---|
| `chango.admin.socket.enabled` | `true` |
| `chango.admin.socket.path` | `${chango.base.data.dir}/master/admin.sock` |

## Metadata store

Master only — a node manager has no metadata RocksDB.

| Key | Default |
|---|---|
| `chango.master.metadata.rocksdb.path` | `${chango.base.data.dir}/master/metadata` |
| `chango.metadata.kms.key.id` | `metadata-encryption` |

## Cluster readiness and membership

| Key | Default | Notes |
|---|---|---|
| `chango.cluster.min.nodemanagers.ready` | `0` | Node managers that must register before the master reports ready. `0` means do not wait |
| `chango.cluster.peers.ready.timeout.ms` | `60000` | |
| `chango.cluster.hosts.sync.enabled` | `true` | Each node rewrites a chango-managed block in `/etc/hosts` with every cluster node's `<private-ip> <fqhn>`, so hostname-based connections resolve without DNS. Entries outside the block are untouched — see [Hosts Sync](../features/hosts-sync.md) |
| `chango.cluster.hosts.sync.interval.ms` | `30000` | |
| `chango.cluster.domain` | `chango.private` | Internal DNS domain; every node's FQHN is `<short-hostname>.<domain>` |
| `chango.cluster.nginx.reconcile.interval.ms` | `15000` | How often the leader reconciles each ShannonStore cluster's nginx upstream against the live API servers |

## Metrics

In-memory only; resets on master restart. Backs the admin UI's CPU / memory charts.

| Key | Default |
|---|---|
| `chango.metrics.collect.interval.seconds` | `10` |
| `chango.metrics.retention.seconds` | `3600` |

## RPC timeouts

| Key | Default |
|---|---|
| `chango.query.rpc.timeout.ms` | `30000` |
| `chango.internal.rpc.timeout.ms` | `10000` |
| `chango.master.broadcast.timeout.ms` | `5000` |

## Admin tokens and HTTP

| Key | Default | Notes |
|---|---|---|
| `chango.admin.token.access.expiry.ms` | `900000` | 15 min |
| `chango.admin.token.refresh.expiry.ms` | `86400000` | 24 h |
| `chango.admin.http.max.content.size.bytes` | `10485760` | 10 MiB. Raise it for large patch uploads |

## PostgreSQL backup

Static defaults for [PostgreSQL Backup & Restore](../features/postgres-backup.md). The schedule, retention and prefix are runtime config, edited from the admin UI.

| Key | Default | Notes |
|---|---|---|
| `chango.postgres.backup.timeout.ms` | `21600000` | 6 h — a ceiling on a stuck process, not a budget |
| `chango.postgres.backup.job.history` | `50` | Jobs kept for the UI |
| `chango.postgres.backup.object.prefix` | `chango-postgres-backups/` | |
| `chango.postgres.bin.dir` | `/usr/pgsql-16/bin` | Host fact — where `pg_dumpall` / `psql` live |
| `chango.postgres.run.as.user` | `postgres` | Host fact — the OS user, and the local superuser |
| `chango.postgres.backup.log.tail.lines` | `500` | Output lines retained from a run |
