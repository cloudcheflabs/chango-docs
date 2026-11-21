# ItdaStream

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "itdastream-1",
  "componentType": "itdastream",
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
| GET | [`/admin/api/itdastream`](#get-admin-api-itdastream) | Any signed-in user | `changoctl itdastream list` |
| GET | [`/admin/api/itdastream/install-defaults`](#get-admin-api-itdastream-install-defaults) | Any signed-in user | `changoctl itdastream defaults` |
| POST | [`/admin/api/itdastream`](#post-admin-api-itdastream) | Administrator | `changoctl itdastream install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/itdastream/{id}`](#get-admin-api-itdastream-id) | Any signed-in user | `changoctl itdastream get ID` |
| DELETE | [`/admin/api/itdastream/{id}`](#delete-admin-api-itdastream-id) | Administrator | `changoctl itdastream delete ID [--purge-data]` |
| POST | [`/admin/api/itdastream/{id}/start`](#post-admin-api-itdastream-id-start) | Administrator | `changoctl itdastream start ID` |
| POST | [`/admin/api/itdastream/{id}/stop`](#post-admin-api-itdastream-id-stop) | Administrator | `changoctl itdastream stop ID` |
| POST | [`/admin/api/itdastream/{id}/restart`](#post-admin-api-itdastream-id-restart) | Administrator | `changoctl itdastream restart ID` |
| GET | [`/admin/api/itdastream/{id}/metrics`](#get-admin-api-itdastream-id-metrics) | Any signed-in user | `changoctl itdastream metrics ID` |
| GET | [`/admin/api/itdastream/{id}/config`](#get-admin-api-itdastream-id-config) | Any signed-in user | `changoctl itdastream config get ID` |
| POST | [`/admin/api/itdastream/{id}/config`](#post-admin-api-itdastream-id-config) | Administrator | `changoctl itdastream config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/itdastream/{id}/scale`](#post-admin-api-itdastream-id-scale) | Administrator | `changoctl itdastream scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/itdastream/{id}/unscale`](#post-admin-api-itdastream-id-unscale) | Administrator | `changoctl itdastream unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/itdastream/{id}/nginx`](#get-admin-api-itdastream-id-nginx) | Any signed-in user | `changoctl itdastream nginx get ID` |
| POST | [`/admin/api/itdastream/{id}/nginx`](#post-admin-api-itdastream-id-nginx) | Administrator | `changoctl itdastream nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/itdastream/{id}/credentials`](#post-admin-api-itdastream-id-credentials) | Administrator | `changoctl itdastream credentials set ID [--admin-password V] [--admin-otok V]` |

## GET `/admin/api/itdastream` { #get-admin-api-itdastream }

- **Permission:** Any signed-in user
- **CLI:** `changoctl itdastream list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/itdastream" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/itdastream/install-defaults` { #get-admin-api-itdastream-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl itdastream defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/itdastream/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/itdastream` { #post-admin-api-itdastream }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `ItdastreamClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (itdastream-) when blank. |
| `version` | string | `"1.0.0"` |  |
| `packageFile` | string | `"itdastream/itdastream-1.0.0.tar.gz"` | Package path under the master's components dir. |
| `masterKey` | string |  | ITDASTREAM_MASTER_KEY value — required, identical across the cluster, >= 32 chars. |
| `retiredKeyRef` | string |  | Reinstall with the retired key of a previously deleted cluster, named by that cluster's id. |
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance (count should be odd: 1, 3, 5, ...). |
| `brokerNodes` | list |  | One NM nodeId per Broker instance. |
| `schemaRegistryNodes` | list |  | One NM nodeId per Schema Registry instance installed alongside the brokers and bound to this cluster's brokers (Kafka-protocol bootstrap). |
| `kafkaBootstrapServers` | string |  | Kafka bootstrap servers itdastream consumes from — passed to every broker. |
| `schemaRegistryUrl` | string |  | Schema Registry URL itdastream resolves Avro schemas against — passed to every broker. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `brokerJvm` | object:JvmConfig |  | Optional JVM tuning for the Broker role, seeded into every broker's conf/jvm.conf at install time. |
| `properties` | map |  | Optional itdastream.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the product's own logs. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "1.0.0", "packageFile": "itdastream/itdastream-1.0.0.tar.gz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/itdastream/{id}` { #get-admin-api-itdastream-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl itdastream get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/itdastream/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/itdastream/{id}` { #delete-admin-api-itdastream-id }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/itdastream/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/itdastream/{id}/start` { #post-admin-api-itdastream-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/itdastream/{id}/stop` { #post-admin-api-itdastream-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/itdastream/{id}/restart` { #post-admin-api-itdastream-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/itdastream/{id}/metrics` { #get-admin-api-itdastream-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl itdastream metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/itdastream/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/itdastream/{id}/config` { #get-admin-api-itdastream-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl itdastream config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/itdastream/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/itdastream/{id}/config` { #post-admin-api-itdastream-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `ItdastreamConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | itdastream.properties key=value edits applied to every Broker node. |
| `brokerJvm` | object:JvmConfig |  | JVM tuning for the Broker group (conf/jvm.conf); null/empty → unchanged. |
| `logDir` | string |  | Absolute directory for the product's own logs. |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "brokerJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/itdastream/{id}/scale` { #post-admin-api-itdastream-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `ItdastreamScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `brokerNodes` | list |  | One NM nodeId per Broker instance to add. |
| `schemaRegistryNodes` | list |  | One NM nodeId per Schema Registry instance to add (non-disruptive). |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/itdastream/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "brokerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/itdastream/{id}/unscale` { #post-admin-api-itdastream-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `ItdastreamScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `brokerNodes` | list |  | One NM nodeId per Broker instance to add. |
| `schemaRegistryNodes` | list |  | One NM nodeId per Schema Registry instance to add (non-disruptive). |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/itdastream/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "brokerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/itdastream/{id}/nginx` { #get-admin-api-itdastream-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl itdastream nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/itdastream/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/itdastream/{id}/nginx` { #post-admin-api-itdastream-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `ItdastreamNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the Schema Registry nginx proxy runs on. |
| `registryListenPort` | int | `0` | Optional preferred listen port. |
| `registryInstanceIds` | list |  | Schema Registry instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"registryListenPort": 0}'
```

## POST `/admin/api/itdastream/{id}/credentials` { #post-admin-api-itdastream-id-credentials }

- **Permission:** Administrator
- **CLI:** `changoctl itdastream credentials set ID [--admin-password V] [--admin-otok V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `adminPassword` | string |
| `adminOtok` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/itdastream/<id>/credentials" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"adminPassword": "<value>", "adminOtok": "<value>"}'
```
