# Control Plane — health, cluster, auth, nodes, metrics

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

| Method | Path | Permission | changoctl |
|---|---|---|---|
| GET | [`/health`](#get-health) | Public | `changoctl health` |
| GET | [`/api/v1/cluster/info`](#get-api-v1-cluster-info) | Public | `changoctl cluster info` |
| GET | [`/api/v1/gateway/topology`](#get-api-v1-gateway-topology) | Public | `changoctl gateway topology` |
| POST | [`/admin/api/auth/login`](#post-admin-api-auth-login) | Public | `changoctl auth login` |
| POST | [`/admin/api/auth/refresh`](#post-admin-api-auth-refresh) | Public | `changoctl auth refresh` |
| GET | [`/admin/api/auth/session`](#get-admin-api-auth-session) | Signed-in user (self) | `changoctl whoami` |
| POST | [`/admin/api/auth/logout`](#post-admin-api-auth-logout) | Signed-in user (self) | `changoctl auth logout` |
| POST | [`/admin/api/auth/change-password`](#post-admin-api-auth-change-password) | Signed-in user (self) | `changoctl passwd` |
| GET | [`/admin/api/auth/sso/providers`](#get-admin-api-auth-sso-providers) | Public | `changoctl sso providers` |
| POST | [`/admin/api/auth/sso/ldap/login`](#post-admin-api-auth-sso-ldap-login) | Public | `changoctl sso ldap-login` |
| GET | [`/admin/api/auth/sso/oidc/start`](#get-admin-api-auth-sso-oidc-start) | Public | `changoctl sso oidc-start` |
| GET | [`/admin/api/auth/sso/saml/start`](#get-admin-api-auth-sso-saml-start) | Public | `changoctl sso saml-start` |
| GET | [`/admin/api/nodes/masters`](#get-admin-api-nodes-masters) | Any signed-in user | `changoctl nodes masters` |
| GET | [`/admin/api/nodes/node-managers`](#get-admin-api-nodes-node-managers) | Any signed-in user | `changoctl nodes node-managers` |
| GET | [`/admin/api/nodes/zookeepers`](#get-admin-api-nodes-zookeepers) | Any signed-in user | `changoctl nodes zookeepers` |
| GET | [`/admin/api/nodes/logs`](#get-admin-api-nodes-logs) | Any signed-in user | `changoctl nodes logs --node V [--lines V]` |
| GET | [`/admin/api/monitoring/metrics`](#get-admin-api-monitoring-metrics) | Any signed-in user | `changoctl monitoring metrics` |
| GET | [`/admin/api/monitoring/hosts`](#get-admin-api-monitoring-hosts) | Any signed-in user | `changoctl monitoring hosts` |
| GET | [`/admin/api/credentials/download`](#get-admin-api-credentials-download) | Administrator | `changoctl credentials download --component V --cluster V --field V [-O FILE]` |

## GET `/health` { #get-health }

- **Permission:** Public
- **CLI:** `changoctl health`

```bash
curl -s -X GET "https://node-1.example.com:8080/health"
```

## GET `/api/v1/cluster/info` { #get-api-v1-cluster-info }

- **Permission:** Public
- **CLI:** `changoctl cluster info`

```bash
curl -s -X GET "https://node-1.example.com:8080/api/v1/cluster/info"
```

## GET `/api/v1/gateway/topology` { #get-api-v1-gateway-topology }

- **Permission:** Public
- **CLI:** `changoctl gateway topology`

```bash
curl -s -X GET "https://node-1.example.com:8080/api/v1/gateway/topology"
```

## POST `/admin/api/auth/login` { #post-admin-api-auth-login }

- **Permission:** Public
- **CLI:** `changoctl auth login`

**Body (JSON):**

| Field | Type | Description |
|---|---|---|
| `username` | string | console user |
| `password` | string |  |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/auth/login" -H 'Content-Type: application/json' -d '{"username": "<value>", "password": "<value>"}'
```

## POST `/admin/api/auth/refresh` { #post-admin-api-auth-refresh }

- **Permission:** Public
- **CLI:** `changoctl auth refresh`

**Body (JSON):**

| Field | Type | Description |
|---|---|---|
| `refreshToken` | string | the refresh token of the last login/refresh — it rotates |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/auth/refresh" -H 'Content-Type: application/json' -d '{"refreshToken": "<value>"}'
```

## GET `/admin/api/auth/session` { #get-admin-api-auth-session }

- **Permission:** Signed-in user (self)
- **CLI:** `changoctl whoami`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/auth/session" -H "Authorization: Bearer $T"
```

## POST `/admin/api/auth/logout` { #post-admin-api-auth-logout }

- **Permission:** Signed-in user (self)
- **CLI:** `changoctl auth logout`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/auth/logout" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## POST `/admin/api/auth/change-password` { #post-admin-api-auth-change-password }

- **Permission:** Signed-in user (self)
- **CLI:** `changoctl passwd`

**Body (JSON):**

| Field | Type | Description |
|---|---|---|
| `oldPassword` | string |  |
| `newPassword` | string |  |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/auth/change-password" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"oldPassword": "<value>", "newPassword": "<value>"}'
```

## GET `/admin/api/auth/sso/providers` { #get-admin-api-auth-sso-providers }

- **Permission:** Public
- **CLI:** `changoctl sso providers`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/auth/sso/providers"
```

## POST `/admin/api/auth/sso/ldap/login` { #post-admin-api-auth-sso-ldap-login }

- **Permission:** Public
- **CLI:** `changoctl sso ldap-login`

**Body (JSON):**

| Field | Type | Description |
|---|---|---|
| `username` | string | directory user |
| `password` | string |  |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/auth/sso/ldap/login" -H 'Content-Type: application/json' -d '{"username": "<value>", "password": "<value>"}'
```

## GET `/admin/api/auth/sso/oidc/start` { #get-admin-api-auth-sso-oidc-start }

- **Permission:** Public
- **CLI:** `changoctl sso oidc-start`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/auth/sso/oidc/start"
```

## GET `/admin/api/auth/sso/saml/start` { #get-admin-api-auth-sso-saml-start }

- **Permission:** Public
- **CLI:** `changoctl sso saml-start`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/auth/sso/saml/start"
```

## GET `/admin/api/nodes/masters` { #get-admin-api-nodes-masters }

- **Permission:** Any signed-in user
- **CLI:** `changoctl nodes masters`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/nodes/masters" -H "Authorization: Bearer $T"
```

## GET `/admin/api/nodes/node-managers` { #get-admin-api-nodes-node-managers }

- **Permission:** Any signed-in user
- **CLI:** `changoctl nodes node-managers`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/nodes/node-managers" -H "Authorization: Bearer $T"
```

## GET `/admin/api/nodes/zookeepers` { #get-admin-api-nodes-zookeepers }

- **Permission:** Any signed-in user
- **CLI:** `changoctl nodes zookeepers`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/nodes/zookeepers" -H "Authorization: Bearer $T"
```

## GET `/admin/api/nodes/logs` { #get-admin-api-nodes-logs }

- **Permission:** Any signed-in user
- **CLI:** `changoctl nodes logs --node V [--lines V]`

**Query parameters:** `node`, `lines`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/nodes/logs?node=<value>&lines=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/monitoring/metrics` { #get-admin-api-monitoring-metrics }

- **Permission:** Any signed-in user
- **CLI:** `changoctl monitoring metrics`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/monitoring/metrics" -H "Authorization: Bearer $T"
```

## GET `/admin/api/monitoring/hosts` { #get-admin-api-monitoring-hosts }

- **Permission:** Any signed-in user
- **CLI:** `changoctl monitoring hosts`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/monitoring/hosts" -H "Authorization: Bearer $T"
```

## GET `/admin/api/credentials/download` { #get-admin-api-credentials-download }

- **Permission:** Administrator
- **CLI:** `changoctl credentials download --component V --cluster V --field V [-O FILE]`

**Query parameters:** `component`, `cluster`, `field`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/credentials/download?component=<value>&cluster=<value>&field=<value>" -H "Authorization: Bearer $T"
```
