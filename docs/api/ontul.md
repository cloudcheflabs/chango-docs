# Ontul (IAM engine)

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "ontul-1",
  "componentType": "ontul",
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
| GET | [`/admin/api/ontul`](#get-admin-api-ontul) | Any signed-in user | `changoctl ontul list` |
| GET | [`/admin/api/ontul/install-defaults`](#get-admin-api-ontul-install-defaults) | Any signed-in user | `changoctl ontul defaults` |
| POST | [`/admin/api/ontul`](#post-admin-api-ontul) | Administrator | `changoctl ontul install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/ontul/{id}`](#get-admin-api-ontul-id) | Any signed-in user | `changoctl ontul get ID` |
| DELETE | [`/admin/api/ontul/{id}`](#delete-admin-api-ontul-id) | Administrator | `changoctl ontul delete ID [--purge-data]` |
| POST | [`/admin/api/ontul/{id}/start`](#post-admin-api-ontul-id-start) | Administrator | `changoctl ontul start ID` |
| POST | [`/admin/api/ontul/{id}/stop`](#post-admin-api-ontul-id-stop) | Administrator | `changoctl ontul stop ID` |
| POST | [`/admin/api/ontul/{id}/restart`](#post-admin-api-ontul-id-restart) | Administrator | `changoctl ontul restart ID` |
| GET | [`/admin/api/ontul/{id}/metrics`](#get-admin-api-ontul-id-metrics) | Any signed-in user | `changoctl ontul metrics ID` |
| GET | [`/admin/api/ontul/{id}/config`](#get-admin-api-ontul-id-config) | Any signed-in user | `changoctl ontul config get ID` |
| POST | [`/admin/api/ontul/{id}/config`](#post-admin-api-ontul-id-config) | Administrator | `changoctl ontul config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/ontul/{id}/scale`](#post-admin-api-ontul-id-scale) | Administrator | `changoctl ontul scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/ontul/{id}/unscale`](#post-admin-api-ontul-id-unscale) | Administrator | `changoctl ontul unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/ontul/{id}/nginx`](#get-admin-api-ontul-id-nginx) | Any signed-in user | `changoctl ontul nginx get ID` |
| POST | [`/admin/api/ontul/{id}/nginx`](#post-admin-api-ontul-id-nginx) | Administrator | `changoctl ontul nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/ontul/{id}/truststore`](#get-admin-api-ontul-id-truststore) | Any signed-in user | `changoctl ontul truststore list ID` |
| POST | [`/admin/api/ontul/{id}/truststore`](#post-admin-api-ontul-id-truststore) | Administrator | `changoctl ontul truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]` |
| DELETE | [`/admin/api/ontul/{id}/truststore`](#delete-admin-api-ontul-id-truststore) | Administrator | `changoctl ontul truststore delete ID --name V` |
| POST | [`/admin/api/ontul/{id}/credentials`](#post-admin-api-ontul-id-credentials) | Administrator | `changoctl ontul credentials set ID [--admin-password V] [--admin-otok V]` |

## GET `/admin/api/ontul` { #get-admin-api-ontul }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ontul list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ontul" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/ontul/install-defaults` { #get-admin-api-ontul-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ontul defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ontul/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ontul` { #post-admin-api-ontul }

- **Permission:** Administrator
- **CLI:** `changoctl ontul install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `OntulClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (ontul-) when blank. |
| `version` | string | `"1.0.0"` |  |
| `packageFile` | string | `"ontul/ontul-1.0.0.tar.gz"` | Package path under the master's components dir. |
| `masterKey` | string |  | ONTUL_MASTER_KEY value — required, identical across the cluster, >= 32 chars. |
| `retiredKeyRef` | string |  | Reinstall with the retired key of a previously deleted cluster, named by that cluster's id. |
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance (count should be odd: 1, 3, 5, ...). |
| `masterNodes` | list |  | One NM nodeId per Master instance. |
| `workerNodes` | list |  | One NM nodeId per Worker instance. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `logDir` | string |  | Absolute directory for the product's own logs; blank keeps the install-dir default. |
| `masterJvm` | object:JvmConfig |  |  |
| `workerJvm` | object:JvmConfig |  | Optional JVM tuning for the Worker role; same semantics as #masterJvm. |
| `properties` | map |  | Optional ontul.properties overrides applied after install — same key=value form the post-install Configure panel edits. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.0.0", "packageFile": "ontul/ontul-1.0.0.tar.gz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/ontul/{id}` { #get-admin-api-ontul-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ontul get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ontul/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/ontul/{id}` { #delete-admin-api-ontul-id }

- **Permission:** Administrator
- **CLI:** `changoctl ontul delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/ontul/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ontul/{id}/start` { #post-admin-api-ontul-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl ontul start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/ontul/{id}/stop` { #post-admin-api-ontul-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl ontul stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/ontul/{id}/restart` { #post-admin-api-ontul-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl ontul restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/ontul/{id}/metrics` { #get-admin-api-ontul-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ontul metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ontul/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/ontul/{id}/config` { #get-admin-api-ontul-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ontul config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ontul/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ontul/{id}/config` { #post-admin-api-ontul-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl ontul config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `OntulConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | ontul.properties key=value edits applied to every Master + Worker node. |
| `confirmDataMoved` | string |  | Acknowledgement required to change an install-only path (a state-store directory). |
| `logDir` | string |  | Absolute directory the product writes its own logs under, or blank to keep the default (a logs directory inside each instance's install dir). |
| `masterJvm` | object:JvmConfig |  |  |
| `workerJvm` | object:JvmConfig |  | JVM tuning for the Worker group (conf/jvm.conf); null/empty → unchanged. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "confirmDataMoved": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/ontul/{id}/scale` { #post-admin-api-ontul-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl ontul scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `OntulScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/ontul/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "masterNodes": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/ontul/{id}/unscale` { #post-admin-api-ontul-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl ontul unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `OntulScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/ontul/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "masterNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/ontul/{id}/nginx` { #get-admin-api-ontul-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ontul nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ontul/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ontul/{id}/nginx` { #post-admin-api-ontul-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl ontul nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `OntulNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `18888` | TCP port nginx listens on for the proxied Master admin endpoint. |
| `masterInstanceIds` | list |  | Master instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 18888}'
```

## GET `/admin/api/ontul/{id}/truststore` { #get-admin-api-ontul-id-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ontul truststore list ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ontul/<id>/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ontul/{id}/truststore` { #post-admin-api-ontul-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl ontul truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |
| `trustStorePassword` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>", "trustStorePassword": "<value>"}'
```

## DELETE `/admin/api/ontul/{id}/truststore` { #delete-admin-api-ontul-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl ontul truststore delete ID --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/ontul/<id>/truststore?name=<value>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ontul/{id}/credentials` { #post-admin-api-ontul-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl ontul credentials set ID [--admin-password V] [--admin-otok V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `adminPassword` | string |
| `adminOtok` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ontul/<id>/credentials" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"adminPassword": "<value>", "adminOtok": "<value>"}'
```
