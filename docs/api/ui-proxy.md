# UI Proxy

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "ui-proxy-1",
  "componentType": "ui-proxy",
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
| GET | [`/admin/api/ui-proxy`](#get-admin-api-ui-proxy) | Any signed-in user | `changoctl ui-proxy list` |
| POST | [`/admin/api/ui-proxy`](#post-admin-api-ui-proxy) | Administrator | `changoctl ui-proxy install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/ui-proxy/{id}`](#get-admin-api-ui-proxy-id) | Any signed-in user | `changoctl ui-proxy get ID` |
| DELETE | [`/admin/api/ui-proxy/{id}`](#delete-admin-api-ui-proxy-id) | Administrator | `changoctl ui-proxy delete ID [--purge-data]` |
| POST | [`/admin/api/ui-proxy/{id}/start`](#post-admin-api-ui-proxy-id-start) | Administrator | `changoctl ui-proxy start ID` |
| POST | [`/admin/api/ui-proxy/{id}/stop`](#post-admin-api-ui-proxy-id-stop) | Administrator | `changoctl ui-proxy stop ID` |
| POST | [`/admin/api/ui-proxy/{id}/restart`](#post-admin-api-ui-proxy-id-restart) | Administrator | `changoctl ui-proxy restart ID` |
| GET | [`/admin/api/ui-proxy/{id}/metrics`](#get-admin-api-ui-proxy-id-metrics) | Any signed-in user | `changoctl ui-proxy metrics ID` |
| GET | [`/admin/api/ui-proxy/{id}/config`](#get-admin-api-ui-proxy-id-config) | Any signed-in user | `changoctl ui-proxy config get ID` |
| POST | [`/admin/api/ui-proxy/{id}/config`](#post-admin-api-ui-proxy-id-config) | Administrator | `changoctl ui-proxy config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/ui-proxy/{id}/scale`](#post-admin-api-ui-proxy-id-scale) | Administrator | `changoctl ui-proxy scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/ui-proxy/{id}/unscale`](#post-admin-api-ui-proxy-id-unscale) | Administrator | `changoctl ui-proxy unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/ui-proxy/{id}/nginx`](#get-admin-api-ui-proxy-id-nginx) | Any signed-in user | `changoctl ui-proxy nginx get ID` |
| POST | [`/admin/api/ui-proxy/{id}/nginx`](#post-admin-api-ui-proxy-id-nginx) | Administrator | `changoctl ui-proxy nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/ui-proxy/upstream-candidates`](#get-admin-api-ui-proxy-upstream-candidates) | Any signed-in user | `changoctl ui-proxy upstream-candidates` |

## GET `/admin/api/ui-proxy` { #get-admin-api-ui-proxy }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ui-proxy list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ui-proxy" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## POST `/admin/api/ui-proxy` { #post-admin-api-ui-proxy }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `UiProxyClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (ui-proxy-) when blank. |
| `version` | string |  | First-party component. |
| `packageFile` | string |  | Package path under the master's components dir. |
| `proxyNodes` | list |  | One NM nodeId per proxy instance. |
| `ontulUrl` | string |  | Ontul IAM base URL the proxy delegates login to. |
| `upstreams` | list |  | Upstream component UIs the proxy routes to — one host=url entry per target. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `logDir` | string |  | Absolute directory for the UI proxy's log (its console output). |
| `proxyJvm` | object:JvmConfig |  | Heap and extra flags for each proxy instance. |
| `properties` | map |  | Optional ui-proxy.properties overrides applied at install — the same key=value form the post-install Configure panel edits. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"installBaseDir": "/opt/components"}'
```

## GET `/admin/api/ui-proxy/{id}` { #get-admin-api-ui-proxy-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ui-proxy get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ui-proxy/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/ui-proxy/{id}` { #delete-admin-api-ui-proxy-id }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/ui-proxy/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ui-proxy/{id}/start` { #post-admin-api-ui-proxy-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/ui-proxy/{id}/stop` { #post-admin-api-ui-proxy-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/ui-proxy/{id}/restart` { #post-admin-api-ui-proxy-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/ui-proxy/{id}/metrics` { #get-admin-api-ui-proxy-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ui-proxy metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/ui-proxy/{id}/config` { #get-admin-api-ui-proxy-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ui-proxy config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ui-proxy/{id}/config` { #post-admin-api-ui-proxy-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `UiProxyConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | ui-proxy.properties key=value edits applied to every proxy instance. |
| `proxyJvm` | object:JvmConfig |  | JVM tuning for the proxy group (conf/jvm.conf); null/empty -> unchanged. |
| `logDir` | string |  | Absolute directory for the UI proxy's log (its console output). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "proxyJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/ui-proxy/{id}/scale` { #post-admin-api-ui-proxy-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `UiProxyScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `proxyNodes` | list |  | One NM nodeId per proxy instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/ui-proxy/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"proxyNodes": "<value>", "removeInstanceIds": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/ui-proxy/{id}/unscale` { #post-admin-api-ui-proxy-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `UiProxyScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `proxyNodes` | list |  | One NM nodeId per proxy instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/ui-proxy/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"proxyNodes": "<value>", "removeInstanceIds": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/ui-proxy/{id}/nginx` { #get-admin-api-ui-proxy-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ui-proxy nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/ui-proxy/{id}/nginx` { #post-admin-api-ui-proxy-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl ui-proxy nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `UiProxyNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `9190` | TCP port nginx listens on for the proxied proxy endpoint. |
| `proxyInstanceIds` | list |  | Proxy instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/ui-proxy/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 9190}'
```

## GET `/admin/api/ui-proxy/upstream-candidates` { #get-admin-api-ui-proxy-upstream-candidates }

- **Permission:** Any signed-in user
- **CLI:** `changoctl ui-proxy upstream-candidates`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/ui-proxy/upstream-candidates" -H "Authorization: Bearer $T"
```
