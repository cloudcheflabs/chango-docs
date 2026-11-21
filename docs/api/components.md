# Component instances (all types)

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

| Method | Path | Permission | changoctl |
|---|---|---|---|
| GET | [`/admin/api/components`](#get-admin-api-components) | Any signed-in user | `changoctl instances list` |
| POST | [`/admin/api/components/install`](#post-admin-api-components-install) | Administrator | `changoctl instances install [--FIELD VALUE ...] [-f body.json]` |
| GET | [`/admin/api/components/{instanceId}`](#get-admin-api-components-instanceid) | Any signed-in user | `changoctl instances get INSTANCEID` |
| DELETE | [`/admin/api/components/{instanceId}`](#delete-admin-api-components-instanceid) | Administrator | `changoctl instances delete INSTANCEID [--purge-data]` |
| POST | [`/admin/api/components/{instanceId}/start`](#post-admin-api-components-instanceid-start) | Administrator | `changoctl instances start INSTANCEID` |
| POST | [`/admin/api/components/{instanceId}/stop`](#post-admin-api-components-instanceid-stop) | Administrator | `changoctl instances stop INSTANCEID` |
| POST | [`/admin/api/components/{instanceId}/restart`](#post-admin-api-components-instanceid-restart) | Administrator | `changoctl instances restart INSTANCEID` |
| GET | [`/admin/api/components/{instanceId}/logs`](#get-admin-api-components-instanceid-logs) | Any signed-in user | `changoctl instances logs INSTANCEID [--lines V]` |
| GET | [`/admin/api/components/{instanceId}/metrics`](#get-admin-api-components-instanceid-metrics) | Any signed-in user | `changoctl instances metrics INSTANCEID` |

## GET `/admin/api/components` { #get-admin-api-components }

- **Permission:** Any signed-in user
- **CLI:** `changoctl instances list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/components" -H "Authorization: Bearer $T"
```

## POST `/admin/api/components/install` { #post-admin-api-components-install }

- **Permission:** Administrator
- **CLI:** `changoctl instances install [--FIELD VALUE ...] [-f body.json]`

**Body:** `ComponentInstallRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `instanceId` | string |  | Cluster-unique instance id (e.g. spark-1). |
| `componentType` | string |  | Component family — spark, trino, kafka, ... |
| `version` | string |  |  |
| `clusterId` | string |  | Owning cluster id — set when the instance is provisioned as part of a cluster; null otherwise. |
| `role` | string |  | Role within the cluster (e.g. ShannonStore zookeeper/api/data). |
| `nodeId` | string |  | Target NM nodeId (must be a registered node manager). |
| `packageFile` | string |  | Path relative to the master's components dir, e.g. spark/spark-3.5.8-bin-hadoop3.tgz. |
| `installPath` | string |  | Absolute path on the NM host where the package is extracted. |
| `startCommand` | string |  |  |
| `stopCommand` | string |  |  |
| `pidFile` | string |  |  |
| `runAsUser` | string |  | Linux user to install and run the component as (NM creates it if missing). |
| `javaVersion` | string |  | Major Java version for the component's start scripts (e.g. "17"); null → Java 17. |
| `env` | map |  |  |
| `config` | map |  |  |
| `propertiesPath` | string |  | Config-file path (relative to installPath) seeded after extraction, e.g. conf/shannonstore.properties. |
| `properties` | map |  | key=value entries upserted into #propertiesPath after the package is extracted. |
| `files` | map |  | Whole config files to overwrite after extraction (path relative to installPath → line list). |
| `binaryArtifacts` | map |  | Extra binary artifacts to ship with the install, keyed by target path (relative to installPath) → source path relative to the master's components/ dir. |
| `postInstallScript` | string |  | One-time setup script the NM runs after extraction (sudo available, cwd = installPath). |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/components/install" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"instanceId": "<value>", "componentType": "<value>"}'
```

## GET `/admin/api/components/{instanceId}` { #get-admin-api-components-instanceid }

- **Permission:** Any signed-in user
- **CLI:** `changoctl instances get INSTANCEID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/components/<instanceId>" -H "Authorization: Bearer $T"
```

## DELETE `/admin/api/components/{instanceId}` { #delete-admin-api-components-instanceid }

- **Permission:** Administrator
- **CLI:** `changoctl instances delete INSTANCEID [--purge-data]`

**Query parameters:** `purgeData`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/components/<instanceId>?purgeData=true" -H "Authorization: Bearer $T"
```

## POST `/admin/api/components/{instanceId}/start` { #post-admin-api-components-instanceid-start }

- **Permission:** Administrator
- **CLI:** `changoctl instances start INSTANCEID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/components/<instanceId>/start" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## POST `/admin/api/components/{instanceId}/stop` { #post-admin-api-components-instanceid-stop }

- **Permission:** Administrator
- **CLI:** `changoctl instances stop INSTANCEID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/components/<instanceId>/stop" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## POST `/admin/api/components/{instanceId}/restart` { #post-admin-api-components-instanceid-restart }

- **Permission:** Administrator
- **CLI:** `changoctl instances restart INSTANCEID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/components/<instanceId>/restart" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## GET `/admin/api/components/{instanceId}/logs` { #get-admin-api-components-instanceid-logs }

- **Permission:** Any signed-in user
- **CLI:** `changoctl instances logs INSTANCEID [--lines V]`

**Query parameters:** `lines`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/components/<instanceId>/logs?lines=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/components/{instanceId}/metrics` { #get-admin-api-components-instanceid-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl instances metrics INSTANCEID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/components/<instanceId>/metrics" -H "Authorization: Bearer $T"
```
