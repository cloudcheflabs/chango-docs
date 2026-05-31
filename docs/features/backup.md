# Backup & Restore

Chango's control-plane state — IAM, KMS, component inventory — lives in three RocksDB stores on the master. The built-in `BackupService` packs all three (plus a manifest) into a single tar archive and uploads it to an S3-compatible target on demand or on a schedule.

## What is in a backup

| Archive entry | Source | What it contains |
|---|---|---|
| `kms/` | `/var/lib/chango/kms/` | KEKs wrapped by the cluster master DEK |
| `iam/` | `/var/lib/chango/iam/` | Users, groups, policies, access keys (password hashes / access secrets are stored hashed / encrypted at the field level inside RocksDB) |
| `metadata/` | `/var/lib/chango/metadata/` | Component inventory, per-cluster settings, gateway topology, nginx state |
| `data/master/patches/` | `<base.data.dir>/master/patches/` | Air-gapped patch library — every patch tarball previously uploaded via `POST /admin/api/patch/upload`, plus its parsed manifest. Included only if the directory exists. |
| `manifest.json` | generated | `timestamp`, `hostname`, `chango.version`, archive checksum, `patchesIncluded` flag |

Including the patch library means a fresh-install restore can re-serve every previously-uploaded patch without the operator re-uploading from the build host. Followers catch up via PATCH_INDEX / PATCH_FETCH automatically — see [Patch System](patch-system.md#non-leader-catch-up-pr-5).

## What is NOT in a backup

- **The cluster root secret** that derives chango's master DEK. The operator owns and stores this out-of-band; without it the backup is mathematically undecryptable. See [KMS](kms.md).
- **Per-component data** — Iceberg files on ShannonStore, NeoRunBase tables, ItdaStream topics, Kafka logs, PostgreSQL data dirs, kiok workflow state. Each component manages its own data lifecycle. Chango's backup is the control-plane backup; the data plane is backed up via the component's own mechanism (most use the same S3 endpoint).
- **Logs** — `/var/log/chango` is operational and excluded.

## Backup destination

The backup target is an S3-compatible endpoint. The same `BackupService` works against AWS S3, ShannonStore, MinIO, or any provider that speaks SigV4 path-style or virtual-hosted style.

| Field | Notes |
|---|---|
| `endpoint` | `https://s3.<region>.amazonaws.com` or `http://<shannonstore-api>:8080` |
| `region` | SigV4 region — for non-AWS providers, anything (typically `us-east-1`) |
| `bucket` | Pre-created |
| `prefix` | Optional path prefix (e.g. `chango-backups/<cluster-name>/`) |
| `accessKey` / `secretKey` | Long-lived S3 credentials |

S3 PUT requests are signed with SigV4 and request server-side encryption (`x-amz-server-side-encryption: AES256`). The payload body is already KMS-envelope-encrypted at the chango layer, so the SSE-S3 layer is a defence-in-depth measure rather than the primary control.

## Triggering a backup

### Admin UI

Sidebar → **Backup** → fill in S3 endpoint / bucket / credentials → **Backup Now**. The destination configuration is persisted (envelope-encrypted in the metadata RocksDB) so subsequent backups reuse the same target.

### REST API

```bash
# Configure the destination (one-time)
curl -X PUT -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d '{
    "endpoint": "http://shannonstore:8080",
    "region": "us-east-1",
    "bucket": "chango-backups",
    "prefix": "prod/",
    "accessKey": "...",
    "secretKey": "..."
  }' $BASE/admin/api/backup/config

# Run a backup
curl -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/backup/run
```

The response includes the S3 key (`prod/chango-<timestamp>-<uuid>.tar.gz`) and the SHA-256 of the archive.

### Schedule

Set a cron expression in the destination config — the leader runs the backup on that schedule. Default is **off**.

`BackupService` arms its cron scheduler at master bootstrap (before leader election finishes), so a follower with a `backup.cron` setting in the metadata RocksDB keeps the scheduler armed even before it wins leadership. `runBackup()` itself is idempotent — every fire produces an immutable S3 object with a fresh `<backupId>` — so a multi-master race at most causes a duplicate S3 PUT, never corrupted state.

The config UI takes a standard 5-field cron (`min hour dom mon dow`). Examples:

| Cron | Meaning |
|---|---|
| `0 2 * * *` | Daily at 02:00 |
| `0 */6 * * *` | Every 6 hours |
| `0 3 * * 0` | Sundays at 03:00 |

Leave the field empty to disable scheduled backups; the **Backup Now** button still works.

## Restoring

Restore is an out-of-band procedure on a fresh master node. Chango deliberately ships no systemd unit — the operator drives the master directly via `bin/start-master.sh` / `bin/stop-master.sh` with the cluster root secret in env.

1. **Stop** the running chango master (if anything is running).
2. **Download** the desired backup object from S3 (e.g. with `aws s3 cp` or `curl` + SigV4).
3. **Untar** it into the master's RocksDB parent dir:

   ```bash
   sudo -u chango /opt/chango/bin/stop-master.sh
   sudo -u chango /opt/chango/bin/stop-zk.sh
   sudo rm -rf /var/lib/chango/{kms,iam,metadata}
   sudo tar -xzf chango-<timestamp>-<uuid>.tar.gz -C /var/lib/chango/
   sudo chown -R chango:chango /var/lib/chango/
   ```

4. **Supply the cluster root secret** on the new master node (same secret as the source cluster — without it the restored RocksDB is undecryptable).
5. **Start** ZooKeeper and the chango master with `CHANGO_MASTER_KEY` supplied from your secret manager:

   ```bash
   export CHANGO_MASTER_KEY=<from secret manager>
   sudo -u chango -E /opt/chango/bin/start-zk.sh
   sleep 3
   sudo -u chango -E /opt/chango/bin/start-master.sh
   ```

   The master opens the restored RocksDB, decrypts KEKs with the master DEK derived from the supplied root secret, and resumes leader election. Component instances stored in the metadata RocksDB are visible again immediately.

### Restoring node managers

NMs do not need to be restored — they have no authoritative state. After the master is back, NMs that are still alive against the same ZooKeeper re-register automatically. NMs that were lost can be reinstalled via [`ansible add-nodemanager.yml`](../installation/automated.md#adding-a-node-manager-later-add-nodemanageryml) (or the manual recipe in [Add another node manager](../operations/cluster-operations.md#add-another-node-manager)) — once registered, the leader re-attaches any component instances that were bound to that nodeId.

### Component data

Restoring the chango master gives you back the component **inventory** — which instance lives on which NM, with which configuration. It does not bring back component data (Iceberg files, NeoRunBase tables, …) — those are backed up via their own component-specific paths and restored separately. After the inventory is restored and the components are visible in the admin UI, start each component cluster again; the component process reads its own data from its still-present data dir.

## Backup hygiene

- Treat each backup tarball as cluster-confidential. Even though chango-side envelope encryption is intact, the tarball contains everything an attacker needs to impersonate your control plane if they ever learn the root secret.
- Keep at least one offline copy. The cluster root secret and the backup tarball stored on the same S3 bucket gives an attacker both halves on a single compromise.
- Test restore. A backup you have never restored from is a backup you do not have.
