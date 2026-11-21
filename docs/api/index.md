# Admin API — Overview

Everything the admin console does goes through one REST API on every master:
`http(s)://<master>:8080/admin/api/…`. This reference lists **every route** — 392 of them,
grouped by area in the pages of this section — with its method, path, permission, request body
and a `curl` example. The same routes are available as commands in [`changoctl`](../operations/cli.md).

The pages are generated from the platform source (the route table, every `*Request` class's
fields, types and defaults, and the server's permission rules) by `tools/gen_api_reference.py`,
so they change only when the source does.

| Page | Covers |
|---|---|
| [Control Plane](control-plane.md) | `/health`, cluster info, login / refresh / session / password, nodes, metrics, logs, credential download |
| [Component instances](components.md) | `/admin/api/components…` — install, start / stop / restart, delete, logs of any instance |
| [Security](security.md) | IAM users & groups, SSO (OIDC / SAML / LDAP), KMS, STS, license, control-plane trust store |
| [Patches & Backup](patch-backup.md) | patch upload / apply / rollback / history, control-plane backup & restore |
| [PostgreSQL](postgres.md) · [Polaris](polaris.md) · [Ontul](ontul.md) · [Trino](trino.md) · [Trino Gateway](trino-gateway.md) · [Spark](spark.md) · [Flink](flink.md) · [Kafka](kafka.md) · [Schema Registry](schema-registry.md) · [Kiok](kiok.md) · [UI Proxy](ui-proxy.md) · [Mium](mium.md) · [NeoRunBase](neorunbase.md) · [ItdaStream](itdastream.md) · [ShannonStore](shannonstore.md) | the component's clusters: install, config, scale, nginx, trust store, credentials, and its own sub-resources (catalogs, topics, connectors, …) |

## Authentication

```bash
A=https://node-1.example.com:8080/admin/api
T=$(curl -s -X POST $A/auth/login -H 'Content-Type: application/json' \
      -d '{"username":"admin","password":"<password>"}' | jq -r .accessToken)
curl -s $A/components -H "Authorization: Bearer $T"
```

`POST /admin/api/auth/login` returns:

```json
{
  "accessToken": "eyJ…",
  "refreshToken": "eyJ…",
  "username": "admin",
  "isAdmin": true,
  "requirePasswordChange": false
}
```

- Every other route takes `Authorization: Bearer <accessToken>`.
- The access token lives **15 minutes**, the refresh token **24 hours**
  (`chango.admin.token.access.expiry.ms`, `chango.admin.token.refresh.expiry.ms`).
- `POST /admin/api/auth/refresh` with `{"refreshToken": "…"}` returns a **new pair** — the refresh token rotates,
  so keep the one it returns. An LDAP login returns no refresh token.
- Public routes (no token): `/health`, `/api/v1/cluster/info`, `/api/v1/gateway/topology`,
  `auth/login`, `auth/refresh`, `auth/sso/*`.

## Which master to call

Any master. A follower forwards every request except `auth/*` to the leader (connect 10 s, read 600 s) — there is no
redirect, so a client never has to find the leader itself. `GET /api/v1/cluster/info` shows the leader and the
readiness of every master and node manager.

| Answer | Meaning | What a client does |
|---|---|---|
| `503 {"error":"cluster not ready"}` | the master has not finished starting, or no leader is known | retry, or another master |
| `502` | the follower could not reach the leader | retry, or another master — the request was not performed |

## Order of checks

1. `GET /health` answers `200` on any master that is up.
2. Before the master is ready: `503 cluster not ready`.
3. Public routes are served.
4. No or invalid token: `401`.
5. A user who must change the initial password: `403` with `"requirePasswordChange": true` — every route except
   `auth/*` (so the change itself still works). Change it with `POST /admin/api/auth/change-password`.
6. Permission (next section): `403 forbidden: '<user>' is not authorized — admin role required.`

## Permissions

| Permission (in the route tables) | Who |
|---|---|
| **Public** | anyone |
| **Any signed-in user** | every console user — reads |
| **Administrator** | users in a group holding *AdministratorAccess* |
| **Signed-in user (self)** | the caller's own session and password (`auth/*`) |

An administrator is required for every change (any method other than `GET`) and for the `GET`s whose answer carries
a secret: `…/credentials`, `…/password`, `…/admin-password`, `…/catalog-config`, `…/catalog-connection`,
`iam/download-key/…` and `credentials/download`. The rule is enforced by the server for every route; the console
only hides the buttons.

Secret settings are never part of a normal answer — they read `***`. Fetch one with
`GET /admin/api/credentials/download?component=<type>&clusterId=<id>&field=<name>` (administrator).

## Errors

Errors are `{"error": "<message>"}`:

| Status | When |
|---|---|
| `400` | invalid argument or state (`IllegalArgumentException` / `IllegalStateException` in the handler) — the message says which |
| `401` | no or invalid token |
| `403` | password change required, or the route needs an administrator |
| `404` / `405` | unknown route or method |
| `409` / `410` | conflict (already exists) / route removed |
| `502` / `503` | see *Which master to call*; `gateway/*` also answers `503` for a gateway that is not ready |
| `500` | anything else — the master log has the stack trace |

## Unknown fields — `ignoredFields`

A request body field the server does not read is not an error: the request is **applied** and a successful JSON
object answer carries `"ignoredFields": ["s3PathStyle", …]`. Treat it as a warning that a value you meant to set was
dropped (typically a misspelt name — e.g. `s3PathStyle` instead of `s3PathStyleAccess`). `changoctl` checks field
names before sending.

## Long operations

Installs, Trino catalog changes, patch apply and similar calls are **synchronous** and the server sets no timeout —
they return when the work is done, which can take minutes. If the connection drops, the work continues on the
server: read the state again (`GET /admin/api/<component>/<id>`, `GET /admin/api/patch/history…`) instead of sending
the request again.
