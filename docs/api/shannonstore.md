# ShannonStore

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "shannonstore-1",
  "componentType": "shannonstore",
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
| GET | [`/admin/api/clusters`](#get-admin-api-clusters) | Any signed-in user | `changoctl shannonstore list` |
| GET | [`/admin/api/clusters/install-defaults`](#get-admin-api-clusters-install-defaults) | Any signed-in user | `changoctl shannonstore defaults` |
| POST | [`/admin/api/clusters`](#post-admin-api-clusters) | Administrator | `changoctl shannonstore install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/clusters/{id}`](#get-admin-api-clusters-id) | Any signed-in user | `changoctl shannonstore get ID` |
| DELETE | [`/admin/api/clusters/{id}`](#delete-admin-api-clusters-id) | Administrator | `changoctl shannonstore delete ID [--purge-data]` |
| POST | [`/admin/api/clusters/{id}/start`](#post-admin-api-clusters-id-start) | Administrator | `changoctl shannonstore start ID` |
| POST | [`/admin/api/clusters/{id}/stop`](#post-admin-api-clusters-id-stop) | Administrator | `changoctl shannonstore stop ID` |
| POST | [`/admin/api/clusters/{id}/restart`](#post-admin-api-clusters-id-restart) | Administrator | `changoctl shannonstore restart ID` |
| GET | [`/admin/api/clusters/{id}/metrics`](#get-admin-api-clusters-id-metrics) | Any signed-in user | `changoctl shannonstore metrics ID` |
| GET | [`/admin/api/clusters/{id}/config`](#get-admin-api-clusters-id-config) | Any signed-in user | `changoctl shannonstore config get ID` |
| POST | [`/admin/api/clusters/{id}/settings`](#post-admin-api-clusters-id-settings) | Administrator | `changoctl shannonstore config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/clusters/{id}/scale`](#post-admin-api-clusters-id-scale) | Administrator | `changoctl shannonstore scale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/clusters/{id}/nginx`](#get-admin-api-clusters-id-nginx) | Any signed-in user | `changoctl shannonstore nginx get ID` |
| POST | [`/admin/api/clusters/{id}/nginx`](#post-admin-api-clusters-id-nginx) | Administrator | `changoctl shannonstore nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/clusters/{id}/credentials`](#post-admin-api-clusters-id-credentials) | Administrator | `changoctl shannonstore credentials set ID [--admin-password V] [--admin-otok V]` |

## GET `/admin/api/clusters` { #get-admin-api-clusters }

- **Permission:** Any signed-in user
- **CLI:** `changoctl shannonstore list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/clusters" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/clusters/install-defaults` { #get-admin-api-clusters-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl shannonstore defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/clusters/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/clusters` { #post-admin-api-clusters }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `ShannonStoreClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (shannonstore-) when blank. |
| `version` | string | `"1.0.0"` |  |
| `packageFile` | string | `"shannonstore/shannonstore-1.0.0.tar.gz"` | Package path under the master's components dir. |
| `masterKey` | string |  | SHANNONSTORE_MASTER_KEY value — required, identical across the cluster. |
| `retiredKeyRef` | string |  | Reinstall with the retired key of a previously deleted cluster, named by that cluster's id. |
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance (count should be odd: 1, 3, 5, ...). |
| `apiNodes` | list |  | One NM nodeId per API Server instance. |
| `dataNodes` | list |  | One NM nodeId per Data Node instance. |
| `ecDataShards` | int | `4` | Erasure-coding data shards (k). |
| `ecParityShards` | int | `2` | Erasure-coding parity shards (m). |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `apiJvm` | object:JvmConfig |  | JVM tuning for the API server group (conf/jvm.conf). |
| `dataJvm` | object:JvmConfig |  | JVM tuning for the Data node group (conf/jvm.conf). |
| `properties` | map |  | Optional shannonstore.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the product's own logs; blank keeps the install-dir default. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.0.0", "packageFile": "shannonstore/shannonstore-1.0.0.tar.gz", "ecDataShards": 4, "ecParityShards": 2}'
```

## GET `/admin/api/clusters/{id}` { #get-admin-api-clusters-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl shannonstore get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/clusters/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/clusters/{id}` { #delete-admin-api-clusters-id }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/clusters/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/clusters/{id}/start` { #post-admin-api-clusters-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/clusters/{id}/stop` { #post-admin-api-clusters-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/clusters/{id}/restart` { #post-admin-api-clusters-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/clusters/{id}/metrics` { #get-admin-api-clusters-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl shannonstore metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/clusters/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/clusters/{id}/config` { #get-admin-api-clusters-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl shannonstore config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/clusters/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/clusters/{id}/settings` { #post-admin-api-clusters-id-settings }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `ShannonStoreSettingsRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | shannonstore.properties key=value edits applied to every API + Data node. |
| `apiJvm` | object:JvmConfig |  | JVM tuning for the API server group (conf/jvm.conf); null → unchanged. |
| `dataJvm` | object:JvmConfig |  | JVM tuning for the Data node group (conf/jvm.conf); null → unchanged. |
| `logDir` | string |  | Absolute directory the product writes its own logs under, or blank for the default (a logs directory inside each instance's install dir). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters/<id>/settings" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "apiJvm": "<value>"}'
```

## POST `/admin/api/clusters/{id}/scale` { #post-admin-api-clusters-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `ShannonStoreScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `apiNodes` | list |  | One NM nodeId per API Server instance to add. |
| `dataNodes` | list |  | One NM nodeId per Data Node instance to add. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "apiNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/clusters/{id}/nginx` { #get-admin-api-clusters-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl shannonstore nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/clusters/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/clusters/{id}/nginx` { #post-admin-api-clusters-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `ShannonStoreNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `8088` | TCP port nginx listens on for the proxied S3 API. |
| `apiInstanceIds` | list |  | API server instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 8088}'
```

## POST `/admin/api/clusters/{id}/credentials` { #post-admin-api-clusters-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl shannonstore credentials set ID [--admin-password V] [--admin-otok V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `adminPassword` | string |
| `adminOtok` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/clusters/<id>/credentials" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"adminPassword": "<value>", "adminOtok": "<value>"}'
```
