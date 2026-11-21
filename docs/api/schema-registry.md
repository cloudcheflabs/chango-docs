# Schema Registry

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "schema-registry-1",
  "componentType": "schema-registry",
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
| GET | [`/admin/api/schema-registry`](#get-admin-api-schema-registry) | Any signed-in user | `changoctl schema-registry list` |
| GET | [`/admin/api/schema-registry/install-defaults`](#get-admin-api-schema-registry-install-defaults) | Any signed-in user | `changoctl schema-registry defaults` |
| POST | [`/admin/api/schema-registry`](#post-admin-api-schema-registry) | Administrator | `changoctl schema-registry install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/schema-registry/{id}`](#get-admin-api-schema-registry-id) | Any signed-in user | `changoctl schema-registry get ID` |
| DELETE | [`/admin/api/schema-registry/{id}`](#delete-admin-api-schema-registry-id) | Administrator | `changoctl schema-registry delete ID [--purge-data]` |
| POST | [`/admin/api/schema-registry/{id}/start`](#post-admin-api-schema-registry-id-start) | Administrator | `changoctl schema-registry start ID` |
| POST | [`/admin/api/schema-registry/{id}/stop`](#post-admin-api-schema-registry-id-stop) | Administrator | `changoctl schema-registry stop ID` |
| POST | [`/admin/api/schema-registry/{id}/restart`](#post-admin-api-schema-registry-id-restart) | Administrator | `changoctl schema-registry restart ID` |
| GET | [`/admin/api/schema-registry/{id}/metrics`](#get-admin-api-schema-registry-id-metrics) | Any signed-in user | `changoctl schema-registry metrics ID` |
| GET | [`/admin/api/schema-registry/{id}/config`](#get-admin-api-schema-registry-id-config) | Any signed-in user | `changoctl schema-registry config get ID` |
| POST | [`/admin/api/schema-registry/{id}/config`](#post-admin-api-schema-registry-id-config) | Administrator | `changoctl schema-registry config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/schema-registry/{id}/scale`](#post-admin-api-schema-registry-id-scale) | Administrator | `changoctl schema-registry scale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/schema-registry/{id}/nginx`](#get-admin-api-schema-registry-id-nginx) | Any signed-in user | `changoctl schema-registry nginx get ID` |
| POST | [`/admin/api/schema-registry/{id}/nginx`](#post-admin-api-schema-registry-id-nginx) | Administrator | `changoctl schema-registry nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/schema-registry/sources`](#get-admin-api-schema-registry-sources) | Any signed-in user | `changoctl schema-registry sources` |
| GET | [`/admin/api/schema-registry/{id}/registry/subjects`](#get-admin-api-schema-registry-id-registry-subjects) | Any signed-in user | `changoctl schema-registry subjects ID [--deleted]` |
| GET | [`/admin/api/schema-registry/{id}/registry/schemas/types`](#get-admin-api-schema-registry-id-registry-schemas-types) | Any signed-in user | `changoctl schema-registry types ID` |
| GET | [`/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions`](#get-admin-api-schema-registry-id-registry-subjects-subject-versions) | Any signed-in user | `changoctl schema-registry versions ID SUBJECT [--deleted]` |
| GET | [`/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions/{version}`](#get-admin-api-schema-registry-id-registry-subjects-subject-versions-version) | Any signed-in user | `changoctl schema-registry version ID SUBJECT VERSION` |
| POST | [`/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions`](#post-admin-api-schema-registry-id-registry-subjects-subject-versions) | Administrator | `changoctl schema-registry register ID SUBJECT --schema V [--type V]` |
| POST | [`/admin/api/schema-registry/{id}/registry/compatibility/subjects/{subject}/versions/latest`](#post-admin-api-schema-registry-id-registry-compatibility-subjects-subject-versions-latest) | Administrator | `changoctl schema-registry check ID SUBJECT --schema V [--type V] [--detail]` |
| GET | [`/admin/api/schema-registry/{id}/registry/config`](#get-admin-api-schema-registry-id-registry-config) | Any signed-in user | `changoctl schema-registry compat get ID` |
| PUT | [`/admin/api/schema-registry/{id}/registry/config`](#put-admin-api-schema-registry-id-registry-config) | Administrator | `changoctl schema-registry compat set ID --level V` |
| GET | [`/admin/api/schema-registry/{id}/registry/config/{subject}`](#get-admin-api-schema-registry-id-registry-config-subject) | Any signed-in user | `changoctl schema-registry subject-compat get ID SUBJECT` |
| PUT | [`/admin/api/schema-registry/{id}/registry/config/{subject}`](#put-admin-api-schema-registry-id-registry-config-subject) | Administrator | `changoctl schema-registry subject-compat set ID SUBJECT --level V` |
| DELETE | [`/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions/{version}`](#delete-admin-api-schema-registry-id-registry-subjects-subject-versions-version) | Administrator | `changoctl schema-registry delete-version ID SUBJECT VERSION [--permanent]` |
| DELETE | [`/admin/api/schema-registry/{id}/registry/subjects/{subject}`](#delete-admin-api-schema-registry-id-registry-subjects-subject) | Administrator | `changoctl schema-registry delete-subject ID SUBJECT [--permanent]` |

## GET `/admin/api/schema-registry` { #get-admin-api-schema-registry }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/schema-registry/install-defaults` { #get-admin-api-schema-registry-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/schema-registry` { #post-admin-api-schema-registry }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `SchemaRegistryClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (schema-registry-) when blank. |
| `version` | string | `"7.7.1"` |  |
| `packageFile` | string | `"schema-registry/confluent-community-7.7.1.tar.gz"` | Package path under the master's components dir. |
| `kafkaBootstrapServers` | string |  | Kafka bootstrap server list (kafkastore.bootstrap.servers) — required, comma-separated host:port pairs. |
| `registryNodes` | list |  | One NM nodeId per Schema Registry instance. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `registryJvm` | object:JvmConfig |  | Optional JVM tuning for the Registry role, seeded into every registry's conf/jvm.conf at install time. |
| `properties` | map |  | Optional schema-registry.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the schema registry's log (its console output). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "7.7.1", "packageFile": "schema-registry/confluent-community-7.7.1.tar.gz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/schema-registry/{id}` { #get-admin-api-schema-registry-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/schema-registry/{id}` { #delete-admin-api-schema-registry-id }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/schema-registry/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/schema-registry/{id}/start` { #post-admin-api-schema-registry-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/schema-registry/{id}/stop` { #post-admin-api-schema-registry-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/schema-registry/{id}/restart` { #post-admin-api-schema-registry-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/schema-registry/{id}/metrics` { #get-admin-api-schema-registry-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/schema-registry/{id}/config` { #get-admin-api-schema-registry-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/schema-registry/{id}/config` { #post-admin-api-schema-registry-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `SchemaRegistryConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | schema-registry.properties key=value edits applied to every registry node. |
| `registryJvm` | object:JvmConfig |  | JVM tuning for the registry group (conf/jvm.conf); null/empty → unchanged. |
| `logDir` | string |  | Absolute directory for the schema registry's log (its console output). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "registryJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/schema-registry/{id}/scale` { #post-admin-api-schema-registry-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `SchemaRegistryScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `registryNodes` | list |  | One NM nodeId per Schema Registry instance to add. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"registryNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/schema-registry/{id}/nginx` { #get-admin-api-schema-registry-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/schema-registry/{id}/nginx` { #post-admin-api-schema-registry-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `SchemaRegistryNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the nginx proxy runs on. |
| `listenPort` | int | `8081` | TCP port nginx listens on for the proxied registry HTTP endpoint. |
| `registryInstanceIds` | list |  | Registry instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"listenPort": 8081}'
```

## GET `/admin/api/schema-registry/sources` { #get-admin-api-schema-registry-sources }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry sources`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/sources" -H "Authorization: Bearer $T"
```

## GET `/admin/api/schema-registry/{id}/registry/subjects` { #get-admin-api-schema-registry-id-registry-subjects }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry subjects ID [--deleted]`

**Query parameters:** `deleted`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/subjects?deleted=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/schema-registry/{id}/registry/schemas/types` { #get-admin-api-schema-registry-id-registry-schemas-types }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry types ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/schemas/types" -H "Authorization: Bearer $T"
```

## GET `/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions` { #get-admin-api-schema-registry-id-registry-subjects-subject-versions }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry versions ID SUBJECT [--deleted]`

**Query parameters:** `deleted`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/subjects/<subject>/versions?deleted=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions/{version}` { #get-admin-api-schema-registry-id-registry-subjects-subject-versions-version }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry version ID SUBJECT VERSION`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/subjects/<subject>/versions/<version>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions` { #post-admin-api-schema-registry-id-registry-subjects-subject-versions }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry register ID SUBJECT --schema V [--type V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `schema` | string |
| `type` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/subjects/<subject>/versions" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"schema": "<value>", "type": "<value>"}'
```

## POST `/admin/api/schema-registry/{id}/registry/compatibility/subjects/{subject}/versions/latest` { #post-admin-api-schema-registry-id-registry-compatibility-subjects-subject-versions-latest }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry check ID SUBJECT --schema V [--type V] [--detail]`

**Body (JSON):**

| Field | Type |
|---|---|
| `schema` | string |
| `type` | string |
| `detail` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/compatibility/subjects/<subject>/versions/latest" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"schema": "<value>", "type": "<value>", "detail": "<value>"}'
```

## GET `/admin/api/schema-registry/{id}/registry/config` { #get-admin-api-schema-registry-id-registry-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry compat get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/config" -H "Authorization: Bearer $T"
```

## PUT `/admin/api/schema-registry/{id}/registry/config` { #put-admin-api-schema-registry-id-registry-config }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry compat set ID --level V`

**Body (JSON):**

| Field | Type |
|---|---|
| `level` | string |

```bash
curl -s -X PUT "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"level": "<value>"}'
```

## GET `/admin/api/schema-registry/{id}/registry/config/{subject}` { #get-admin-api-schema-registry-id-registry-config-subject }

- **Permission:** Any signed-in user
- **CLI:** `changoctl schema-registry subject-compat get ID SUBJECT`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/config/<subject>" -H "Authorization: Bearer $T"
```

## PUT `/admin/api/schema-registry/{id}/registry/config/{subject}` { #put-admin-api-schema-registry-id-registry-config-subject }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry subject-compat set ID SUBJECT --level V`

**Body (JSON):**

| Field | Type |
|---|---|
| `level` | string |

```bash
curl -s -X PUT "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/config/<subject>" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"level": "<value>"}'
```

## DELETE `/admin/api/schema-registry/{id}/registry/subjects/{subject}/versions/{version}` { #delete-admin-api-schema-registry-id-registry-subjects-subject-versions-version }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry delete-version ID SUBJECT VERSION [--permanent]`

**Query parameters:** `permanent`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/subjects/<subject>/versions/<version>?permanent=<value>" -H "Authorization: Bearer $T"
```

## DELETE `/admin/api/schema-registry/{id}/registry/subjects/{subject}` { #delete-admin-api-schema-registry-id-registry-subjects-subject }

- **Permission:** Administrator
- **CLI:** `changoctl schema-registry delete-subject ID SUBJECT [--permanent]`

**Query parameters:** `permanent`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/schema-registry/<id>/registry/subjects/<subject>?permanent=<value>" -H "Authorization: Bearer $T"
```
