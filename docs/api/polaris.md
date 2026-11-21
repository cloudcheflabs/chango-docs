# Polaris (catalog server)

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "polaris-1",
  "componentType": "polaris",
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

!!! note "Ontul authorization and catalog S3 keys"
    - `POST /admin/api/polaris/{id}/config` with `ontulAuthzOp` = `enable` | `update` | `disable` turns
      the Ontul authorization extension on or off. Blank `ontulAuthzEndpoint` / `ontulAuthzToken` keep the
      stored values, else use this platform's Ontul cluster; `ontulAuthzCatalogMap`
      (`lakehouse=iceberg,…`) maps Polaris catalog names to the catalog names IAM policies use — blank
      derives it from the query engine's catalogs. The servers restart one at a time. The extension
      itself is installed as a Polaris patch (`server/` directory).
    - Catalogs carry no S3 credentials; the servers use their own (`s3-credentials`). For catalogs
      created by an earlier version, `POST …/catalogs/{catalog}/remove-s3-keys` removes the keys from
      the catalog and from every table and view in it. Engines started before that keep the old
      defaults and copy the keys into tables they create until restarted — restart them and call it
      again.

| Method | Path | Permission | changoctl |
|---|---|---|---|
| GET | [`/admin/api/polaris`](#get-admin-api-polaris) | Any signed-in user | `changoctl polaris list` |
| GET | [`/admin/api/polaris/install-defaults`](#get-admin-api-polaris-install-defaults) | Any signed-in user | `changoctl polaris defaults` |
| POST | [`/admin/api/polaris`](#post-admin-api-polaris) | Administrator | `changoctl polaris install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/polaris/{id}`](#get-admin-api-polaris-id) | Any signed-in user | `changoctl polaris get ID` |
| DELETE | [`/admin/api/polaris/{id}`](#delete-admin-api-polaris-id) | Administrator | `changoctl polaris delete ID [--purge-data]` |
| POST | [`/admin/api/polaris/{id}/start`](#post-admin-api-polaris-id-start) | Administrator | `changoctl polaris start ID` |
| POST | [`/admin/api/polaris/{id}/stop`](#post-admin-api-polaris-id-stop) | Administrator | `changoctl polaris stop ID` |
| POST | [`/admin/api/polaris/{id}/restart`](#post-admin-api-polaris-id-restart) | Administrator | `changoctl polaris restart ID` |
| GET | [`/admin/api/polaris/{id}/metrics`](#get-admin-api-polaris-id-metrics) | Any signed-in user | `changoctl polaris metrics ID` |
| GET | [`/admin/api/polaris/{id}/config`](#get-admin-api-polaris-id-config) | Any signed-in user | `changoctl polaris config get ID` |
| POST | [`/admin/api/polaris/{id}/config`](#post-admin-api-polaris-id-config) | Administrator | `changoctl polaris config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/polaris/{id}/scale`](#post-admin-api-polaris-id-scale) | Administrator | `changoctl polaris scale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/polaris/{id}/nginx`](#get-admin-api-polaris-id-nginx) | Any signed-in user | `changoctl polaris nginx get ID` |
| POST | [`/admin/api/polaris/{id}/nginx`](#post-admin-api-polaris-id-nginx) | Administrator | `changoctl polaris nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/polaris/{id}/truststore`](#get-admin-api-polaris-id-truststore) | Any signed-in user | `changoctl polaris truststore list ID` |
| POST | [`/admin/api/polaris/{id}/truststore`](#post-admin-api-polaris-id-truststore) | Administrator | `changoctl polaris truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]` |
| DELETE | [`/admin/api/polaris/{id}/truststore`](#delete-admin-api-polaris-id-truststore) | Administrator | `changoctl polaris truststore delete ID --name V` |
| GET | [`/admin/api/polaris/{id}/catalogs`](#get-admin-api-polaris-id-catalogs) | Any signed-in user | `changoctl polaris catalogs ID` |
| POST | [`/admin/api/polaris/{id}/catalogs`](#post-admin-api-polaris-id-catalogs) | Administrator | `changoctl polaris catalog create ID [NAME] [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/polaris/{id}/catalogs/{catalog}/config`](#post-admin-api-polaris-id-catalogs-catalog-config) | Administrator | `changoctl polaris catalog update ID CATALOG -f body.json \| --set K=V` |
| PATCH | [`/admin/api/polaris/{id}/catalogs/{catalog}`](#patch-admin-api-polaris-id-catalogs-catalog) | Administrator | `changoctl polaris catalog patch ID CATALOG -f body.json \| --set K=V` |
| DELETE | [`/admin/api/polaris/{id}/catalogs/{catalog}`](#delete-admin-api-polaris-id-catalogs-catalog) | Administrator | `changoctl polaris catalog delete ID CATALOG` |
| POST | [`/admin/api/polaris/{id}/catalogs/{catalog}/remove-s3-keys`](#post-admin-api-polaris-id-catalogs-catalog-remove-s3-keys) | Administrator | `changoctl polaris catalog remove-s3-keys ID CATALOG` |
| GET | [`/admin/api/polaris/{id}/credentials`](#get-admin-api-polaris-id-credentials) | Administrator | `changoctl polaris credentials ID` |
| GET | [`/admin/api/polaris/{id}/rest-endpoint`](#get-admin-api-polaris-id-rest-endpoint) | Any signed-in user | `changoctl polaris rest-endpoint ID` |
| POST | [`/admin/api/polaris/{id}/s3-credentials`](#post-admin-api-polaris-id-s3-credentials) | Administrator | `changoctl polaris s3-credentials ID [--FIELD VALUE ...] [-f body.json]` |

## GET `/admin/api/polaris` { #get-admin-api-polaris }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/polaris/install-defaults` { #get-admin-api-polaris-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris` { #post-admin-api-polaris }

- **Permission:** Administrator
- **CLI:** `changoctl polaris install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `PolarisClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (polaris-) when blank. |
| `version` | string | `"1.4.1"` |  |
| `packageFile` | string | `"polaris/polaris-bin-1.4.1.tgz"` | Package path under the master's components dir. |
| `serverNodes` | list |  | One NM nodeId per Polaris server instance. |
| `pgInstanceId` | string | `""` | Optional — id of a chango-installed PostgreSQL instance. |
| `pgHost` | string |  | PostgreSQL metastore — the database must already exist. |
| `pgPort` | int | `5432` |  |
| `pgDatabase` | string | `"postgres"` |  |
| `pgUser` | string | `"postgres"` |  |
| `pgPassword` | string | `""` |  |
| `s3Endpoint` | string | `""` | S3 storage defaults — used for Iceberg catalog creation. |
| `s3AccessKey` | string | `""` |  |
| `s3SecretKey` | string | `""` |  |
| `s3Region` | string | `"us-east-1"` |  |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `serverJvm` | object:JvmConfig |  | Optional JVM tuning for the Polaris server role. |
| `properties` | map |  | Optional Polaris -D system-property overrides applied after install — Polaris does not have a properties file; everything is delivered through POLARIS_JAVA_OPTS, so properties entries render as -Dkey=value on every serv… |
| `logDir` | string |  | Absolute directory for the catalog server's log. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.4.1", "packageFile": "polaris/polaris-bin-1.4.1.tgz", "pgPort": 5432, "pgDatabase": "postgres"}'
```

## GET `/admin/api/polaris/{id}` { #get-admin-api-polaris-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/polaris/{id}` { #delete-admin-api-polaris-id }

- **Permission:** Administrator
- **CLI:** `changoctl polaris delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/polaris/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris/{id}/start` { #post-admin-api-polaris-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl polaris start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/polaris/{id}/stop` { #post-admin-api-polaris-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl polaris stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/polaris/{id}/restart` { #post-admin-api-polaris-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl polaris restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/polaris/{id}/metrics` { #get-admin-api-polaris-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/polaris/{id}/config` { #get-admin-api-polaris-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris/{id}/config` { #post-admin-api-polaris-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl polaris config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `PolarisConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `extraOpts` | map |  |  |
| `logDir` | string |  | Absolute directory for the catalog server's log. |
| `serverJvm` | object:JvmConfig |  | Heap / extra JVM flags for the server role, changeable after install. |
| `ontulAuthzOp` | string |  | Ontul authorization extension — applied only when set: enable, update (rotate endpoint/token) or disable. |
| `ontulAuthzEndpoint` | string |  |  |
| `ontulAuthzToken` | string |  |  |
| `ontulAuthzCatalogMap` | string |  | Polaris catalog → catalog name used in IAM policies, lakehouse=iceberg,…. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"extraOpts": "<value>", "logDir": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/polaris/{id}/scale` { #post-admin-api-polaris-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl polaris scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `PolarisScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `addServerNodes` | list |  | NM nodeIds to add a new Polaris server on (one entry per server). |
| `removeInstanceIds` | list |  | Instance ids of Polaris servers to remove. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"addServerNodes": "<value>", "removeInstanceIds": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/polaris/{id}/nginx` { #get-admin-api-polaris-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris/{id}/nginx` { #post-admin-api-polaris-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl polaris nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `PolarisNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `8190` | TCP port nginx listens on. |
| `serverInstanceIds` | list |  | Polaris server instance ids to place behind the proxy. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 8190}'
```

## GET `/admin/api/polaris/{id}/truststore` { #get-admin-api-polaris-id-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris truststore list ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris/{id}/truststore` { #post-admin-api-polaris-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl polaris truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |
| `trustStorePassword` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>", "trustStorePassword": "<value>"}'
```

## DELETE `/admin/api/polaris/{id}/truststore` { #delete-admin-api-polaris-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl polaris truststore delete ID --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/polaris/<id>/truststore?name=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/polaris/{id}/catalogs` { #get-admin-api-polaris-id-catalogs }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris catalogs ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>/catalogs" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris/{id}/catalogs` { #post-admin-api-polaris-id-catalogs }

- **Permission:** Administrator
- **CLI:** `changoctl polaris catalog create ID [NAME] [--FIELD VALUE ...] [-f body.json]`

**Body:** `PolarisCatalogRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string |  | Catalog name. |
| `s3Bucket` | string | `""` | S3 bucket holding the catalog warehouse. |
| `s3AccessKey` | string | `""` | Accepted only when it is the server's own key (then ignored); anything else is refused. |
| `s3SecretKey` | string | `""` | Accepted only when it is the server's own secret (then ignored); anything else is refused. |
| `s3Region` | string | `""` | S3 region (most S3-compatible stores ignore it, but the AWS SDK needs one). |
| `s3Endpoint` | string | `""` | S3 endpoint URL, e.g. http://host:8080. |
| `s3PathStyleAccess` | bool | `true` | S3 path-style access (true for ShannonStore / MinIO / most S3-compatible stores). |
| `defaultBaseLocation` | string | `""` | Optional explicit base location. |
| `tableFormatVersion` | string | `"2"` | Iceberg table format version this catalog hands to clients that do not ask for one — written as table-default.format-version. |
| `dropWithPurge` | bool | `true` | Whether DROP TABLE may delete the table's data files — written as the catalog property polaris.config.drop-with-purge.enabled. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/catalogs" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"s3PathStyleAccess": true, "tableFormatVersion": "2", "dropWithPurge": true}'
```

## POST `/admin/api/polaris/{id}/catalogs/{catalog}/config` { #post-admin-api-polaris-id-catalogs-catalog-config }

- **Permission:** Administrator
- **CLI:** `changoctl polaris catalog update ID CATALOG -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/catalogs/<catalog>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## PATCH `/admin/api/polaris/{id}/catalogs/{catalog}` { #patch-admin-api-polaris-id-catalogs-catalog }

- **Permission:** Administrator
- **CLI:** `changoctl polaris catalog patch ID CATALOG -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X PATCH "https://node-1.example.com:8080/admin/api/polaris/<id>/catalogs/<catalog>" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## DELETE `/admin/api/polaris/{id}/catalogs/{catalog}` { #delete-admin-api-polaris-id-catalogs-catalog }

- **Permission:** Administrator
- **CLI:** `changoctl polaris catalog delete ID CATALOG`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/polaris/<id>/catalogs/<catalog>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris/{id}/catalogs/{catalog}/remove-s3-keys` { #post-admin-api-polaris-id-catalogs-catalog-remove-s3-keys }

- **Permission:** Administrator
- **CLI:** `changoctl polaris catalog remove-s3-keys ID CATALOG`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/catalogs/<catalog>/remove-s3-keys" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## GET `/admin/api/polaris/{id}/credentials` { #get-admin-api-polaris-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl polaris credentials ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>/credentials" -H "Authorization: Bearer $T"
```

## GET `/admin/api/polaris/{id}/rest-endpoint` { #get-admin-api-polaris-id-rest-endpoint }

- **Permission:** Any signed-in user
- **CLI:** `changoctl polaris rest-endpoint ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/polaris/<id>/rest-endpoint" -H "Authorization: Bearer $T"
```

## POST `/admin/api/polaris/{id}/s3-credentials` { #post-admin-api-polaris-id-s3-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl polaris s3-credentials ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `PolarisS3CredentialsRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `s3AccessKey` | string | `""` |  |
| `s3SecretKey` | string | `""` |  |
| `s3Region` | string | `""` |  |
| `s3Endpoint` | string | `""` |  |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/polaris/<id>/s3-credentials" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"s3AccessKey": "<value>", "s3SecretKey": "<value>"}'
```
