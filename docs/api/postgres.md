# PostgreSQL

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "postgres-1",
  "componentType": "postgres",
  "version": "1.4.1",
  "status": "RUNNING",
  "createdAt": 1795219200000,
  "lastUpdatedAt": 1795219260000,
  "settings": {
    "realm": "polaris-1",
    "clientSecret": "***"
  }
}
```

| Method | Path | Permission | changoctl |
|---|---|---|---|
| GET | [`/admin/api/postgres`](#get-admin-api-postgres) | Any signed-in user | `changoctl postgres list` |
| GET | [`/admin/api/postgres/install-defaults`](#get-admin-api-postgres-install-defaults) | Any signed-in user | `changoctl postgres defaults` |
| POST | [`/admin/api/postgres`](#post-admin-api-postgres) | Administrator | `changoctl postgres install [INSTANCEID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/postgres/{id}`](#get-admin-api-postgres-id) | Any signed-in user | `changoctl postgres get ID` |
| DELETE | [`/admin/api/postgres/{id}`](#delete-admin-api-postgres-id) | Administrator | `changoctl postgres delete ID [--purge-data]` |
| POST | [`/admin/api/postgres/{id}/start`](#post-admin-api-postgres-id-start) | Administrator | `changoctl postgres start ID` |
| POST | [`/admin/api/postgres/{id}/stop`](#post-admin-api-postgres-id-stop) | Administrator | `changoctl postgres stop ID` |
| POST | [`/admin/api/postgres/{id}/restart`](#post-admin-api-postgres-id-restart) | Administrator | `changoctl postgres restart ID` |
| GET | [`/admin/api/postgres/{id}/config`](#get-admin-api-postgres-id-config) | Any signed-in user | `changoctl postgres config get ID` |
| POST | [`/admin/api/postgres/{id}/config`](#post-admin-api-postgres-id-config) | Administrator | `changoctl postgres config set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/postgres/{id}/credentials`](#get-admin-api-postgres-id-credentials) | Administrator | `changoctl postgres credentials ID` |
| GET | [`/admin/api/postgres/metrics`](#get-admin-api-postgres-metrics) | Any signed-in user | `changoctl postgres metrics` |
| GET | [`/admin/api/postgres/backup-config`](#get-admin-api-postgres-backup-config) | Any signed-in user | `changoctl postgres backup-config get` |
| POST | [`/admin/api/postgres/backup-config`](#post-admin-api-postgres-backup-config) | Administrator | `changoctl postgres backup-config set -f body.json \| --set K=V` |
| GET | [`/admin/api/postgres/backup-jobs`](#get-admin-api-postgres-backup-jobs) | Any signed-in user | `changoctl postgres backup-jobs all` |
| GET | [`/admin/api/postgres/{id}/backup-jobs`](#get-admin-api-postgres-id-backup-jobs) | Any signed-in user | `changoctl postgres backup-jobs ID` |
| GET | [`/admin/api/postgres/{id}/backups`](#get-admin-api-postgres-id-backups) | Any signed-in user | `changoctl postgres backups ID [--limit V] [--offset V]` |
| POST | [`/admin/api/postgres/{id}/backup`](#post-admin-api-postgres-id-backup) | Administrator | `changoctl postgres backup ID` |
| POST | [`/admin/api/postgres/{id}/restore`](#post-admin-api-postgres-id-restore) | Administrator | `changoctl postgres restore ID --object-key V [--expect-sha256 V]` |

## GET `/admin/api/postgres` { #get-admin-api-postgres }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/postgres/install-defaults` { #get-admin-api-postgres-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/postgres` { #post-admin-api-postgres }

- **Permission:** Administrator
- **CLI:** `changoctl postgres install [INSTANCEID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `PostgresInstallRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `instanceId` | string |  | Unique instance id (e.g. pg-main). |
| `nodeId` | string |  | Target NM nodeId — must not already host a PostgreSQL instance. |
| `port` | int | `5432` | TCP port PostgreSQL listens on. |
| `password` | string |  | Password for the postgres superuser. |
| `version` | string | `"16"` |  |
| `packageFile` | string | `"postgresql/postgresql16-core-rocky9-x86_64.tar.gz"` | Package path under the master's components dir. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on the NM host under which the install dir is created. |
| `properties` | map |  | Operator-tunable postgresql.conf entries applied after initdb (after chango's per-instance port / listen_addresses append). |
| `logDir` | string |  | Absolute directory for the relational database's server log (logging_collector + log_directory). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"port": 5432, "version": "16", "packageFile": "postgresql/postgresql16-core-rocky9-x86_64.tar.gz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/postgres/{id}` { #get-admin-api-postgres-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/postgres/{id}` { #delete-admin-api-postgres-id }

- **Permission:** Administrator
- **CLI:** `changoctl postgres delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/postgres/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/postgres/{id}/start` { #post-admin-api-postgres-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl postgres start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/postgres/{id}/stop` { #post-admin-api-postgres-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl postgres stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/postgres/{id}/restart` { #post-admin-api-postgres-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl postgres restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/postgres/{id}/config` { #get-admin-api-postgres-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/postgres/{id}/config` { #post-admin-api-postgres-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl postgres config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `PostgresConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | postgresql.conf key=value edits. |
| `logDir` | string |  | Absolute directory for the relational database's server log (logging_collector + log_directory). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "logDir": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/postgres/{id}/credentials` { #get-admin-api-postgres-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl postgres credentials ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/<id>/credentials" -H "Authorization: Bearer $T"
```

## GET `/admin/api/postgres/metrics` { #get-admin-api-postgres-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres metrics`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/postgres/backup-config` { #get-admin-api-postgres-backup-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres backup-config get`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/backup-config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/postgres/backup-config` { #post-admin-api-postgres-backup-config }

- **Permission:** Administrator
- **CLI:** `changoctl postgres backup-config set -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres/backup-config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## GET `/admin/api/postgres/backup-jobs` { #get-admin-api-postgres-backup-jobs }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres backup-jobs all`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/backup-jobs" -H "Authorization: Bearer $T"
```

## GET `/admin/api/postgres/{id}/backup-jobs` { #get-admin-api-postgres-id-backup-jobs }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres backup-jobs ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/<id>/backup-jobs" -H "Authorization: Bearer $T"
```

## GET `/admin/api/postgres/{id}/backups` { #get-admin-api-postgres-id-backups }

- **Permission:** Any signed-in user
- **CLI:** `changoctl postgres backups ID [--limit V] [--offset V]`

**Query parameters:** `limit`, `offset`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/postgres/<id>/backups?limit=<value>&offset=<value>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/postgres/{id}/backup` { #post-admin-api-postgres-id-backup }

- **Permission:** Administrator
- **CLI:** `changoctl postgres backup ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres/<id>/backup" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## POST `/admin/api/postgres/{id}/restore` { #post-admin-api-postgres-id-restore }

- **Permission:** Administrator
- **CLI:** `changoctl postgres restore ID --object-key V [--expect-sha256 V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `objectKey` | string |
| `expectSha256` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/postgres/<id>/restore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"objectKey": "<value>", "expectSha256": "<value>"}'
```
