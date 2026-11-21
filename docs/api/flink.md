# Flink

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "flink-1",
  "componentType": "flink",
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
| GET | [`/admin/api/flink`](#get-admin-api-flink) | Any signed-in user | `changoctl flink list` |
| GET | [`/admin/api/flink/install-defaults`](#get-admin-api-flink-install-defaults) | Any signed-in user | `changoctl flink defaults` |
| POST | [`/admin/api/flink`](#post-admin-api-flink) | Administrator | `changoctl flink install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/flink/{id}`](#get-admin-api-flink-id) | Any signed-in user | `changoctl flink get ID` |
| DELETE | [`/admin/api/flink/{id}`](#delete-admin-api-flink-id) | Administrator | `changoctl flink delete ID [--purge-data]` |
| POST | [`/admin/api/flink/{id}/start`](#post-admin-api-flink-id-start) | Administrator | `changoctl flink start ID` |
| POST | [`/admin/api/flink/{id}/stop`](#post-admin-api-flink-id-stop) | Administrator | `changoctl flink stop ID` |
| POST | [`/admin/api/flink/{id}/restart`](#post-admin-api-flink-id-restart) | Administrator | `changoctl flink restart ID` |
| GET | [`/admin/api/flink/{id}/metrics`](#get-admin-api-flink-id-metrics) | Any signed-in user | `changoctl flink metrics ID` |
| GET | [`/admin/api/flink/{id}/config`](#get-admin-api-flink-id-config) | Any signed-in user | `changoctl flink config get ID` |
| POST | [`/admin/api/flink/{id}/config`](#post-admin-api-flink-id-config) | Administrator | `changoctl flink config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/flink/{id}/scale`](#post-admin-api-flink-id-scale) | Administrator | `changoctl flink scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/flink/{id}/unscale`](#post-admin-api-flink-id-unscale) | Administrator | `changoctl flink unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/flink/{id}/truststore`](#get-admin-api-flink-id-truststore) | Any signed-in user | `changoctl flink truststore list ID` |
| POST | [`/admin/api/flink/{id}/truststore`](#post-admin-api-flink-id-truststore) | Administrator | `changoctl flink truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]` |
| DELETE | [`/admin/api/flink/{id}/truststore`](#delete-admin-api-flink-id-truststore) | Administrator | `changoctl flink truststore delete ID --name V` |

## GET `/admin/api/flink` { #get-admin-api-flink }

- **Permission:** Any signed-in user
- **CLI:** `changoctl flink list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/flink" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/flink/install-defaults` { #get-admin-api-flink-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl flink defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/flink/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/flink` { #post-admin-api-flink }

- **Permission:** Administrator
- **CLI:** `changoctl flink install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `FlinkClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (flink-) when blank. |
| `version` | string | `"1.19.3"` |  |
| `packageFile` | string | `"flink/flink-1.19.3-bin-scala_2.12.tgz"` | Package path under the master's components dir. |
| `jobmanagerNodes` | list |  | One NM nodeId per JobManager instance (the first is the cluster's primary). |
| `taskmanagerNodes` | list |  | One NM nodeId per TaskManager instance. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `ontulAuthzEndpoint` | string |  | Ontul IAM authorization endpoint for the chango-flink-authz plugin (e.g. http://ontul-master:18080). |
| `ontulAuthzToken` | string |  | Long-lived ontul credential the chango-flink-authz plugin uses to call ontul's authz API (sent as Authorization: Token ). |
| `jobmanagerJvm` | object:JvmConfig |  | Optional JVM tuning for the JobManager role. |
| `taskmanagerJvm` | object:JvmConfig |  | Optional JVM tuning for the TaskManager role; same semantics as #jobmanagerJvm. |
| `properties` | map |  | Optional config.yaml key=value overrides applied after install — same flattened key form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for JobManager + TaskManager logs. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.19.3", "packageFile": "flink/flink-1.19.3-bin-scala_2.12.tgz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/flink/{id}` { #get-admin-api-flink-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl flink get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/flink/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/flink/{id}` { #delete-admin-api-flink-id }

- **Permission:** Administrator
- **CLI:** `changoctl flink delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/flink/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/flink/{id}/start` { #post-admin-api-flink-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl flink start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/flink/{id}/stop` { #post-admin-api-flink-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl flink stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/flink/{id}/restart` { #post-admin-api-flink-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl flink restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/flink/{id}/metrics` { #get-admin-api-flink-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl flink metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/flink/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/flink/{id}/config` { #get-admin-api-flink-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl flink config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/flink/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/flink/{id}/config` { #post-admin-api-flink-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl flink config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `FlinkConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | config.yaml key=value edits applied to every JobManager + TaskManager node. |
| `jobmanagerJvm` | object:JvmConfig |  | JVM tuning for the JobManager group (conf/jvm.conf); null/empty → unchanged. |
| `taskmanagerJvm` | object:JvmConfig |  | JVM tuning for the TaskManager group (conf/jvm.conf); null/empty → unchanged. |
| `ontulAuthzOp` | string |  |  |
| `ontulAuthzEndpoint` | string |  |  |
| `ontulAuthzToken` | string |  |  |
| `logDir` | string |  | Absolute directory for JobManager + TaskManager logs. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "jobmanagerJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/flink/{id}/scale` { #post-admin-api-flink-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl flink scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `FlinkScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `jobmanagerNodes` | list |  | One NM nodeId per JobManager instance to add. |
| `taskmanagerNodes` | list |  | One NM nodeId per TaskManager instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/flink/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"jobmanagerNodes": "<value>", "taskmanagerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/flink/{id}/unscale` { #post-admin-api-flink-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl flink unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `FlinkScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `jobmanagerNodes` | list |  | One NM nodeId per JobManager instance to add. |
| `taskmanagerNodes` | list |  | One NM nodeId per TaskManager instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/flink/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"jobmanagerNodes": "<value>", "taskmanagerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/flink/{id}/truststore` { #get-admin-api-flink-id-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl flink truststore list ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/flink/<id>/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/flink/{id}/truststore` { #post-admin-api-flink-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl flink truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |
| `trustStorePassword` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/flink/<id>/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>", "trustStorePassword": "<value>"}'
```

## DELETE `/admin/api/flink/{id}/truststore` { #delete-admin-api-flink-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl flink truststore delete ID --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/flink/<id>/truststore?name=<value>" -H "Authorization: Bearer $T"
```
