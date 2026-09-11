# PostgreSQL Backup & Restore

Chango's own [backup](backup.md) covers the control plane — KMS, IAM, the component inventory. It does not cover what lives *inside* a managed PostgreSQL instance, and for most clusters that is the more consequential omission.

The reason is the Polaris catalog. Polaris keeps its metastore in a chango-managed PostgreSQL, and that metastore is the only record of which Iceberg tables exist and where their metadata files live. Losing it does not lose a single byte of data in object storage — every Parquet file and every manifest is still there — but it loses every pointer into them. The master's archive knows a PostgreSQL instance exists; it knows nothing about its contents.

So each PostgreSQL instance can be dumped to S3 and restored from it, on demand or on a schedule.

## How it runs

The dump runs on the node manager hosting the instance and is uploaded to S3 from there. It never passes through the master.

```
Admin UI / REST                    Master (leader)                 Node manager
      │                                  │                               │
      │  POST /postgres/<id>/backup      │                               │
      ├─────────────────────────────────►│                               │
      │  ◄── { jobId, status: RUNNING }  │                               │
      │                                  │  PG_BACKUP_REQ                │
      │                                  ├──────────────────────────────►│
      │                                  │   { objectKey, s3 config }    │
      │  GET  /postgres/<id>/backup-jobs │                               │  pg_dumpall | gzip
      ├─────────────────────────────────►│                               │         │
      │  ◄── { status, sizeBytes, … }    │                               │         ▼
      │                                  │  ◄────────────────────────────┤   ┌──────────┐
      │                                  │   { objectKey, sha256, … }    │   │    S3    │
                                                                             └──────────┘
```

Two decisions in that picture are worth explaining.

**The dump does not travel through the master.** `pg_dumpall` is a local binary reading a local data directory, so it can only be produced on the node manager. It is also the one chango artifact with no upper bound — control-plane archives are megabytes, a customer database is whatever it is. Routing it through the master would put an arbitrarily large file on the master's heap and its network path twice, for nothing. Only the outcome comes back.

**Backup and restore are jobs, not request-response.** A dump runs for as long as it runs. Holding the HTTP call open for its duration means the browser gives up first, the operator retries, and two dumps of the same instance run at once. The REST call therefore starts a job and answers immediately; the UI polls it.

Only one operation runs per instance at a time. Two concurrent backups would merely waste work, but a restore racing anything else on the same instance leaves it in a state neither operation intended, so the second request is refused rather than queued.

## Credentials

Neither direction handles the PostgreSQL superuser password.

Chango initdb's every managed instance with `--auth-local=peer`, which makes the `postgres` OS user the local superuser. Both `pg_dumpall` and `psql` run as that user over the local socket, so there is no password to pass on a command line, leak into a process listing, or write to a log.

The S3 credentials do travel to the node manager, in the request payload — that is what the internal protocol's KMS payload encryption exists for.

The dump file itself stays `0600` for its whole life. It is written by `postgres`, so the node-manager user cannot read it to upload; rather than widening the mode — which would leave a world-readable copy of every database on the host for the length of the upload — ownership moves back to the node-manager user once the dump is complete, and moves to `postgres` again for a restore.

## Format

`pg_dumpall` plain SQL, gzipped. One file per instance covering roles, tablespaces and every database.

A `pg_dump -Fc` per database would restore faster in parallel, but it would silently drop the globals — and an instance backup that loses its roles restores into a database nobody can log into. The slower format is the one that actually restores.

## Where archives go

The S3 destination is the same `backup.s3.*` configuration the master's own backup uses, edited on **Settings → Backup** in the admin UI. One bucket and one credential pair serve both. Configuring them twice is how a rotated key ends up applied to one and not the other, with the second failing quietly.

Only the prefix differs:

| | Object key |
|---|---|
| Master control-plane archive | `chango-backups/<backupId>.tar.gz` |
| PostgreSQL archive | `chango-postgres-backups/<instanceId>/<timestamp>-<rand>.sql.gz` |

Each instance gets its own folder, so a listing sorts chronologically per instance and archives from different instances never collide.

If no S3 destination is configured, the Backup & Restore drawer says so and the **Back up now** button is disabled. There is no point offering an action that is known to fail.

## Configuration

The destination is shared; these three keys are PostgreSQL-specific and live in the metadata store, set from the drawer's **Schedule** tab or `POST /admin/api/postgres/backup-config`.

| Key | Default | Notes |
|---|---|---|
| `backup.postgres.object-prefix` | `chango-postgres-backups/` | Key prefix inside the shared bucket |
| `backup.postgres.cron` | *(empty)* | 5-field UNIX cron; empty means manual only |
| `backup.postgres.retention.days` | `0` | `0` keeps archives forever |

Static defaults are in `chango.properties`:

| Key | Default | Notes |
|---|---|---|
| `chango.postgres.backup.timeout.ms` | `21600000` (6 h) | A ceiling on a stuck process, not a budget — a large dump legitimately runs for hours |
| `chango.postgres.backup.job.history` | `50` | Jobs kept for the UI's history panel |
| `chango.postgres.backup.object.prefix` | `chango-postgres-backups/` | Default for the runtime key above |
| `chango.postgres.bin.dir` | `/usr/pgsql-16/bin` | Where `pg_dumpall` / `psql` live on a node-manager host |
| `chango.postgres.run.as.user` | `postgres` | The OS user, and the local superuser |
| `chango.postgres.backup.log.tail.lines` | `500` | Output lines retained from a run |

