# Trino (query engine)

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "trino-1",
  "componentType": "trino",
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
| GET | [`/admin/api/trino`](#get-admin-api-trino) | Any signed-in user | `changoctl trino list` |
| GET | [`/admin/api/trino/install-defaults`](#get-admin-api-trino-install-defaults) | Any signed-in user | `changoctl trino defaults` |
| POST | [`/admin/api/trino`](#post-admin-api-trino) | Administrator | `changoctl trino install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/trino/{id}`](#get-admin-api-trino-id) | Any signed-in user | `changoctl trino get ID` |
| DELETE | [`/admin/api/trino/{id}`](#delete-admin-api-trino-id) | Administrator | `changoctl trino delete ID [--purge-data]` |
| POST | [`/admin/api/trino/{id}/start`](#post-admin-api-trino-id-start) | Administrator | `changoctl trino start ID` |
| POST | [`/admin/api/trino/{id}/stop`](#post-admin-api-trino-id-stop) | Administrator | `changoctl trino stop ID` |
| POST | [`/admin/api/trino/{id}/restart`](#post-admin-api-trino-id-restart) | Administrator | `changoctl trino restart ID` |
| GET | [`/admin/api/trino/{id}/metrics`](#get-admin-api-trino-id-metrics) | Any signed-in user | `changoctl trino metrics ID` |
| GET | [`/admin/api/trino/{id}/config`](#get-admin-api-trino-id-config) | Any signed-in user | `changoctl trino config get ID` |
| POST | [`/admin/api/trino/{id}/config`](#post-admin-api-trino-id-config) | Administrator | `changoctl trino config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/trino/{id}/scale`](#post-admin-api-trino-id-scale) | Administrator | `changoctl trino scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/trino/{id}/unscale`](#post-admin-api-trino-id-unscale) | Administrator | `changoctl trino unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/trino/{id}/truststore`](#get-admin-api-trino-id-truststore) | Any signed-in user | `changoctl trino truststore list ID` |
| POST | [`/admin/api/trino/{id}/truststore`](#post-admin-api-trino-id-truststore) | Administrator | `changoctl trino truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]` |
| DELETE | [`/admin/api/trino/{id}/truststore`](#delete-admin-api-trino-id-truststore) | Administrator | `changoctl trino truststore delete ID --name V` |
| GET | [`/admin/api/trino/{id}/catalogs`](#get-admin-api-trino-id-catalogs) | Any signed-in user | `changoctl trino catalogs ID` |
| POST | [`/admin/api/trino/{id}/catalog`](#post-admin-api-trino-id-catalog) | Administrator | `changoctl trino catalog add ID [NAME] [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/trino/{id}/catalog`](#post-admin-api-trino-id-catalog) | Administrator | `changoctl trino catalog update ID [NAME] [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/trino/{id}/catalog`](#post-admin-api-trino-id-catalog) | Administrator | `changoctl trino catalog delete ID [NAME] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/trino/{id}/resource-groups`](#get-admin-api-trino-id-resource-groups) | Any signed-in user | `changoctl trino resource-groups ID` |
| POST | [`/admin/api/trino/{id}/resource-group`](#post-admin-api-trino-id-resource-group) | Administrator | `changoctl trino resource-group ID [--FIELD VALUE ...] [-f body.json]` |

## GET `/admin/api/trino` { #get-admin-api-trino }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/trino/install-defaults` { #get-admin-api-trino-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino` { #post-admin-api-trino }

- **Permission:** Administrator
- **CLI:** `changoctl trino install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (trino-) when blank. |
| `version` | string | `"479"` |  |
| `packageFile` | string | `"trino/trino-server-479.tar.gz"` | Package path under the master's components dir. |
| `coordinatorNodes` | list |  | One NM nodeId per Coordinator instance (typically a single coordinator). |
| `workerNodes` | list |  | One NM nodeId per Worker instance. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `nodeEnvironment` | string | `"production"` | node.properties node.environment value — same across the whole cluster. |
| `queryMaxMemory` | string | `"4GB"` |  |
| `queryMaxMemoryPerNode` | string | `"1GB"` |  |
| `memoryHeapHeadroomPerNode` | string | `"1GB"` |  |
| `retryPolicy` | string | `"QUERY"` | Fault-tolerant retry policy — QUERY, TASK, or NONE. |
| `exchangeManagerEnabled` | bool | `false` |  |
| `exchangeBaseDirectory` | string | `""` |  |
| `exchangeS3Region` | string | `""` |  |
| `exchangeS3Endpoint` | string | `""` |  |
| `exchangeS3AccessKey` | string | `""` |  |
| `exchangeS3SecretKey` | string | `""` |  |
| `ontulAuthzEndpoint` | string | `""` | Ontul IAM endpoint for the chango-trino-authz plugin. |
| `ontulAuthzToken` | string | `""` | Long-lived ontul user-key token (OTOK prefix). |
| `resourceGroupEnabled` | bool | `true` | On by default, backed by PostgreSQL. |
| `resourceGroupPgInstanceId` | string | `""` | One of two paths — pick exactly one: chango-installed PG (recommended). |
| `resourceGroupPgHost` | string | `""` |  |
| `resourceGroupPgPort` | int | `5432` |  |
| `resourceGroupDbName` | string | `""` | Blank -> default resource_groups_. |
| `resourceGroupDbUser` | string | `"trino"` |  |
| `resourceGroupDbPassword` | string | `""` |  |
| `coordinatorJvm` | object:JvmConfig |  | Optional JVM tuning for the Coordinator role, seeded into every coordinator's etc/jvm.config at install time. |
| `workerJvm` | object:JvmConfig |  | Optional JVM tuning for the Worker role; same semantics as #coordinatorJvm. |
| `properties` | map |  | Optional config.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the query engine's server + launcher logs. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "479", "packageFile": "trino/trino-server-479.tar.gz", "installBaseDir": "/opt/components", "nodeEnvironment": "production"}'
```

## GET `/admin/api/trino/{id}` { #get-admin-api-trino-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/trino/{id}` { #delete-admin-api-trino-id }

- **Permission:** Administrator
- **CLI:** `changoctl trino delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/trino/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino/{id}/start` { #post-admin-api-trino-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl trino start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/trino/{id}/stop` { #post-admin-api-trino-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl trino stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/trino/{id}/restart` { #post-admin-api-trino-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl trino restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/trino/{id}/metrics` { #get-admin-api-trino-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/trino/{id}/config` { #get-admin-api-trino-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino/{id}/config` { #post-admin-api-trino-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl trino config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | config.properties key=value edits applied to every Coordinator + Worker. |
| `coordinatorJvm` | object:JvmConfig |  | JVM tuning for the Coordinator group (etc/jvm.config); null/empty → unchanged. |
| `workerJvm` | object:JvmConfig |  | JVM tuning for the Worker group (etc/jvm.config); null/empty → unchanged. |
| `exchangeManagerOp` | string |  |  |
| `exchangeBaseDirectory` | string |  |  |
| `exchangeS3Region` | string |  |  |
| `exchangeS3Endpoint` | string |  |  |
| `exchangeS3AccessKey` | string |  |  |
| `exchangeS3SecretKey` | string |  |  |
| `resourceGroupDbOp` | string |  |  |
| `resourceGroupPgInstanceId` | string |  | Optional — id of a chango-installed PostgreSQL instance. |
| `resourceGroupPgHost` | string |  |  |
| `resourceGroupPgPort` | int |  |  |
| `resourceGroupDbName` | string |  |  |
| `resourceGroupDbUser` | string |  |  |
| `resourceGroupDbPassword` | string |  |  |
| `ontulAuthzOp` | string |  |  |
| `ontulAuthzEndpoint` | string |  |  |
| `ontulAuthzToken` | string |  |  |
| `logDir` | string |  | Absolute directory for the query engine's server + launcher logs. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "coordinatorJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/trino/{id}/scale` { #post-admin-api-trino-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl trino scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/trino/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"workerNodes": "<value>", "removeInstanceIds": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/trino/{id}/unscale` { #post-admin-api-trino-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl trino unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/trino/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"workerNodes": "<value>", "removeInstanceIds": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/trino/{id}/truststore` { #get-admin-api-trino-id-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino truststore list ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino/<id>/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino/{id}/truststore` { #post-admin-api-trino-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl trino truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |
| `trustStorePassword` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>", "trustStorePassword": "<value>"}'
```

## DELETE `/admin/api/trino/{id}/truststore` { #delete-admin-api-trino-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl trino truststore delete ID --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/trino/<id>/truststore?name=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/trino/{id}/catalogs` { #get-admin-api-trino-id-catalogs }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino catalogs ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino/<id>/catalogs" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino/{id}/catalog` { #post-admin-api-trino-id-catalog }

- **Permission:** Administrator
- **CLI:** `changoctl trino catalog add ID [NAME] [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoCatalogRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `op` | string |  | Operation — one of add, update, delete. |
| `name` | string |  | Catalog name — alphanumeric/underscore; becomes etc/catalog/.properties. |
| `properties` | string |  | Full text body of the .properties file (newline-separated lines). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/catalog" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"op": "<value>", "name": "<value>"}'
```

## POST `/admin/api/trino/{id}/catalog` { #post-admin-api-trino-id-catalog }

- **Permission:** Administrator
- **CLI:** `changoctl trino catalog update ID [NAME] [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoCatalogRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `op` | string |  | Operation — one of add, update, delete. |
| `name` | string |  | Catalog name — alphanumeric/underscore; becomes etc/catalog/.properties. |
| `properties` | string |  | Full text body of the .properties file (newline-separated lines). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/catalog" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"op": "<value>", "name": "<value>"}'
```

## POST `/admin/api/trino/{id}/catalog` { #post-admin-api-trino-id-catalog }

- **Permission:** Administrator
- **CLI:** `changoctl trino catalog delete ID [NAME] [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoCatalogRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `op` | string |  | Operation — one of add, update, delete. |
| `name` | string |  | Catalog name — alphanumeric/underscore; becomes etc/catalog/.properties. |
| `properties` | string |  | Full text body of the .properties file (newline-separated lines). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/catalog" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"op": "<value>", "name": "<value>"}'
```

## GET `/admin/api/trino/{id}/resource-groups` { #get-admin-api-trino-id-resource-groups }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino resource-groups ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino/<id>/resource-groups" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino/{id}/resource-group` { #post-admin-api-trino-id-resource-group }

- **Permission:** Administrator
- **CLI:** `changoctl trino resource-group ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoResourceGroupRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `op` | string |  | Operation — one of add, update, delete, seed. |
| `name` | string |  | Resource group name (resource_groups.name). |
| `parent` | string |  | Parent group name — blank/null for a root group (parent). |
| `softMemoryLimit` | string | `"100%"` | Soft memory limit, e.g. 50% or 10GB (soft_memory_limit). |
| `maxQueued` | int | `1000` | Maximum queued queries (max_queued). |
| `softConcurrencyLimit` | int |  | Soft concurrency limit — null = unset (soft_concurrency_limit). |
| `hardConcurrencyLimit` | int | `100` | Maximum concurrently running queries (hard_concurrency_limit). |
| `schedulingPolicy` | string | `"fair"` | Scheduling policy — fair, weighted, weighted_fair, query_priority. |
| `schedulingWeight` | int |  | Scheduling weight (used by weighted/weighted_fair) — null = unset. |
| `jmxExport` | bool | `true` | Whether to expose this group's stats via JMX (jmx_export). |
| `softCpuLimit` | string |  | Soft CPU limit over the quota period, e.g. 1h — null/blank = unset. |
| `hardCpuLimit` | string |  | Hard CPU limit over the quota period, e.g. 1h — null/blank = unset. |
| `environment` | string | `"production"` | node.environment this group applies to (environment). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino/<id>/resource-group" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"softMemoryLimit": "100%", "maxQueued": 1000, "hardConcurrencyLimit": 100, "schedulingPolicy": "fair"}'
```
