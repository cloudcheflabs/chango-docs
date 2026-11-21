# Kiok (workflow)

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "kiok-1",
  "componentType": "kiok",
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
| GET | [`/admin/api/kiok`](#get-admin-api-kiok) | Any signed-in user | `changoctl kiok list` |
| GET | [`/admin/api/kiok/install-defaults`](#get-admin-api-kiok-install-defaults) | Any signed-in user | `changoctl kiok defaults` |
| POST | [`/admin/api/kiok`](#post-admin-api-kiok) | Administrator | `changoctl kiok install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/kiok/{id}`](#get-admin-api-kiok-id) | Any signed-in user | `changoctl kiok get ID` |
| DELETE | [`/admin/api/kiok/{id}`](#delete-admin-api-kiok-id) | Administrator | `changoctl kiok delete ID [--purge-data]` |
| POST | [`/admin/api/kiok/{id}/start`](#post-admin-api-kiok-id-start) | Administrator | `changoctl kiok start ID` |
| POST | [`/admin/api/kiok/{id}/stop`](#post-admin-api-kiok-id-stop) | Administrator | `changoctl kiok stop ID` |
| POST | [`/admin/api/kiok/{id}/restart`](#post-admin-api-kiok-id-restart) | Administrator | `changoctl kiok restart ID` |
| GET | [`/admin/api/kiok/{id}/metrics`](#get-admin-api-kiok-id-metrics) | Any signed-in user | `changoctl kiok metrics ID` |
| GET | [`/admin/api/kiok/{id}/config`](#get-admin-api-kiok-id-config) | Any signed-in user | `changoctl kiok config get ID` |
| POST | [`/admin/api/kiok/{id}/config`](#post-admin-api-kiok-id-config) | Administrator | `changoctl kiok config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/kiok/{id}/scale`](#post-admin-api-kiok-id-scale) | Administrator | `changoctl kiok scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/kiok/{id}/unscale`](#post-admin-api-kiok-id-unscale) | Administrator | `changoctl kiok unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/kiok/{id}/nginx`](#get-admin-api-kiok-id-nginx) | Any signed-in user | `changoctl kiok nginx get ID` |
| POST | [`/admin/api/kiok/{id}/nginx`](#post-admin-api-kiok-id-nginx) | Administrator | `changoctl kiok nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/kiok/{id}/truststore`](#get-admin-api-kiok-id-truststore) | Any signed-in user | `changoctl kiok truststore list ID` |
| POST | [`/admin/api/kiok/{id}/truststore`](#post-admin-api-kiok-id-truststore) | Administrator | `changoctl kiok truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]` |
| DELETE | [`/admin/api/kiok/{id}/truststore`](#delete-admin-api-kiok-id-truststore) | Administrator | `changoctl kiok truststore delete ID --name V` |
| POST | [`/admin/api/kiok/{id}/credentials`](#post-admin-api-kiok-id-credentials) | Administrator | `changoctl kiok credentials set ID [--admin-password V] [--admin-otok V]` |

## GET `/admin/api/kiok` { #get-admin-api-kiok }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kiok list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kiok" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/kiok/install-defaults` { #get-admin-api-kiok-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kiok defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kiok/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kiok` { #post-admin-api-kiok }

- **Permission:** Administrator
- **CLI:** `changoctl kiok install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `KiokClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (kiok-) when blank. |
| `version` | string | `"1.0.0"` |  |
| `packageFile` | string | `"kiok/kiok-1.0.0.tar.gz"` | Package path under the master's components dir. |
| `masterKey` | string |  | KIOK_MASTER_KEY value — required, identical across the cluster, >= 32 chars. |
| `retiredKeyRef` | string |  | Reinstall with the retired key of a previously deleted cluster, named by that cluster's id. |
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance (count should be odd: 1, 3, 5, ...). |
| `masterNodes` | list |  | One NM nodeId per Master instance. |
| `workerNodes` | list |  | One NM nodeId per Worker instance. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `masterJvm` | object:JvmConfig |  | Optional JVM tuning for the Master role, seeded into every master's conf/jvm.conf at install time. |
| `workerJvm` | object:JvmConfig |  | Optional JVM tuning for the Worker role; same semantics as #masterJvm. |
| `properties` | map |  | Optional kiok.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the product's own logs; blank keeps the install-dir default. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.0.0", "packageFile": "kiok/kiok-1.0.0.tar.gz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/kiok/{id}` { #get-admin-api-kiok-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kiok get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kiok/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/kiok/{id}` { #delete-admin-api-kiok-id }

- **Permission:** Administrator
- **CLI:** `changoctl kiok delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/kiok/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kiok/{id}/start` { #post-admin-api-kiok-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl kiok start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/kiok/{id}/stop` { #post-admin-api-kiok-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl kiok stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/kiok/{id}/restart` { #post-admin-api-kiok-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl kiok restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/kiok/{id}/metrics` { #get-admin-api-kiok-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kiok metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kiok/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kiok/{id}/config` { #get-admin-api-kiok-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kiok config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kiok/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kiok/{id}/config` { #post-admin-api-kiok-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl kiok config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KiokConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | kiok.properties key=value edits applied to every Master + Worker node. |
| `confirmDataMoved` | string |  | Acknowledgement required to change an install-only path (a state-store directory). |
| `masterJvm` | object:JvmConfig |  |  |
| `workerJvm` | object:JvmConfig |  | JVM tuning for the Worker group (conf/jvm.conf); null/empty → unchanged. |
| `logDir` | string |  | Absolute directory the product writes its own logs under, or blank for the default (a logs directory inside each instance's install dir). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "confirmDataMoved": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/kiok/{id}/scale` { #post-admin-api-kiok-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl kiok scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KiokScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/kiok/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "masterNodes": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/kiok/{id}/unscale` { #post-admin-api-kiok-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl kiok unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KiokScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/kiok/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "masterNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/kiok/{id}/nginx` { #get-admin-api-kiok-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kiok nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kiok/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kiok/{id}/nginx` { #post-admin-api-kiok-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl kiok nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KiokNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `18890` | TCP port nginx listens on for the proxied Master admin endpoint. |
| `masterInstanceIds` | list |  | Master instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 18890}'
```

## GET `/admin/api/kiok/{id}/truststore` { #get-admin-api-kiok-id-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kiok truststore list ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kiok/<id>/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kiok/{id}/truststore` { #post-admin-api-kiok-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl kiok truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |
| `trustStorePassword` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>", "trustStorePassword": "<value>"}'
```

## DELETE `/admin/api/kiok/{id}/truststore` { #delete-admin-api-kiok-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl kiok truststore delete ID --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/kiok/<id>/truststore?name=<value>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kiok/{id}/credentials` { #post-admin-api-kiok-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl kiok credentials set ID [--admin-password V] [--admin-otok V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `adminPassword` | string |
| `adminOtok` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kiok/<id>/credentials" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"adminPassword": "<value>", "adminOtok": "<value>"}'
```
