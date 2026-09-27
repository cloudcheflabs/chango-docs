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

## Authentication — password storage

| Key | Default | Notes |
|---|---|---|
| `chango.auth.password.hash.iterations` | `600000` | PBKDF2-HMAC-SHA256 iterations used when a local password is written. The count travels with each stored hash, so raising it does **not** invalidate existing passwords. Values written by an earlier version as an unsalted SHA-256 still verify and are rewritten on their owner's next successful login. |

## Single sign-on (OIDC / SAML / LDAP)

Every setting below can also be managed from the console under **Settings → SSO**,
which stores it in the replicated metadata store and applies it on every master with
no restart. **Stored settings win over the properties file**: the file brings a
cluster up, and the console is how it is changed afterwards — if the file won, a
console change would be reverted by the next restart, silently. See
[Single Sign-On](../features/sso.md).

### Identity mapping (all three providers)

| Key | Default | Notes |
|---|---|---|
| `chango.sso.group.mappings` | (empty) | `idpGroup:changoGroup` pairs, comma-separated. Empty means provider group names are used as they are. **Once set the mapping is exhaustive** — a group not named here is dropped, so creating a group at the provider cannot grant access on this cluster by itself. |
| `chango.sso.allow.unmapped.groups` | `false` | Whether an identity whose groups all map to nothing may still sign in. Off deliberately: such a session has no policies and is denied every action. The directory endpoint reports that case as `403`, separately from a wrong password's `401`. |
| `chango.sso.federated.session.seconds` | `3600` | Lifetime of a federated session — the record that lets every master and node manager resolve a federated caller's groups by name. It bounds how long access outlives a revocation at the provider, which this cluster is not told about. No refresh token is issued, for the same reason. |

### OpenID Connect

| Key | Default | Notes |
|---|---|---|
| `chango.sso.oidc.enabled` | `false` | Enable the OIDC provider. |
| `chango.sso.oidc.issuer` | (empty) | Issuer URL. Endpoints and the signing key set are read from its discovery document. |
| `chango.sso.oidc.client.id` | (empty) | Client id registered at the provider. |
| `chango.sso.oidc.client.secret` | (empty) | Client secret. Credential — never read back by the console. |
| `chango.sso.oidc.redirect.uri` | `http://localhost:8080/admin/api/auth/sso/oidc/callback` | Must match the redirect URI registered at the provider exactly, and must be the address browsers reach — the load balancer's, not one master's. |
| `chango.sso.oidc.scopes` | `openid profile email` | Deliberately excludes `groups`: it is not a standard scope, and a provider that does not define it rejects the whole authorization request with `invalid_scope`. |
| `chango.sso.oidc.username.claim` | `preferred_username` | Claim holding the login name. |
| `chango.sso.oidc.groups.claim` | `groups` | Claim holding group membership. The provider must be configured to include it. |
| `chango.sso.oidc.audience` | (empty) | Expected audience. Empty falls back to the client id. A token issued for another application is refused even though it is genuine. |

### SAML 2.0

| Key | Default | Notes |
|---|---|---|
| `chango.sso.saml.enabled` | `false` | Enable the SAML provider. |
| `chango.sso.saml.idp.entity.id` | (empty) | Read automatically when the provider's metadata is imported from the console. |
| `chango.sso.saml.idp.sso.url` | (empty) | IdP single sign-on URL. |
| `chango.sso.saml.idp.certificate` | (empty) | Base64 IdP signing certificate. Every assertion's signature is verified against it. |
| `chango.sso.saml.sp.entity.id` | `chango` | This cluster's entity ID, as it appears in the SP metadata the provider imports. |
| `chango.sso.saml.sp.acs.url` | `http://localhost:8080/admin/api/auth/sso/saml/acs` | Assertion consumer URL. As with the OIDC redirect, this must be the address browsers reach. |
| `chango.sso.saml.nameid.format` | (empty) | Empty omits the request entirely and lets the provider issue what it is configured for — naming one breaks more integrations than it fixes. |
| `chango.sso.saml.sign.requests` | `false` | Needs an SP keypair, generated from the console; re-import the SP metadata at the provider afterwards. |
| `chango.sso.saml.username.attribute` | `uid` | Assertion attribute holding the login name. |
| `chango.sso.saml.groups.attribute` | `groups` | Assertion attribute holding group membership. |

### LDAP / Active Directory

| Key | Default | Notes |
|---|---|---|
| `chango.sso.ldap.enabled` | `false` | Enable the directory provider. With it on, a directory password works on the ordinary login form too. |
| `chango.sso.ldap.url` | `ldap://ldap.example.com:389` | Use `ldaps://` or enable StartTLS — otherwise the bind password crosses the network in the clear. |
| `chango.sso.ldap.bind.dn` | (empty) | Service account that searches for user entries. Authentication is search then bind: the user's DN cannot be constructed, since Active Directory puts people under `CN=John Doe,OU=Staff,…`. |
| `chango.sso.ldap.bind.password` | (empty) | Service account password. Credential. |
| `chango.sso.ldap.user.base.dn` | (empty) | Subtree searched for user entries. |
| `chango.sso.ldap.user.filter` | `(uid={0})` | `{0}` is the login name, escaped per RFC 4515 before substitution. Active Directory usually wants `(sAMAccountName={0})`. |
| `chango.sso.ldap.group.base.dn` | (empty) | Subtree searched for groups. |
| `chango.sso.ldap.group.filter` | `(member={0})` | `{0}` is the user's DN. Membership is read both from this search **and** from the user's `memberOf`, because directories disagree about which side records it. |
| `chango.sso.ldap.group.name.attribute` | `cn` | Attribute holding the group name. |
| `chango.sso.ldap.starttls` | `false` | Upgrade a plain `ldap://` connection with StartTLS. |

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
