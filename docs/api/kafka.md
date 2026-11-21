# Kafka (+ Connect, topics)

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

## Cluster record

Cluster routes of this component return the cluster record. Secret settings (passwords, secret keys, tokens) are never returned — they read `***`; download them with `GET /admin/api/credentials/download` (administrator).

```json
{
  "clusterId": "kafka-1",
  "componentType": "kafka",
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

!!! note "Kafka Connect pass-through"
    `/admin/api/kafka/{id}/connect/connectors…` is forwarded verbatim to the Kafka Connect REST
    API of that cluster (`/connectors…`, query string included), so `pause`, `resume`, `restart`,
    `status` and `config` behave exactly as Kafka Connect documents them.

| Method | Path | Permission | changoctl |
|---|---|---|---|
| GET | [`/admin/api/kafka`](#get-admin-api-kafka) | Any signed-in user | `changoctl kafka list` |
| GET | [`/admin/api/kafka/install-defaults`](#get-admin-api-kafka-install-defaults) | Any signed-in user | `changoctl kafka defaults` |
| POST | [`/admin/api/kafka`](#post-admin-api-kafka) | Administrator | `changoctl kafka install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/kafka/{id}`](#get-admin-api-kafka-id) | Any signed-in user | `changoctl kafka get ID` |
| DELETE | [`/admin/api/kafka/{id}`](#delete-admin-api-kafka-id) | Administrator | `changoctl kafka delete ID [--purge-data]` |
| POST | [`/admin/api/kafka/{id}/start`](#post-admin-api-kafka-id-start) | Administrator | `changoctl kafka start ID` |
| POST | [`/admin/api/kafka/{id}/stop`](#post-admin-api-kafka-id-stop) | Administrator | `changoctl kafka stop ID` |
| POST | [`/admin/api/kafka/{id}/restart`](#post-admin-api-kafka-id-restart) | Administrator | `changoctl kafka restart ID` |
| GET | [`/admin/api/kafka/{id}/metrics`](#get-admin-api-kafka-id-metrics) | Any signed-in user | `changoctl kafka metrics ID` |
| GET | [`/admin/api/kafka/{id}/config`](#get-admin-api-kafka-id-config) | Any signed-in user | `changoctl kafka config get ID` |
| POST | [`/admin/api/kafka/{id}/config`](#post-admin-api-kafka-id-config) | Administrator | `changoctl kafka config set ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/kafka/{id}/scale`](#post-admin-api-kafka-id-scale) | Administrator | `changoctl kafka scale ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/kafka/{id}/unscale`](#post-admin-api-kafka-id-unscale) | Administrator | `changoctl kafka unscale ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/kafka/{id}/nginx`](#get-admin-api-kafka-id-nginx) | Any signed-in user | `changoctl kafka nginx get ID` |
| POST | [`/admin/api/kafka/{id}/nginx`](#post-admin-api-kafka-id-nginx) | Administrator | `changoctl kafka nginx set ID [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/kafka/{id}/topics`](#get-admin-api-kafka-id-topics) | Any signed-in user | `changoctl kafka topics ID` |
| POST | [`/admin/api/kafka/{id}/topics`](#post-admin-api-kafka-id-topics) | Administrator | `changoctl kafka topic create ID [NAME] [--partitions V] [--replication-factor V]` |
| DELETE | [`/admin/api/kafka/{id}/topics/{topic}`](#delete-admin-api-kafka-id-topics-topic) | Administrator | `changoctl kafka topic delete ID TOPIC` |
| GET | [`/admin/api/kafka/{id}/connect`](#get-admin-api-kafka-id-connect) | Any signed-in user | `changoctl kafka connect get ID` |
| POST | [`/admin/api/kafka/{id}/connect`](#post-admin-api-kafka-id-connect) | Administrator | `changoctl kafka connect install ID [--FIELD VALUE ...] [-f body.json]` |
| POST | [`/admin/api/kafka/{id}/connect/restart`](#post-admin-api-kafka-id-connect-restart) | Administrator | `changoctl kafka connect restart ID` |
| GET | [`/admin/api/kafka/{id}/connect/plugins`](#get-admin-api-kafka-id-connect-plugins) | Any signed-in user | `changoctl kafka connect plugins ID` |
| POST | [`/admin/api/kafka/{id}/connect/plugins`](#post-admin-api-kafka-id-connect-plugins) | Administrator | `changoctl kafka connect plugin upload ID --plugin-id V [--name V] [--version V] --file FILE` |
| DELETE | [`/admin/api/kafka/{id}/connect/plugins/{pluginId}`](#delete-admin-api-kafka-id-connect-plugins-pluginid) | Administrator | `changoctl kafka connect plugin delete ID PLUGINID` |
| POST | [`/admin/api/kafka/{id}/connect/plugins/default`](#post-admin-api-kafka-id-connect-plugins-default) | Administrator | `changoctl kafka connect plugin install-default ID [--connector A,B]` |
| GET | [`/admin/api/kafka/{id}/connect/connector-plugins`](#get-admin-api-kafka-id-connect-connector-plugins) | Any signed-in user | `changoctl kafka connect connector-plugins ID` |
| GET | [`/admin/api/kafka/{id}/connect/connectors`](#get-admin-api-kafka-id-connect-connectors) | Any signed-in user | `changoctl kafka connect connectors ID [--expand V]` |
| GET | [`/admin/api/kafka/{id}/connect/connectors/{name}`](#get-admin-api-kafka-id-connect-connectors-name) | Any signed-in user | `changoctl kafka connect connector get ID NAME` |
| GET | [`/admin/api/kafka/{id}/connect/connectors/{name}/status`](#get-admin-api-kafka-id-connect-connectors-name-status) | Any signed-in user | `changoctl kafka connect connector status ID NAME` |
| GET | [`/admin/api/kafka/{id}/connect/connectors/{name}/config`](#get-admin-api-kafka-id-connect-connectors-name-config) | Any signed-in user | `changoctl kafka connect connector config ID NAME` |
| PUT | [`/admin/api/kafka/{id}/connect/connectors/{name}/config`](#put-admin-api-kafka-id-connect-connectors-name-config) | Administrator | `changoctl kafka connect connector put ID NAME -f body.json \| --set K=V` |
| POST | [`/admin/api/kafka/{id}/connect/connectors`](#post-admin-api-kafka-id-connect-connectors) | Administrator | `changoctl kafka connect connector create ID -f body.json \| --set K=V` |
| PUT | [`/admin/api/kafka/{id}/connect/connectors/{name}/pause`](#put-admin-api-kafka-id-connect-connectors-name-pause) | Administrator | `changoctl kafka connect connector pause ID NAME` |
| PUT | [`/admin/api/kafka/{id}/connect/connectors/{name}/resume`](#put-admin-api-kafka-id-connect-connectors-name-resume) | Administrator | `changoctl kafka connect connector resume ID NAME` |
| POST | [`/admin/api/kafka/{id}/connect/connectors/{name}/restart`](#post-admin-api-kafka-id-connect-connectors-name-restart) | Administrator | `changoctl kafka connect connector restart ID NAME` |
| POST | [`/admin/api/kafka/{id}/connect/connectors/{name}/tasks/{task}/restart`](#post-admin-api-kafka-id-connect-connectors-name-tasks-task-restart) | Administrator | `changoctl kafka connect connector task-restart ID NAME TASK` |
| DELETE | [`/admin/api/kafka/{id}/connect/connectors/{name}`](#delete-admin-api-kafka-id-connect-connectors-name) | Administrator | `changoctl kafka connect connector delete ID NAME` |

## GET `/admin/api/kafka` { #get-admin-api-kafka }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka" -H "Authorization: Bearer $T"
```

**Response:** Array of cluster records.

## GET `/admin/api/kafka/install-defaults` { #get-admin-api-kafka-install-defaults }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka defaults`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/install-defaults" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka` { #post-admin-api-kafka }

- **Permission:** Administrator
- **CLI:** `changoctl kafka install [CLUSTERID] [--FIELD VALUE ...] [-f body.json]`

**Body:** `KafkaClusterRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `clusterId` | string |  | Optional — auto-generated (kafka-) when blank. |
| `version` | string | `"3.7.2"` |  |
| `packageFile` | string | `"kafka/kafka_2.12-3.7.2.tgz"` | Package path under the master's components dir. |
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance (count should be odd: 1, 3, 5, ...). |
| `brokerNodes` | list |  | One NM nodeId per Broker instance. |
| `schemaRegistryNodes` | list |  | One NM nodeId per Schema Registry instance installed alongside the brokers and bound to this cluster's brokers. |
| `installBaseDir` | string | `"/opt/components"` | Base directory on each NM host under which instance install dirs are created. |
| `brokerJvm` | object:JvmConfig |  | Optional JVM tuning for the Broker role, seeded into every broker's config/jvm.conf and config/kafka-env.sh at install time. |
| `schemaRegistryJvm` | object:JvmConfig |  | Optional JVM tuning for the co-located Schema Registry role. |
| `properties` | map |  | Optional server.properties overrides applied after install — same key=value form the post-install Configure panel edits. |
| `logDir` | string |  | Absolute directory for the broker's application logs (server.log, *.out). |
| `dataDir` | string |  | Absolute root for broker topic data (log.dirs). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"version": "3.7.2", "packageFile": "kafka/kafka_2.12-3.7.2.tgz", "installBaseDir": "/opt/components"}'
```

## GET `/admin/api/kafka/{id}` { #get-admin-api-kafka-id }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>" -H "Authorization: Bearer $T"
```

**Response:** The cluster record (secret settings shown as `***`).

## DELETE `/admin/api/kafka/{id}` { #delete-admin-api-kafka-id }

- **Permission:** Administrator
- **CLI:** `changoctl kafka delete ID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/kafka/<id>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka/{id}/start` { #post-admin-api-kafka-id-start }

- **Permission:** Administrator
- **CLI:** `changoctl kafka start ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/kafka/{id}/stop` { #post-admin-api-kafka-id-stop }

- **Permission:** Administrator
- **CLI:** `changoctl kafka stop ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## POST `/admin/api/kafka/{id}/restart` { #post-admin-api-kafka-id-restart }

- **Permission:** Administrator
- **CLI:** `changoctl kafka restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

**Response:** The updated cluster record.

## GET `/admin/api/kafka/{id}/metrics` { #get-admin-api-kafka-id-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka metrics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kafka/{id}/config` { #get-admin-api-kafka-id-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka config get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/config" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka/{id}/config` { #post-admin-api-kafka-id-config }

- **Permission:** Administrator
- **CLI:** `changoctl kafka config set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KafkaConfigRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `properties` | map |  | server.properties key=value edits applied to every Broker node. |
| `brokerJvm` | object:JvmConfig |  | JVM tuning for the Broker group (conf/jvm.conf); null/empty → unchanged. |
| `schemaRegistryJvm` | object:JvmConfig |  | JVM tuning for the co-located Schema Registry; null/empty → unchanged. |
| `logDir` | string |  | Absolute directory for the broker's application logs (server.log, *.out). |
| `dataDir` | string |  | Absolute root for broker topic data (log.dirs). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"properties": "<value>", "brokerJvm": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/kafka/{id}/scale` { #post-admin-api-kafka-id-scale }

- **Permission:** Administrator
- **CLI:** `changoctl kafka scale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KafkaScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `brokerNodes` | list |  | One NM nodeId per Broker instance to add. |
| `schemaRegistryNodes` | list |  | One NM nodeId per Schema Registry instance to add (non-disruptive). |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/kafka/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/scale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "brokerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## POST `/admin/api/kafka/{id}/unscale` { #post-admin-api-kafka-id-unscale }

- **Permission:** Administrator
- **CLI:** `changoctl kafka unscale ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KafkaScaleRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `zkNodes` | list |  | One NM nodeId per ZooKeeper instance to add (triggers an ensemble rebuild + restart). |
| `brokerNodes` | list |  | One NM nodeId per Broker instance to add. |
| `schemaRegistryNodes` | list |  | One NM nodeId per Schema Registry instance to add (non-disruptive). |
| `removeInstanceIds` | list |  | Scale-IN: instance ids to remove from the cluster (POST /admin/api/kafka/{id/unscale}). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/unscale" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"zkNodes": "<value>", "brokerNodes": "<value>"}'
```

**Response:** The updated cluster record.

## GET `/admin/api/kafka/{id}/nginx` { #get-admin-api-kafka-id-nginx }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka nginx get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/nginx" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka/{id}/nginx` { #post-admin-api-kafka-id-nginx }

- **Permission:** Administrator
- **CLI:** `changoctl kafka nginx set ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KafkaNginxRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `nodeId` | string |  | NM nodeId the Schema Registry nginx proxy runs on. |
| `registryListenPort` | int | `0` | Optional preferred listen port. |
| `registryInstanceIds` | list |  | Schema Registry instance ids to place behind the proxy (the upstream pool). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/nginx" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"registryListenPort": 0}'
```

## GET `/admin/api/kafka/{id}/topics` { #get-admin-api-kafka-id-topics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka topics ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/topics" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka/{id}/topics` { #post-admin-api-kafka-id-topics }

- **Permission:** Administrator
- **CLI:** `changoctl kafka topic create ID [NAME] [--partitions V] [--replication-factor V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `partitions` | string |
| `replicationFactor` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/topics" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"partitions": "<value>", "replicationFactor": "<value>"}'
```

## DELETE `/admin/api/kafka/{id}/topics/{topic}` { #delete-admin-api-kafka-id-topics-topic }

- **Permission:** Administrator
- **CLI:** `changoctl kafka topic delete ID TOPIC`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/kafka/<id>/topics/<topic>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kafka/{id}/connect` { #get-admin-api-kafka-id-connect }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka connect get ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/connect" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka/{id}/connect` { #post-admin-api-kafka-id-connect }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect install ID [--FIELD VALUE ...] [-f body.json]`

**Body:** `KafkaConnectRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `connectNodes` | list |  | Node managers to place Connect workers on. |
| `connectJvm` | object:JvmConfig |  | Optional heap / extra JVM flags for the workers. |
| `withDebezium` | bool |  | Install the bundled Debezium connectors as part of this call. |
| `debeziumConnectors` | list |  |  |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/connect" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"connectNodes": "<value>", "connectJvm": "<value>"}'
```

## POST `/admin/api/kafka/{id}/connect/restart` { #post-admin-api-kafka-id-connect-restart }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect restart ID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## GET `/admin/api/kafka/{id}/connect/plugins` { #get-admin-api-kafka-id-connect-plugins }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka connect plugins ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/plugins" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka/{id}/connect/plugins` { #post-admin-api-kafka-id-connect-plugins }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect plugin upload ID --plugin-id V [--name V] [--version V] --file FILE`

**Body:** the patch tarball as raw bytes (`Content-Type: application/gzip`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/plugins" -H "Authorization: Bearer $T" -H 'Content-Type: application/gzip' --data-binary @patch.tgz
```

## DELETE `/admin/api/kafka/{id}/connect/plugins/{pluginId}` { #delete-admin-api-kafka-id-connect-plugins-pluginid }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect plugin delete ID PLUGINID`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/plugins/<pluginId>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kafka/{id}/connect/plugins/default` { #post-admin-api-kafka-id-connect-plugins-default }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect plugin install-default ID [--connector A,B]`

**Body (JSON):**

| Field | Type |
|---|---|
| `connector` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/plugins/default" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"connector": "<value>"}'
```

## GET `/admin/api/kafka/{id}/connect/connector-plugins` { #get-admin-api-kafka-id-connect-connector-plugins }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka connect connector-plugins ID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connector-plugins" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kafka/{id}/connect/connectors` { #get-admin-api-kafka-id-connect-connectors }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka connect connectors ID [--expand V]`

**Query parameters:** `expand`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors?expand=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kafka/{id}/connect/connectors/{name}` { #get-admin-api-kafka-id-connect-connectors-name }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka connect connector get ID NAME`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kafka/{id}/connect/connectors/{name}/status` { #get-admin-api-kafka-id-connect-connectors-name-status }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka connect connector status ID NAME`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>/status" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kafka/{id}/connect/connectors/{name}/config` { #get-admin-api-kafka-id-connect-connectors-name-config }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kafka connect connector config ID NAME`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>/config" -H "Authorization: Bearer $T"
```

## PUT `/admin/api/kafka/{id}/connect/connectors/{name}/config` { #put-admin-api-kafka-id-connect-connectors-name-config }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect connector put ID NAME -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X PUT "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>/config" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## POST `/admin/api/kafka/{id}/connect/connectors` { #post-admin-api-kafka-id-connect-connectors }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect connector create ID -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## PUT `/admin/api/kafka/{id}/connect/connectors/{name}/pause` { #put-admin-api-kafka-id-connect-connectors-name-pause }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect connector pause ID NAME`

**Body:** `{}` (empty object).

```bash
curl -s -X PUT "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>/pause" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## PUT `/admin/api/kafka/{id}/connect/connectors/{name}/resume` { #put-admin-api-kafka-id-connect-connectors-name-resume }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect connector resume ID NAME`

**Body:** `{}` (empty object).

```bash
curl -s -X PUT "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>/resume" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## POST `/admin/api/kafka/{id}/connect/connectors/{name}/restart` { #post-admin-api-kafka-id-connect-connectors-name-restart }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect connector restart ID NAME`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## POST `/admin/api/kafka/{id}/connect/connectors/{name}/tasks/{task}/restart` { #post-admin-api-kafka-id-connect-connectors-name-tasks-task-restart }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect connector task-restart ID NAME TASK`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>/tasks/<task>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## DELETE `/admin/api/kafka/{id}/connect/connectors/{name}` { #delete-admin-api-kafka-id-connect-connectors-name }

- **Permission:** Administrator
- **CLI:** `changoctl kafka connect connector delete ID NAME`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/kafka/<id>/connect/connectors/<name>" -H "Authorization: Bearer $T"
```
