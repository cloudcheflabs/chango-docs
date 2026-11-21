# Mium

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "mium-1",
  "componentType": "mium",
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
| GET | [`/admin/api/mium`](#get-admin-api-mium) | Any signed-in user | `changoctl mium list` |
| GET | [`/admin/api/mium/install-defaults`](#get-admin-api-mium-install-defaults) | Any signed-in user | `changoctl mium defaults` |
| POST | [`/admin/api/mium`](#post-admin-api-mium) | Administrator | `changoctl mium install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/mium/{id}`](#get-admin-api-mium-id) | Any signed-in user | `changoctl mium get ID` |
| DELETE | [`/admin/api/mium/{id}`](#delete-admin-api-mium-id) | Administrator | `changoctl mium delete ID [--purge-data]` |
| POST | [`/admin/api/mium/{id}/start`](#post-admin-api-mium-id-start) | Administrator | `changoctl mium start ID` |
| POST | [`/admin/api/mium/{id}/stop`](#post-admin-api-mium-id-stop) | Administrator | `changoctl mium stop ID` |
| POST | [`/admin/api/mium/{id}/restart`](#post-admin-api-mium-id-restart) | Administrator | `changoctl mium restart ID` |
| GET | [`/admin/api/mium/{id}/metrics`](#get-admin-api-mium-id-metrics) | Any signed-in user | `changoctl mium metrics ID` |
| GET | [`/admin/api/mium/{id}/config`](#get-admin-api-mium-id-config) | Any signed-in user | `changoctl mium config get ID` |
| POST | [`/admin/api/mium/{id}/config`](#post-admin-api-mium-id-config) | Administrator | `changoctl mium config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/mium/{id}/scale`](#post-admin-api-mium-id-scale) | Administrator | `changoctl mium scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/mium/{id}/unscale`](#post-admin-api-mium-id-unscale) | Administrator | `changoctl mium unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/mium/{id}/nginx`](#get-admin-api-mium-id-nginx) | Any signed-in user | `changoctl mium nginx get ID` |
| POST | [`/admin/api/mium/{id}/nginx`](#post-admin-api-mium-id-nginx) | Administrator | `changoctl mium nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/mium/{id}/credentials`](#post-admin-api-mium-id-credentials) | Administrator | `changoctl mium credentials set ID [--admin-password V] [--admin-otok V]` |

## GET `/admin/api/mium` { #get-admin-api-mium }

- **Permission:** Any signed-in user
- **CLI:** `changoctl mium list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/mium" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/mium/install-defaults` { #get-admin-api-mium-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl mium defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/mium/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/mium` { #post-admin-api-mium }

- **Permission:** Administrator
- **CLI:** `changoctl mium install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `MiumClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (mium-) when blank. |
| `version` | string | `"1.0.0"` |  |
| `packageFile` | string | `"mium/mium-1.0.0.tar.gz"` | Package path under the master's components dir. |
| `masterKey` | string |  | MIUM_MASTER_KEY value — required, identical across the cluster, >= 32 chars. |
| `retiredKeyRef` | string |  | Reinstall with the retired key of a previously deleted cluster, named by that cluster's id. |
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance (count should be odd: 1, 3, 5, ...). |
| `masterNodes` | list |  | One NM nodeId per Master instance. |
| `workerNodes` | list |  | One NM nodeId per Worker instance. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `masterJvm` | object:JvmConfig |  | Optional JVM tuning for the Master role, seeded into every master's conf/jvm.conf at install time. |
| `workerJvm` | object:JvmConfig |  | Optional JVM tuning for the Worker role; same semantics as #masterJvm. |
| `properties` | map |  | Optional mium.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the product's own logs; blank keeps the install-dir default. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.0.0", "packageFile": "mium/mium-1.0.0.tar.gz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/mium/{id}` { #get-admin-api-mium-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl mium get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/mium/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/mium/{id}` { #delete-admin-api-mium-id }

- **Permission:** Administrator
- **CLI:** `changoctl mium delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/mium/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/mium/{id}/start` { #post-admin-api-mium-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl mium start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/mium/{id}/stop` { #post-admin-api-mium-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl mium stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/mium/{id}/restart` { #post-admin-api-mium-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl mium restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/mium/{id}/metrics` { #get-admin-api-mium-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl mium metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/mium/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/mium/{id}/config` { #get-admin-api-mium-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl mium config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/mium/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/mium/{id}/config` { #post-admin-api-mium-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl mium config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `MiumConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | mium.properties key=value edits applied to every Master + Worker node. |
| `masterJvm` | object:JvmConfig |  | JVM tuning for the Master group (conf/jvm.conf); null/empty → unchanged. |
| `workerJvm` | object:JvmConfig |  | JVM tuning for the Worker group (conf/jvm.conf); null/empty → unchanged. |
| `logDir` | string |  | Absolute directory the product writes its own logs under, or blank for the default (a logs directory inside each instance's install dir). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "masterJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/mium/{id}/scale` { #post-admin-api-mium-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl mium scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `MiumScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/mium/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "masterNodes": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/mium/{id}/unscale` { #post-admin-api-mium-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl mium unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `MiumScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `masterNodes` | list |  | One NM nodeId per Master instance to add. |
| `workerNodes` | list |  | One NM nodeId per Worker instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/mium/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "masterNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/mium/{id}/nginx` { #get-admin-api-mium-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl mium nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/mium/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/mium/{id}/nginx` { #post-admin-api-mium-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl mium nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `MiumNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `18890` | TCP port nginx listens on for the proxied Master admin endpoint. |
| `masterInstanceIds` | list |  | Master instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 18890}'
```

## POST `/admin/api/mium/{id}/credentials` { #post-admin-api-mium-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl mium credentials set ID [--admin-password V] [--admin-otok V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `adminPassword` | string |
| `adminOtok` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/mium/<id>/credentials" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"adminPassword": "<value>", "adminOtok": "<value>"}'
```
