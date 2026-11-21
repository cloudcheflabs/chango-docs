# Patches & Backup

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

| Method | Path | Permission | changoctl |
|---|---|---|---|
| GET | [`/admin/api/backup/config`](#get-admin-api-backup-config) | Any signed-in user | `changoctl backup config get` |
| POST | [`/admin/api/backup/config`](#post-admin-api-backup-config) | Administrator | `changoctl backup config set -f body.json \| --set K=V` |
| POST | [`/admin/api/backup/run`](#post-admin-api-backup-run) | Administrator | `changoctl backup run` |
| GET | [`/admin/api/backup/runs`](#get-admin-api-backup-runs) | Any signed-in user | `changoctl backup runs` |
| GET | [`/admin/api/backup/archives`](#get-admin-api-backup-archives) | Any signed-in user | `changoctl backup archives [--limit V] [--offset V]` |
| GET | [`/admin/api/patch/library`](#get-admin-api-patch-library) | Any signed-in user | `changoctl patch list [--component V]` |
| POST | [`/admin/api/patch/upload`](#post-admin-api-patch-upload) | Administrator | `changoctl patch upload --file FILE` |
| GET | [`/admin/api/patch/level`](#get-admin-api-patch-level) | Any signed-in user | `changoctl patch level --cluster V` |
| GET | [`/admin/api/patch/{patchId}/raw`](#get-admin-api-patch-patchid-raw) | Any signed-in user | `changoctl patch download PATCHID [-O FILE]` |
| POST | [`/admin/api/patch/{patchId}/apply`](#post-admin-api-patch-patchid-apply) | Administrator | `changoctl patch apply PATCHID` |
| POST | [`/admin/api/patch/rollback`](#post-admin-api-patch-rollback) | Administrator | `changoctl patch rollback --component V --cluster V [--to V]` |
| GET | [`/admin/api/patch/history`](#get-admin-api-patch-history) | Any signed-in user | `changoctl patch history --component V --cluster V` |

## GET `/admin/api/backup/config` { #get-admin-api-backup-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl backup config get`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/backup/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/backup/config` { #post-admin-api-backup-config }

- **Permission:** Administrator
- **CLI:** `changoctl backup config set -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/backup/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## POST `/admin/api/backup/run` { #post-admin-api-backup-run }

- **Permission:** Administrator
- **CLI:** `changoctl backup run`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/backup/run" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## GET `/admin/api/backup/runs` { #get-admin-api-backup-runs }

- **Permission:** Any signed-in user
- **CLI:** `changoctl backup runs`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/backup/runs" -H "Authorization: Bearer $T"
```

## GET `/admin/api/backup/archives` { #get-admin-api-backup-archives }

- **Permission:** Any signed-in user
- **CLI:** `changoctl backup archives [--limit V] [--offset V]`

**Query parameters:** `limit`, `offset`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/backup/archives?limit=<value>&offset=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/patch/library` { #get-admin-api-patch-library }

- **Permission:** Any signed-in user
- **CLI:** `changoctl patch list [--component V]`

**Query parameters:** `component`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/patch/library?component=<value>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/patch/upload` { #post-admin-api-patch-upload }

- **Permission:** Administrator
- **CLI:** `changoctl patch upload --file FILE`

**Body:** the patch tarball as raw bytes (`Content-Type: application/gzip`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/patch/upload" -H "Authorization: Bearer $T" -H 'Content-Type: application/gzip' --data-binary @patch.tgz
```

## GET `/admin/api/patch/level` { #get-admin-api-patch-level }

- **Permission:** Any signed-in user
- **CLI:** `changoctl patch level --cluster V`

**Query parameters:** `cluster`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/patch/level?cluster=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/patch/{patchId}/raw` { #get-admin-api-patch-patchid-raw }

- **Permission:** Any signed-in user
- **CLI:** `changoctl patch download PATCHID [-O FILE]`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/patch/<patchId>/raw" -H "Authorization: Bearer $T"
```

## POST `/admin/api/patch/{patchId}/apply` { #post-admin-api-patch-patchid-apply }

- **Permission:** Administrator
- **CLI:** `changoctl patch apply PATCHID`

**Body (JSON):**

| Field | Type | Description |
|---|---|---|
| `clusterId` | string | target cluster — required for a component patch, omitted for the platform's own patch |
| `restartMode` | string | default `rolling` |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/patch/<patchId>/apply" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"clusterId": "<value>", "restartMode": "<value>"}'
```

## POST `/admin/api/patch/rollback` { #post-admin-api-patch-rollback }

- **Permission:** Administrator
- **CLI:** `changoctl patch rollback --component V --cluster V [--to V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `component` | string |
| `cluster` | string |
| `to` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/patch/rollback" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"component": "<value>", "cluster": "<value>", "to": "<value>"}'
```

## GET `/admin/api/patch/history` { #get-admin-api-patch-history }

- **Permission:** Any signed-in user
- **CLI:** `changoctl patch history --component V --cluster V`

**Query parameters:** `component`, `cluster`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/patch/history?component=<value>&cluster=<value>" -H "Authorization: Bearer $T"
```
