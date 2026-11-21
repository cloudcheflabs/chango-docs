# NeoRunBase

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "neorunbase-1",
  "componentType": "neorunbase",
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
| GET | [`/admin/api/neorunbase`](#get-admin-api-neorunbase) | Any signed-in user | `changoctl neorunbase list` |
| GET | [`/admin/api/neorunbase/install-defaults`](#get-admin-api-neorunbase-install-defaults) | Any signed-in user | `changoctl neorunbase defaults` |
| POST | [`/admin/api/neorunbase`](#post-admin-api-neorunbase) | Administrator | `changoctl neorunbase install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/neorunbase/{id}`](#get-admin-api-neorunbase-id) | Any signed-in user | `changoctl neorunbase get ID` |
| DELETE | [`/admin/api/neorunbase/{id}`](#delete-admin-api-neorunbase-id) | Administrator | `changoctl neorunbase delete ID [--purge-data]` |
| POST | [`/admin/api/neorunbase/{id}/start`](#post-admin-api-neorunbase-id-start) | Administrator | `changoctl neorunbase start ID` |
| POST | [`/admin/api/neorunbase/{id}/stop`](#post-admin-api-neorunbase-id-stop) | Administrator | `changoctl neorunbase stop ID` |
| POST | [`/admin/api/neorunbase/{id}/restart`](#post-admin-api-neorunbase-id-restart) | Administrator | `changoctl neorunbase restart ID` |
| GET | [`/admin/api/neorunbase/{id}/metrics`](#get-admin-api-neorunbase-id-metrics) | Any signed-in user | `changoctl neorunbase metrics ID` |
| GET | [`/admin/api/neorunbase/{id}/config`](#get-admin-api-neorunbase-id-config) | Any signed-in user | `changoctl neorunbase config get ID` |
| POST | [`/admin/api/neorunbase/{id}/config`](#post-admin-api-neorunbase-id-config) | Administrator | `changoctl neorunbase config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/neorunbase/{id}/scale`](#post-admin-api-neorunbase-id-scale) | Administrator | `changoctl neorunbase scale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/neorunbase/{id}/nginx`](#get-admin-api-neorunbase-id-nginx) | Any signed-in user | `changoctl neorunbase nginx get ID` |
| POST | [`/admin/api/neorunbase/{id}/nginx`](#post-admin-api-neorunbase-id-nginx) | Administrator | `changoctl neorunbase nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/neorunbase/{id}/credentials`](#post-admin-api-neorunbase-id-credentials) | Administrator | `changoctl neorunbase credentials set ID [--admin-password V] [--admin-otok V]` |

## GET `/admin/api/neorunbase` { #get-admin-api-neorunbase }

- **Permission:** Any signed-in user
- **CLI:** `changoctl neorunbase list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/neorunbase" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/neorunbase/install-defaults` { #get-admin-api-neorunbase-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl neorunbase defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/neorunbase/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/neorunbase` { #post-admin-api-neorunbase }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `NeorunBaseClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (neorunbase-) when blank. |
| `version` | string | `"1.0.0"` |  |
| `packageFile` | string | `"neorunbase/neorunbase-1.0.0.tar.gz"` | Package path under the master's components dir. |
| `masterKey` | string |  | NEORUNBASE_MASTER_KEY value — required, identical across the cluster, >= 32 chars. |
| `retiredKeyRef` | string |  | Reinstall with the retired key of a previously deleted cluster, named by that cluster's id. |
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance (count should be odd: 1, 3, 5, ...). |
| `coordinatorNodes` | list |  | One NM nodeId per Coordinator instance. |
| `datanodeNodes` | list |  | One NM nodeId per DataNode instance. |
| `pgInstanceId` | string | `""` | Optional — id of a chango-installed PostgreSQL instance. |
| `pgHost` | string |  | PostgreSQL connection used by the Coordinator — the database must already exist. |
| `pgPort` | int | `5432` |  |
| `pgDatabase` | string | `"postgres"` |  |
| `pgUser` | string | `"postgres"` |  |
| `pgPassword` | string | `""` |  |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `coordinatorJvm` | object:JvmConfig |  | Optional JVM tuning for the Coordinator role, seeded into every coordinator's conf/jvm.conf at install time. |
| `datanodeJvm` | object:JvmConfig |  | Optional JVM tuning for the DataNode role; same semantics as #coordinatorJvm. |
| `properties` | map |  | Optional neorunbase.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the product's own logs; blank keeps the install-dir default. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.0.0", "packageFile": "neorunbase/neorunbase-1.0.0.tar.gz", "pgPort": 5432, "pgDatabase": "postgres"}'
```

## GET `/admin/api/neorunbase/{id}` { #get-admin-api-neorunbase-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl neorunbase get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/neorunbase/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/neorunbase/{id}` { #delete-admin-api-neorunbase-id }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/neorunbase/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/neorunbase/{id}/start` { #post-admin-api-neorunbase-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/neorunbase/{id}/stop` { #post-admin-api-neorunbase-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/neorunbase/{id}/restart` { #post-admin-api-neorunbase-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/neorunbase/{id}/metrics` { #get-admin-api-neorunbase-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl neorunbase metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/neorunbase/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/neorunbase/{id}/config` { #get-admin-api-neorunbase-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl neorunbase config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/neorunbase/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/neorunbase/{id}/config` { #post-admin-api-neorunbase-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `NeorunBaseConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | neorunbase.properties key=value edits applied to every Coordinator + DataNode node. |
| `coordinatorJvm` | object:JvmConfig |  | JVM tuning for the Coordinator group (conf/jvm.conf); null/empty → unchanged. |
| `datanodeJvm` | object:JvmConfig |  | JVM tuning for the DataNode group (conf/jvm.conf); null/empty → unchanged. |
| `logDir` | string |  | Absolute directory the product writes its own logs under, or blank for the default (a logs directory inside each instance's install dir). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "coordinatorJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/neorunbase/{id}/scale` { #post-admin-api-neorunbase-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `NeorunBaseScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `coordinatorNodes` | list |  | One NM nodeId per Coordinator instance to add. |
| `datanodeNodes` | list |  | One NM nodeId per DataNode instance to add. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "coordinatorNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/neorunbase/{id}/nginx` { #get-admin-api-neorunbase-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl neorunbase nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/neorunbase/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/neorunbase/{id}/nginx` { #post-admin-api-neorunbase-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `NeorunBaseNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `18888` | TCP port nginx listens on for the proxied Coordinator admin endpoint. |
| `coordinatorInstanceIds` | list |  | Coordinator instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 18888}'
```

## POST `/admin/api/neorunbase/{id}/credentials` { #post-admin-api-neorunbase-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl neorunbase credentials set ID [--admin-password V] [--admin-otok V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `adminPassword` | string |
| `adminOtok` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/neorunbase/<id>/credentials" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"adminPassword": "<value>", "adminOtok": "<value>"}'
```
