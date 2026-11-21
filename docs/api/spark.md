# Spark (+ Livy)

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "spark-1",
  "componentType": "spark",
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
| GET | [`/admin/api/spark`](#get-admin-api-spark) | Any signed-in user | `changoctl spark list` |
| GET | [`/admin/api/spark/install-defaults`](#get-admin-api-spark-install-defaults) | Any signed-in user | `changoctl spark defaults` |
| POST | [`/admin/api/spark`](#post-admin-api-spark) | Administrator | `changoctl spark install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/spark/{id}`](#get-admin-api-spark-id) | Any signed-in user | `changoctl spark get ID` |
| DELETE | [`/admin/api/spark/{id}`](#delete-admin-api-spark-id) | Administrator | `changoctl spark delete ID [--purge-data]` |
| POST | [`/admin/api/spark/{id}/start`](#post-admin-api-spark-id-start) | Administrator | `changoctl spark start ID` |
| POST | [`/admin/api/spark/{id}/stop`](#post-admin-api-spark-id-stop) | Administrator | `changoctl spark stop ID` |
| POST | [`/admin/api/spark/{id}/restart`](#post-admin-api-spark-id-restart) | Administrator | `changoctl spark restart ID` |
| GET | [`/admin/api/spark/{id}/metrics`](#get-admin-api-spark-id-metrics) | Any signed-in user | `changoctl spark metrics ID` |
| GET | [`/admin/api/spark/{id}/config`](#get-admin-api-spark-id-config) | Any signed-in user | `changoctl spark config get ID` |
| POST | [`/admin/api/spark/{id}/config`](#post-admin-api-spark-id-config) | Administrator | `changoctl spark config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/spark/{id}/scale`](#post-admin-api-spark-id-scale) | Administrator | `changoctl spark scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/spark/{id}/unscale`](#post-admin-api-spark-id-unscale) | Administrator | `changoctl spark unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/spark/{id}/truststore`](#get-admin-api-spark-id-truststore) | Any signed-in user | `changoctl spark truststore list ID` |
| POST | [`/admin/api/spark/{id}/truststore`](#post-admin-api-spark-id-truststore) | Administrator | `changoctl spark truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]` |
| DELETE | [`/admin/api/spark/{id}/truststore`](#delete-admin-api-spark-id-truststore) | Administrator | `changoctl spark truststore delete ID --name V` |

## GET `/admin/api/spark` { #get-admin-api-spark }

- **Permission:** Any signed-in user
- **CLI:** `changoctl spark list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/spark" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/spark/install-defaults` { #get-admin-api-spark-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl spark defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/spark/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/spark` { #post-admin-api-spark }

- **Permission:** Administrator
- **CLI:** `changoctl spark install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `SparkClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (spark-) when blank. |
| `version` | string | `"3.5.8"` |  |
| `packageFile` | string | `"spark/spark-3.5.8-bin-hadoop3.tgz"` | Package path under the master's components dir. |
| `masterNodes` | list |  | One NM nodeId per Master instance. |
| `workerNodes` | list |  | One NM nodeId per Worker instance. |
| `historyServerNodes` | list |  | Optional — one NM nodeId per History Server instance. |
| `livyNodes` | list |  | Optional — one NM nodeId per Livy server instance. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `ontulAuthzEndpoint` | string | `""` | Ontul IAM authorization endpoint (e.g. http://ontul-master:18080) used to configure the chango-spark-authz SparkSessionExtensions plugin in each instance's conf/spark-defaults.conf. |
| `ontulAuthzToken` | string | `""` | Service token the chango-spark-authz plugin authenticates to Ontul IAM with. |
| `eventLogEnabled` | bool | `false` | Spark job-log (history-server) storage on S3. |
| `eventLogDir` | string | `""` |  |
| `s3Endpoint` | string | `""` |  |
| `s3Region` | string | `"us-east-1"` |  |
| `s3AccessKey` | string | `""` |  |
| `s3SecretKey` | string | `""` |  |
| `s3PathStyleAccess` | bool | `true` |  |
| `livyOverrides` | map |  | Optional free-form livy.conf overrides applied at Livy install time. |
| `masterJvm` | object:JvmConfig |  | Optional JVM tuning for the standalone Master role. |
| `workerJvm` | object:JvmConfig |  | Optional JVM tuning for the Worker role; same semantics as #masterJvm. |
| `livyJvm` | object:JvmConfig |  | Optional JVM tuning for the Livy server role, seeded into the Livy instance's conf/jvm.conf. |
| `historyServerJvm` | object:JvmConfig |  | Optional JVM tuning for the History Server role, translated into SPARK_DAEMON_MEMORY + SPARK_HISTORY_OPTS the same way as the Master. |
| `properties` | map |  | Optional spark-defaults.conf overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the daemon logs AND the executor/job logs (SPARK_WORKER_DIR) — streaming jobs are the ones that fill a disk. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "3.5.8", "packageFile": "spark/spark-3.5.8-bin-hadoop3.tgz", "installBaseDir": "/opt/components", "eventLogEnabled": false}'
```

## GET `/admin/api/spark/{id}` { #get-admin-api-spark-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl spark get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/spark/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/spark/{id}` { #delete-admin-api-spark-id }

- **Permission:** Administrator
- **CLI:** `changoctl spark delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/spark/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/spark/{id}/start` { #post-admin-api-spark-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl spark start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/spark/{id}/stop` { #post-admin-api-spark-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl spark stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/spark/{id}/restart` { #post-admin-api-spark-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl spark restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/spark/{id}/metrics` { #get-admin-api-spark-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl spark metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/spark/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/spark/{id}/config` { #get-admin-api-spark-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl spark config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/spark/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/spark/{id}/config` { #post-admin-api-spark-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl spark config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `SparkConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | spark-defaults.conf key=value edits applied to every Master + Worker node. |
| `masterJvm` | object:JvmConfig |  | JVM tuning for the Master group (conf/jvm.conf); null/empty → unchanged. |
| `workerJvm` | object:JvmConfig |  | JVM tuning for the Worker group (conf/jvm.conf); null/empty → unchanged. |
| `historyServerJvm` | object:JvmConfig |  | JVM tuning for the History Server; null/empty → unchanged. |
| `livyJvm` | object:JvmConfig |  | JVM tuning for the Livy server; null/empty → unchanged. |
| `ontulAuthzOp` | string |  |  |
| `ontulAuthzEndpoint` | string |  |  |
| `ontulAuthzToken` | string |  |  |
| `s3Op` | string |  |  |
| `s3Endpoint` | string |  |  |
| `s3Region` | string |  |  |
| `s3AccessKey` | string |  |  |
| `s3SecretKey` | string |  |  |
| `s3PathStyleAccess` | bool |  |  |
| `eventLogOp` | string |  |  |
| `eventLogDir` | string |  |  |
| `livyOverrides` | map |  | Optional free-form livy.conf overrides. |
| `logDir` | string |  | Absolute directory for the daemon logs AND the executor/job logs (SPARK_WORKER_DIR) — streaming jobs are the ones that fill a disk. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "masterJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/spark/{id}/scale` { #post-admin-api-spark-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl spark scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `SparkScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `livyNodes` | list |  | Session servers (Livy) to add. |
| `removeInstanceIds` | list |  |  |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"masterNodes": "<value>", "workerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/spark/{id}/unscale` { #post-admin-api-spark-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl spark unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `SparkScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `livyNodes` | list |  | Session servers (Livy) to add. |
| `removeInstanceIds` | list |  |  |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"masterNodes": "<value>", "workerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/spark/{id}/truststore` { #get-admin-api-spark-id-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl spark truststore list ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/spark/<id>/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/spark/{id}/truststore` { #post-admin-api-spark-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl spark truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |
| `trustStorePassword` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/spark/<id>/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>", "trustStorePassword": "<value>"}'
```

## DELETE `/admin/api/spark/{id}/truststore` { #delete-admin-api-spark-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl spark truststore delete ID --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/spark/<id>/truststore?name=<value>" -H "Authorization: Bearer $T"
```
