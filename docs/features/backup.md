# Backup & Restore

Chango's control-plane state — KMS, IAM, component inventory — lives in three RocksDB stores on the master. The built-in `BackupService` packs all three (plus the patch library and a manifest) into a single `tar.gz` and uploads it to an S3-compatible target on demand or on a schedule. `chango-cli backup` is the operator side: list archives, check which master key one needs, and restore.

## What is in a backup

The archive stores **absolute paths**, so it extracts back over the same locations it came from.

| Archive entry | Default location | What it contains |
|---|---|---|
| KMS RocksDB | `<base.data.dir>/master/kms` | The keystore — versioned KEKs, sealed under the master key |
| IAM RocksDB | `<base.data.dir>/master/iam` | Users, groups, policies, access keys |
| Metadata RocksDB | `<base.data.dir>/master/metadata` | Component inventory, per-cluster settings (including managed product master keys), gateway topology, nginx state, `backup.s3.*` config, retired product keys |
| Patch library | `<base.data.dir>/master/patches` | Every patch tarball uploaded via `POST /admin/api/patch/upload`, plus its parsed manifest. Included only if the directory exists |
| `manifest.json` | generated | See below |

Including the patch library means a fresh-install restore can re-serve every previously-uploaded patch without the operator re-uploading from the build host. Followers catch up via PATCH_INDEX / PATCH_FETCH automatically — see [Patch System](patch-system.md#non-leader-catch-up-pr-5).

### manifest.json

```json
{
  "backupId": "20260808T024859-59e9eb89",
  "createdAt": "2026-08-08T02:48:59.697788815Z",
  "hostname": "ip-172-31-4-142",
  "changoVersion": "3.0.0",
  "kmsRocksDbPath": "/opt/chango/data/master/kms",
  "iamRocksDbPath": "/opt/chango/data/master/iam",
  "metadataRocksDbPath": "/opt/chango/data/master/metadata",
  "masterKeyEnv": "CHANGO_MASTER_KEY",
  "masterKeyFingerprint": "ea65f9199a78782a",
  "s3Endpoint": "http://shannon-api:8081",
  "s3Bucket": "chango-backups",
  "s3Region": "us-east-1",
  "s3ObjectPrefix": "chango-backups/",
  "s3PathStyle": "true",
  "patchesDir": "/opt/chango/data/master/patches",
  "patchesIncluded": true
}
```

Two fields exist for reasons worth knowing:

- **`masterKeyFingerprint`** — the non-secret fingerprint of the key that seals this archive. It is the only way to tell *which* key opens a given archive once a rotation has happened; without it a wrong-key restore is discovered only when the master refuses to start. See [which key does this archive need](#which-key-does-this-archive-need).
- **The `s3*` fields** — restoring after a total loss means reaching S3 *before* the metadata store (which holds `backup.s3.*`) exists. The non-secret half of that config therefore travels inside the archive. Credentials deliberately do not.

The RocksDB paths are recorded **absolute**, resolved the same way `tar` resolved them. Restore uses them to move the existing directories aside before extracting; a relative path would resolve against the restoring process's working directory, protect the wrong directory, and then extract on top of the real one.

## What is NOT in a backup

- **The master key.** Chango never persists it — it is an environment variable held in process memory. The operator stores it out-of-band and re-supplies it at restore time. Without it the archive is mathematically undecryptable. See [KMS](kms.md#root-of-trust--the-master-key).
- **Per-component data** — Iceberg files on ShannonStore, NeoRunBase tables, ItdaStream topics, Kafka logs, kiok workflow state. Chango's backup is the *control-plane* backup; each component backs up its own data.

    The exception is **PostgreSQL**, which chango does back up — see [PostgreSQL Backup & Restore](postgres-backup.md). It is separate from this archive because the omission matters more there than elsewhere: Polaris keeps its metastore in a managed PostgreSQL, and that metastore is the only record of which Iceberg tables exist and where their metadata lives. It shares this page's `backup.s3.*` destination and differs only in object prefix.
- **Logs** — `/var/log/chango` is operational and excluded.

## Configuration

All keys live in the metadata store (envelope-encrypted) and are set through the admin UI or `POST /admin/api/backup/config`. They are **runtime config**, not `chango.properties` entries — see [Config Runtime-Only Policy](config-runtime-only.md).

| Key | Default | Notes |
|---|---|---|
| `backup.s3.endpoint` | — | `https://s3.<region>.amazonaws.com`, `http://<shannonstore-api>:8081`, a MinIO URL, … |
| `backup.s3.region` | `us-east-1` | SigV4 region; anything for non-AWS providers |
| `backup.s3.bucket` | — | Must already exist |
| `backup.s3.object-prefix` | `chango-backups/` | Key prefix inside the bucket |
| `backup.s3.path-style` | `true` | `false` for virtual-hosted addressing |
| `backup.s3.access-key` | — | |
| `backup.s3.secret-key` | — | Returned as `<set>` by `GET`, never echoed back |
| `backup.s3.sse` | `AES256` | Server-side encryption to request; `none` disables it |
| `backup.retention.days` | `0` | `0` keeps archives forever |
| `backup.cron` | *(empty)* | 5-field UNIX cron; empty disables scheduled runs |

`GET /admin/api/backup/config` additionally returns two read-only values: `backup.cron.nextFireTime` and `backup.masterKeyFingerprint` (the key a restore of today's archives will need).

### Server-side encryption is an explicit choice

The archive is already envelope-encrypted by chango, so SSE is defence in depth rather than the primary control. It is still requested by default, because AWS S3 always supports it.

Not every S3-compatible store does. **MinIO without a configured KMS answers `501 NotImplemented`**, and the upload fails outright:

```
PUT chango-backups/20260808T013432.tar.gz failed: HTTP 501 — this endpoint does not
implement server-side encryption (AES256). Either configure a KMS on it, or set
backup.s3.sse=none to upload without SSE (the archive is still KMS
envelope-encrypted by chango itself).
```

Chango does **not** silently retry without SSE. Quietly downgrading an encryption setting is exactly the kind of change that should never happen behind an operator's back, so the failure explains the trade-off and leaves the decision in config. Set `backup.s3.sse = none` for such endpoints; the `run` response echoes back which value was applied.

### Retention

`backup.retention.days > 0` deletes archives under the configured prefix that are older than the window. Pruning happens **after** a successful upload, never before, so a failed backup can never be the thing that deletes the last good archive. Objects whose `LastModified` the endpoint does not report are left alone rather than guessed at.

!!! warning "Keep product master keys at least as long as archives"
    An archive is worthless without the key that opens it. `backup.retention.days` is therefore the floor for how long a deleted product cluster's master key stays retrievable — see [Product master keys](product-master-keys.md#retention).

## Triggering a backup

### Admin UI

**Settings → Backup** — fill in the S3 fields, retention, SSE and cron, then **Save**; **Run backup now** triggers one immediately. The page also shows the master-key fingerprint a restore will require. Destination config is persisted envelope-encrypted in the metadata store.

### REST API

Config is a **`POST` merge-update of flat keys** — send only what you want to change:

```bash
curl -X POST -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{
    "backup.s3.endpoint": "http://shannon-api:8081",
    "backup.s3.region": "us-east-1",
    "backup.s3.bucket": "chango-backups",
    "backup.s3.object-prefix": "prod/",
    "backup.s3.path-style": "true",
    "backup.s3.access-key": "...",
    "backup.s3.secret-key": "...",
    "backup.s3.sse": "AES256",
    "backup.retention.days": "30",
    "backup.cron": "0 2 * * *"
  }' $BASE/admin/api/backup/config
# → {"status":"ok"}

curl -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/backup/run
```

`run` answers with:

```json
{
  "backupId": "20260808T024859-59e9eb89",
  "objectKey": "prod/20260808T024859-59e9eb89.tar.gz",
  "sizeBytes": 101864,
  "createdAt": "2026-08-08T02:48:59.7Z",
  "masterKeyFingerprint": "ea65f9199a78782a",
  "serverSideEncryption": "AES256",
  "pruned": []
}
```

`GET /admin/api/backup/config` and `POST /admin/api/backup/run` are leader-only; an invalid cron is rejected with `400` at save time rather than silently never firing.

### Schedule

| Cron | Meaning |
|---|---|
| `0 2 * * *` | Daily at 02:00 |
| `0 */6 * * *` | Every 6 hours |
| `0 3 * * 0` | Sundays at 03:00 |

Every master arms the scheduler — the expression lives in replicated config — but **only the leader actually runs the backup**. A follower's metadata store trails the leader, so its archive would be slightly stale, and with retention enabled two masters would prune concurrently. Followers keep the schedule armed, so a new leader picks up the very next window. Leave `backup.cron` empty to disable scheduled runs; **Run backup now** still works.

## Inspecting archives

```bash
$ /opt/chango/bin/chango-cli.sh backup list
BACKUP-ID                                              SIZE  LAST-MODIFIED
20260808T024859-59e9eb89                             101864  2026-08-08T02:48:59.6Z
20260808T013916-eb4600af                              73545  2026-08-08T01:39:16.4Z
```

S3 coordinates are resolved in this order: command-line flags → `$CHANGO_BACKUP_S3_*` env vars → the running master's own config (read over the admin socket, which requires `$CHANGO_MASTER_KEY`). The last source is a convenience for `list` / `inspect`; **restore cannot use it**, because restore runs with the master stopped.

### Which key does this archive need?

```bash
$ /opt/chango/bin/chango-cli.sh backup inspect --backup-id 20260808T024859-59e9eb89
backupId        : 20260808T024859-59e9eb89
createdAt       : 2026-08-08T02:48:59.697788815Z
changoVersion   : 3.0.0
sizeBytes       : 101864
kms dir         : /opt/chango/data/master/kms
iam dir         : /opt/chango/data/master/iam
metadata dir    : /opt/chango/data/master/metadata
patches included: true

requires master key fp : ea65f9199a78782a
this host holds        : 251b8c532ce30e9b
restorable here        : NO

Supply that key as $CHANGO_MASTER_KEY (or add it to $CHANGO_MASTER_KEY_PREVIOUS)
before restoring. Without it this archive cannot be decrypted —
the key is deliberately never included in the backup.
```

`inspect` exits non-zero when the archive is not restorable on this host, so it can gate a restore in a script. Add the retired key to `$CHANGO_MASTER_KEY_PREVIOUS` and it flips to `YES`:

```
requires master key fp : ea65f9199a78782a
this host holds        : 251b8c532ce30e9b, ea65f9199a78782a
restorable here        : YES
```

This is what makes a master-key rotation safe for existing archives — see [Rotating the master key](kms.md#rotating-the-master-key).

Archives written before fingerprints were recorded report `master key : NOT RECORDED` and can only be matched by their `createdAt` against your own key history.

## Restoring

Restore replaces the master's own RocksDB directories, which cannot be swapped under a live process holding their `LOCK`s. It therefore runs from a separate process with the master **stopped** — which is also why it is not a REST call, and why the S3 credentials must come from flags or env rather than from the metadata store that is being restored.

```bash
export CHANGO_MASTER_KEY=<the key that archive needs>      # check with `backup inspect`
sudo -u chango /opt/chango/bin/stop-master.sh

sudo -u chango env \
  JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64 \
  CHANGO_MASTER_KEY="$CHANGO_MASTER_KEY" \
  CHANGO_BACKUP_S3_ENDPOINT=http://shannon-api:8081 \
  CHANGO_BACKUP_S3_BUCKET=chango-backups \
  CHANGO_BACKUP_S3_ACCESS_KEY=... \
  CHANGO_BACKUP_S3_SECRET_KEY=... \
  /opt/chango/bin/chango-cli.sh backup restore \
      --backup-id 20260808T024859-59e9eb89 --chown chango:chango --yes
```

What `restore` does, in order:

1. **Refuses if a master is answering** the admin socket, naming `stop-master.sh`.
2. **Verifies the master key** against the manifest fingerprint *before* touching any directory. A wrong key stops here with nothing changed.
3. **Moves the existing directories aside** to `<dir>.before-restore-<epochMillis>`. Extracting over them would leave stale SST files behind and corrupt the RocksDB.
4. **Extracts** the archive (`tar -xzf … -C /`), excluding the manifest entry — it is already parsed in memory, and it would otherwise land at `/`.
5. **Rolls the directories back** if extraction fails, so a failed restore never leaves the master with no KMS/IAM/metadata. If the rollback itself fails, it prints where the preserved copies are.
6. **`chown -R`** to the user given by `--chown` (tar restores as the invoking user).
7. **Opens the restored keystore** and reports `verified: restored keystore opens with the supplied master key`. This is the check that turns "the restore looked fine but the master will not start" into an error at restore time.

Then start the master, re-passing the same `-D` arguments the cluster was first started with — chango does not persist them:

```bash
sudo -u chango -E /opt/chango/bin/start-master.sh \
    -Dchango.zk.serverList=host1:2181,host2:2181,host3:2181 -Dchango.zk.rootPath=/chango
```

!!! warning "Multi-master: restore one node only"
    Restore the node you want to be authoritative, then clear the **other** masters' KMS / IAM / metadata directories before starting them — they re-sync from the leader. Restoring several nodes independently gives you several divergent copies of the same cluster.

### Manual equivalent

If you cannot use the CLI (for example, an archive whose manifest predates absolute paths), the same steps by hand:

```bash
sudo -u chango /opt/chango/bin/stop-master.sh
sudo mv /opt/chango/data/master/kms{,.old}
sudo mv /opt/chango/data/master/iam{,.old}
sudo mv /opt/chango/data/metadata{,.old}
sudo tar -xzf <archive>.tar.gz -C / --exclude='chango-backup-manifest-*.json'
sudo chown -R chango:chango /opt/chango/data
export CHANGO_MASTER_KEY=<key for that archive>
sudo -u chango -E /opt/chango/bin/start-master.sh -Dchango.zk.serverList=… -Dchango.zk.rootPath=/chango
```

Chango ships no systemd unit — the operator drives the master through `bin/start-master.sh` / `bin/stop-master.sh` with the master key in the environment. Ansible deliberately creates neither a unit nor a sysconfig file.

### Restoring node managers

NMs hold no authoritative state. Once the master is back, NMs still alive against the same ZooKeeper re-register automatically. Lost NMs can be reinstalled with [`add-nodemanager.yml`](../installation/automated.md#adding-a-node-manager-later-add-nodemanageryml) or the [manual recipe](../operations/cluster-operations.md#add-another-node-manager); the leader re-attaches component instances bound to that nodeId.

### Component data

Restoring the master gives back the component **inventory** — which instance lives on which NM with which configuration — not component data. After the inventory is back and the clusters are visible in the admin UI, start each cluster again; the component process reads its own data from its still-present data dir. If a product's data dir was lost too, note that its master key is what decrypts it: see [Product master keys](product-master-keys.md).

## Backup hygiene

- Treat every archive as cluster-confidential. Chango-side encryption is intact, but the archive is everything an attacker needs to impersonate your control plane if they ever learn the master key.
- **Never store the master key in the same bucket as the archives.** One compromise would otherwise hand over both halves.
- Keep retired master keys as long as the archives sealed under them. `backup inspect` tells you which fingerprint each archive needs.
- Test a restore. A backup you have never restored from is a backup you do not have — and `restore` now verifies the keystore actually opens, so a test restore gives a real answer.