The last two are host facts rather than chango's to decide, which is why they are configurable: a site that installs PostgreSQL somewhere else needs a way to say so.

## Scheduling

Set a 5-field UNIX cron on the Schedule tab. When it fires, **every RUNNING instance** is backed up; instances that are stopped are skipped and logged rather than failing the run.

An invalid expression is rejected on save with a `400` naming the problem. Accepting it and silently never firing is the failure that gets discovered months later, when the backup is needed.

The next fire time is shown under the field, so "did I write that correctly" is answerable without waiting for 03:00.

Two details make the schedule behave under load:

- The next fire time is advanced **before** the backup runs. A dump that takes longer than the interval would otherwise be immediately due again on completion, and a slow instance would back up in a continuous loop.
- Only the leader dispatches. Followers keep the schedule armed — the expression lives in replicated config — so a new leader picks up the very next window rather than waiting for a restart.

If one instance fails, the others still run. A single unreachable database is not a reason to skip the rest of the fleet.

## Retention

`backup.postgres.retention.days` deletes archives older than the window, **after** a successful backup — so a failed run can never be what deletes the last good archive.

An object whose endpoint reports no `LastModified` is left alone rather than guessed at. Deleting a backup on missing metadata is not recoverable.

## Restore

Restore is always an explicit operator action naming both the instance and the archive. Pick an archive from the list and press **Restore**; a confirmation appears first, because the archive recreates every role and database it contains and therefore **replaces what is in the instance now**. Anything written since the archive was taken is lost.

There is deliberately no "restore the latest" shortcut. The situation where that would be convenient — everything is broken and the newest archive is the one you want — is also the situation where the newest archive may be the one that recorded the breakage.

An archive does not have to have come from the instance it is restored into. Restoring a production dump into a staging instance is a legitimate thing to want. It does have to live under the configured prefix, so a restore cannot be pointed at an arbitrary object in the bucket.

### Non-fatal errors

A dumpall replay always reports some errors that do not matter: dropping the role it is connected as, recreating the database it is connected to. Running with `ON_ERROR_STOP` would abort every restore on the first one.

So `psql` runs without it, and the **count of errors is returned and displayed** instead. `2 non-fatal` next to a completed restore is normal for a single-database instance. A number far larger than that is worth reading the job log over. Reporting only "ok" would make a genuinely broken restore indistinguishable from a healthy one.

### Checksum verification

`POST /postgres/<id>/restore` accepts an optional `expectSha256`. When present it is compared against the downloaded archive and the restore is refused on a mismatch, rather than replaying an archive that changed since it was written.

## REST API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/api/postgres/backup-config` | Prefix, cron, retention, and whether the shared S3 destination is usable |
| `POST` | `/admin/api/postgres/backup-config` | Merge-update of the three runtime keys |
| `GET` | `/admin/api/postgres/<id>/backups` | Archives for this instance, newest first |
| `POST` | `/admin/api/postgres/<id>/backup` | Start a backup; answers with the job record |
| `POST` | `/admin/api/postgres/<id>/restore` | Start a restore — `{ objectKey, expectSha256? }` |
| `GET` | `/admin/api/postgres/<id>/backup-jobs` | This instance's jobs, newest first |
| `GET` | `/admin/api/postgres/backup-jobs` | Every instance's jobs |

A job record:

```json
{
  "jobId": "6058ab64-2f5",
  "instanceId": "pg-main",
  "kind": "backup",
  "status": "COMPLETED",
  "startedAt": "2026-09-11T13:51:33Z",
  "finishedAt": "2026-09-11T13:51:36Z",
  "error": "",
  "objectKey": "chango-postgres-backups/pg-main/20260911T135136-9839c866.sql.gz",
  "sizeBytes": 1416,
  "sha256": "…",
  "durationMs": 3104
}
```

`status` is `RUNNING`, `COMPLETED` or `FAILED`. A restore record additionally carries `nonFatalErrors`.

### Example — back up and wait

```bash
BASE=http://<master>:8080
TOK=$(curl -s -X POST $BASE/admin/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{"username":"admin","password":"…"}' | jq -r .accessToken)

JOB=$(curl -s -X POST $BASE/admin/api/postgres/pg-main/backup \
      -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{}' \
      | jq -r .jobId)

until [ "$(curl -s $BASE/admin/api/postgres/pg-main/backup-jobs \
           -H "Authorization: Bearer $TOK" \
           | jq -r --arg j "$JOB" '.[] | select(.jobId==$j) | .status')" != RUNNING ]; do
  sleep 3
done
```

### Example — restore a named archive

```bash
curl -s -X POST $BASE/admin/api/postgres/pg-main/restore \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"objectKey":"chango-postgres-backups/pg-main/20260911T135136-9839c866.sql.gz"}'
```

## What this does not cover

- **Point-in-time recovery.** These are logical dumps at an instant, not WAL archiving. Recovery granularity is the backup interval.
- **Other components' data.** Iceberg files on ShannonStore, NeoRunBase tables, ItdaStream topics, Kafka logs, kiok workflow state — each component backs up its own. See [Backup & Restore](backup.md) for what the control-plane archive covers.
- **The chango master key.** Unchanged from the control-plane backup: chango never persists it, and without it the master's archives cannot be opened. PostgreSQL archives are not sealed with it — they are protected by the object store's access control and whatever server-side encryption it offers.
