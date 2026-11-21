# Trino Gateway

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "trino-gateway-1",
  "componentType": "trino-gateway",
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
| GET | [`/admin/api/gateway/clusters`](#get-admin-api-gateway-clusters) | Any signed-in user | `changoctl gateway clusters list` |
| POST | [`/admin/api/gateway/clusters`](#post-admin-api-gateway-clusters) | Administrator | `changoctl gateway clusters put -f body.json \| --set K=V` |
| DELETE | [`/admin/api/gateway/clusters/{name}`](#delete-admin-api-gateway-clusters-name) | Administrator | `changoctl gateway clusters delete NAME` |
| GET | [`/admin/api/gateway/cluster-groups`](#get-admin-api-gateway-cluster-groups) | Any signed-in user | `changoctl gateway cluster-groups list` |
| POST | [`/admin/api/gateway/cluster-groups`](#post-admin-api-gateway-cluster-groups) | Administrator | `changoctl gateway cluster-groups put -f body.json \| --set K=V` |
| DELETE | [`/admin/api/gateway/cluster-groups/{name}`](#delete-admin-api-gateway-cluster-groups-name) | Administrator | `changoctl gateway cluster-groups delete NAME` |
| GET | [`/admin/api/gateway/resource-groups`](#get-admin-api-gateway-resource-groups) | Any signed-in user | `changoctl gateway resource-groups list` |
| POST | [`/admin/api/gateway/resource-groups`](#post-admin-api-gateway-resource-groups) | Administrator | `changoctl gateway resource-groups put -f body.json \| --set K=V` |
| DELETE | [`/admin/api/gateway/resource-groups/{name}`](#delete-admin-api-gateway-resource-groups-name) | Administrator | `changoctl gateway resource-groups delete NAME` |
| GET | [`/admin/api/gateway/user-groups`](#get-admin-api-gateway-user-groups) | Any signed-in user | `changoctl gateway user-groups list` |
| POST | [`/admin/api/gateway/user-groups`](#post-admin-api-gateway-user-groups) | Administrator | `changoctl gateway user-groups put -f body.json \| --set K=V` |
| DELETE | [`/admin/api/gateway/user-groups/{user}`](#delete-admin-api-gateway-user-groups-user) | Administrator | `changoctl gateway user-groups delete USER` |
| GET | [`/admin/api/trino-gateway`](#get-admin-api-trino-gateway) | Any signed-in user | `changoctl trino-gateway list` |
| GET | [`/admin/api/trino-gateway/install-defaults`](#get-admin-api-trino-gateway-install-defaults) | Any signed-in user | `changoctl trino-gateway defaults` |
| POST | [`/admin/api/trino-gateway`](#post-admin-api-trino-gateway) | Administrator | `changoctl trino-gateway install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/trino-gateway/{id}`](#get-admin-api-trino-gateway-id) | Any signed-in user | `changoctl trino-gateway get ID` |
| DELETE | [`/admin/api/trino-gateway/{id}`](#delete-admin-api-trino-gateway-id) | Administrator | `changoctl trino-gateway delete ID [--purge-data]` |
| POST | [`/admin/api/trino-gateway/{id}/start`](#post-admin-api-trino-gateway-id-start) | Administrator | `changoctl trino-gateway start ID` |
| POST | [`/admin/api/trino-gateway/{id}/stop`](#post-admin-api-trino-gateway-id-stop) | Administrator | `changoctl trino-gateway stop ID` |
| POST | [`/admin/api/trino-gateway/{id}/restart`](#post-admin-api-trino-gateway-id-restart) | Administrator | `changoctl trino-gateway restart ID` |
| GET | [`/admin/api/trino-gateway/{id}/metrics`](#get-admin-api-trino-gateway-id-metrics) | Any signed-in user | `changoctl trino-gateway metrics ID` |
| GET | [`/admin/api/trino-gateway/{id}/config`](#get-admin-api-trino-gateway-id-config) | Any signed-in user | `changoctl trino-gateway config get ID` |
| POST | [`/admin/api/trino-gateway/{id}/config`](#post-admin-api-trino-gateway-id-config) | Administrator | `changoctl trino-gateway config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/trino-gateway/{id}/scale`](#post-admin-api-trino-gateway-id-scale) | Administrator | `changoctl trino-gateway scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/trino-gateway/{id}/unscale`](#post-admin-api-trino-gateway-id-unscale) | Administrator | `changoctl trino-gateway unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/trino-gateway/{id}/nginx`](#get-admin-api-trino-gateway-id-nginx) | Any signed-in user | `changoctl trino-gateway nginx get ID` |
| POST | [`/admin/api/trino-gateway/{id}/nginx`](#post-admin-api-trino-gateway-id-nginx) | Administrator | `changoctl trino-gateway nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/trino-gateway/{id}/truststore`](#get-admin-api-trino-gateway-id-truststore) | Any signed-in user | `changoctl trino-gateway truststore list ID` |
| POST | [`/admin/api/trino-gateway/{id}/truststore`](#post-admin-api-trino-gateway-id-truststore) | Administrator | `changoctl trino-gateway truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]` |
| DELETE | [`/admin/api/trino-gateway/{id}/truststore`](#delete-admin-api-trino-gateway-id-truststore) | Administrator | `changoctl trino-gateway truststore delete ID --name V` |
| GET | [`/admin/api/trino-gateway/{id}/nginx/certificate`](#get-admin-api-trino-gateway-id-nginx-certificate) | Any signed-in user | `changoctl trino-gateway certificate get ID [-O FILE]` |
| GET | [`/admin/api/trino-gateway/{id}/nginx/certificate/info`](#get-admin-api-trino-gateway-id-nginx-certificate-info) | Any signed-in user | `changoctl trino-gateway certificate info ID` |
| POST | [`/admin/api/trino-gateway/{id}/nginx/certificate`](#post-admin-api-trino-gateway-id-nginx-certificate) | Administrator | `changoctl trino-gateway certificate set ID --cert V --key V [--chain V] [--allow-expired]` |
| GET | [`/admin/api/trino-gateway/{id}/attached-groups`](#get-admin-api-trino-gateway-id-attached-groups) | Any signed-in user | `changoctl trino-gateway attached-groups get ID` |
| POST | [`/admin/api/trino-gateway/{id}/attached-groups`](#post-admin-api-trino-gateway-id-attached-groups) | Administrator | `changoctl trino-gateway attached-groups set ID [--group A,B]` |

## GET `/admin/api/gateway/clusters` { #get-admin-api-gateway-clusters }

- **Permission:** Any signed-in user
- **CLI:** `changoctl gateway clusters list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/gateway/clusters" -H "Authorization: Bearer $T"
```

## POST `/admin/api/gateway/clusters` { #post-admin-api-gateway-clusters }

- **Permission:** Administrator
- **CLI:** `changoctl gateway clusters put -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/gateway/clusters" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## DELETE `/admin/api/gateway/clusters/{name}` { #delete-admin-api-gateway-clusters-name }

- **Permission:** Administrator
- **CLI:** `changoctl gateway clusters delete NAME`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/gateway/clusters/<name>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/gateway/cluster-groups` { #get-admin-api-gateway-cluster-groups }

- **Permission:** Any signed-in user
- **CLI:** `changoctl gateway cluster-groups list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/gateway/cluster-groups" -H "Authorization: Bearer $T"
```

## POST `/admin/api/gateway/cluster-groups` { #post-admin-api-gateway-cluster-groups }

- **Permission:** Administrator
- **CLI:** `changoctl gateway cluster-groups put -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/gateway/cluster-groups" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## DELETE `/admin/api/gateway/cluster-groups/{name}` { #delete-admin-api-gateway-cluster-groups-name }

- **Permission:** Administrator
- **CLI:** `changoctl gateway cluster-groups delete NAME`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/gateway/cluster-groups/<name>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/gateway/resource-groups` { #get-admin-api-gateway-resource-groups }

- **Permission:** Any signed-in user
- **CLI:** `changoctl gateway resource-groups list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/gateway/resource-groups" -H "Authorization: Bearer $T"
```

## POST `/admin/api/gateway/resource-groups` { #post-admin-api-gateway-resource-groups }

- **Permission:** Administrator
- **CLI:** `changoctl gateway resource-groups put -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/gateway/resource-groups" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## DELETE `/admin/api/gateway/resource-groups/{name}` { #delete-admin-api-gateway-resource-groups-name }

- **Permission:** Administrator
- **CLI:** `changoctl gateway resource-groups delete NAME`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/gateway/resource-groups/<name>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/gateway/user-groups` { #get-admin-api-gateway-user-groups }

- **Permission:** Any signed-in user
- **CLI:** `changoctl gateway user-groups list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/gateway/user-groups" -H "Authorization: Bearer $T"
```

## POST `/admin/api/gateway/user-groups` { #post-admin-api-gateway-user-groups }

- **Permission:** Administrator
- **CLI:** `changoctl gateway user-groups put -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/gateway/user-groups" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## DELETE `/admin/api/gateway/user-groups/{user}` { #delete-admin-api-gateway-user-groups-user }

- **Permission:** Administrator
- **CLI:** `changoctl gateway user-groups delete USER`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/gateway/user-groups/<user>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/trino-gateway` { #get-admin-api-trino-gateway }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/trino-gateway/install-defaults` { #get-admin-api-trino-gateway-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino-gateway` { #post-admin-api-trino-gateway }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoGatewayClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (trino-gateway-) when blank. |
| `version` | string |  | First-party component. |
| `packageFile` | string |  | Package path under the master's components dir. |
| `gatewayNodes` | list |  | One NM nodeId per gateway instance. |
| `gatewayJvm` | object:JvmConfig |  | Optional JVM tuning seeded into every gateway instance's conf/jvm.conf at install time. |
| `ontulAuthzToken` | string | `""` | Long-lived Ontul OTOK that the gateway uses for its own service-principal authz call (the Token header on /v1/api/authz/check-batch). |
| `attachedClusterGroups` | string | `""` | Comma-separated cluster-group names that this gateway cluster is allowed to route. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `properties` | map |  | Optional trino-gateway.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the query gateway's log (its console output). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"installBaseDir": "/opt/components"}'
```

## GET `/admin/api/trino-gateway/{id}` { #get-admin-api-trino-gateway-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/trino-gateway/{id}` { #delete-admin-api-trino-gateway-id }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/trino-gateway/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino-gateway/{id}/start` { #post-admin-api-trino-gateway-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/trino-gateway/{id}/stop` { #post-admin-api-trino-gateway-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/trino-gateway/{id}/restart` { #post-admin-api-trino-gateway-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/trino-gateway/{id}/metrics` { #get-admin-api-trino-gateway-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/trino-gateway/{id}/config` { #get-admin-api-trino-gateway-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino-gateway/{id}/config` { #post-admin-api-trino-gateway-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoGatewayConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | trino-gateway.properties key=value edits applied to every gateway instance. |
| `gatewayJvm` | object:JvmConfig |  | JVM tuning for the gateway group (conf/jvm.conf); null/empty → unchanged. |
| `logDir` | string |  | Absolute directory for the query gateway's log (its console output). |
| `ontulAuthzToken` | string |  | Service token for the gateway's own authz call (Token on /v1/api/authz/check-batch). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "gatewayJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/trino-gateway/{id}/scale` { #post-admin-api-trino-gateway-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoGatewayScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `gatewayNodes` | list |  | One NM nodeId per gateway instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/trino-gateway/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"gatewayNodes": "<value>", "removeInstanceIds": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/trino-gateway/{id}/unscale` { #post-admin-api-trino-gateway-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoGatewayScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `gatewayNodes` | list |  | One NM nodeId per gateway instance to add. |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/trino-gateway/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"gatewayNodes": "<value>", "removeInstanceIds": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/trino-gateway/{id}/nginx` { #get-admin-api-trino-gateway-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino-gateway/{id}/nginx` { #post-admin-api-trino-gateway-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `TrinoGatewayNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `0` | TCP port nginx listens on for the proxied gateway endpoint. |
| `gatewayInstanceIds` | list |  | Gateway instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 0}'
```

## GET `/admin/api/trino-gateway/{id}/truststore` { #get-admin-api-trino-gateway-id-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway truststore list ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino-gateway/{id}/truststore` { #post-admin-api-trino-gateway-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway truststore add ID [--cert V] [--name V] [--from-gateway V] [--trust-store-password V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |
| `trustStorePassword` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>", "trustStorePassword": "<value>"}'
```

## DELETE `/admin/api/trino-gateway/{id}/truststore` { #delete-admin-api-trino-gateway-id-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway truststore delete ID --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/truststore?name=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/trino-gateway/{id}/nginx/certificate` { #get-admin-api-trino-gateway-id-nginx-certificate }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway certificate get ID [-O FILE]`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/nginx/certificate" -H "Authorization: Bearer $T"
```

## GET `/admin/api/trino-gateway/{id}/nginx/certificate/info` { #get-admin-api-trino-gateway-id-nginx-certificate-info }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway certificate info ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/nginx/certificate/info" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino-gateway/{id}/nginx/certificate` { #post-admin-api-trino-gateway-id-nginx-certificate }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway certificate set ID --cert V --key V [--chain V] [--allow-expired]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `key` | string |
| `chain` | string |
| `allowExpired` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/nginx/certificate" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "key": "<value>", "chain": "<value>", "allowExpired": "<value>"}'
```

## GET `/admin/api/trino-gateway/{id}/attached-groups` { #get-admin-api-trino-gateway-id-attached-groups }

- **Permission:** Any signed-in user
- **CLI:** `changoctl trino-gateway attached-groups get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/attached-groups" -H "Authorization: Bearer $T"
```

## POST `/admin/api/trino-gateway/{id}/attached-groups` { #post-admin-api-trino-gateway-id-attached-groups }

- **Permission:** Administrator
- **CLI:** `changoctl trino-gateway attached-groups set ID [--group A,B]`

**Body (JSON):**

| Field | Type |
|---|---|
| `group` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/trino-gateway/<id>/attached-groups" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"group": "<value>"}'
```
