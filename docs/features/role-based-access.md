# Role-Based Access (Stage 1)

Chango's IAM model is AWS-style — users, groups, policies with `Effect: Allow|Deny`. The data plane (Trino, Spark, Flink via Ontul authz) enforces fine-grained per-action / per-resource policies on every query. The chango **control plane** — admin REST API and admin UI — currently runs in a simpler **Stage-1 RBAC** mode: every authenticated user can read, only admins can mutate or reveal secrets.

Stage-2 will swap this blanket admin gate for the same fine-grained `canPerform(user, action, resource)` check the data plane uses; until then, Stage-1 is the bright line that protects the control plane.

## The Stage-1 rule

> A user is **admin** iff they hold the `AdministratorAccess` policy (directly attached or attached to a group they belong to). Every other authenticated user is **read-only**.

The default `admin` user belongs to `admin-group`, which holds `AdministratorAccess` — that's the admin. Any IAM user you create later is non-admin by default; add them to a group with `AdministratorAccess` to make them admin.

## What admins can do

Everything. Every mutating route, every secret-reveal route, every config endpoint, every install / start / stop / restart / scale call. Same surface as the `admin` user.

## What non-admins can do

Every authenticated `GET` that does **not** return a secret. Concretely:

- Read the cluster topology, every component's instance list, status, metrics.
- Read the admin UI's nginx / scale / install / configure panels in read-only mode (the form values are visible; the buttons are hidden).
- View backup history (not the destination credentials).
- View the patch library (not upload / apply / rollback).
- Read IAM users / groups / policies (not access keys, not user passwords).

## What non-admins cannot do

Two gates close on the backend:

### 1. Mutations

Any `POST`, `PUT`, `PATCH`, `DELETE` except under `/admin/api/auth/*`. Examples:

- `POST /admin/api/ontul` (install)
- `POST /admin/api/ontul/<id>/restart`
- `POST /admin/api/iam/users`
- `POST /admin/api/backup/run`
- `POST /admin/api/patch/upload`
- `PUT  /admin/api/backup/config`
- `POST /admin/api/<comp>/<id>/config`
- `POST /admin/api/<comp>/<id>/scale`

A non-admin hitting any of these gets:

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"error":"forbidden: 'alice' is not authorized — admin role required."}
```

### 2. Secret-reveal GETs

Some `GET` routes return live secrets in the response body — they're closed to non-admins too:

| Route | What it reveals |
|---|---|
| `GET /admin/api/iam/download-key/<accessKeyId>` | The access key's secret + (optionally) session token — single-use download. |
| `GET /admin/api/<comp>/<id>/password` | The component's superuser / admin password (Postgres, Shannonstore, Ontul, Kiok, NeoRunBase, Mium). |
| `GET /admin/api/<comp>/<id>/admin-password` | Same, for components that distinguish admin-password from a sweep-discovered password. |
| `GET /admin/api/polaris/<id>/catalog-config` | Polaris catalog body including the S3 secret-access-key. |
| `GET /admin/api/polaris/<id>/catalog-connection` | Same. |

Both gates are in `AdminApiHandler.handle()`:

```java
boolean mutating       = !"GET".equals(method);
boolean revealsSecret  = rest.startsWith("iam/download-key/")
                      || rest.endsWith("/admin-password")
                      || rest.endsWith("/password")
                      || rest.endsWith("/catalog-config")
                      || rest.endsWith("/catalog-connection")
                      || …;
if ((mutating || revealsSecret) && !rest.startsWith("auth/") && !isAdmin(authUser))
    return 403;
```

`auth/*` (login, refresh, session, logout, change-password) stays open — that's how a user reaches the admin UI in the first place. `change-password` runs `requireLeader()` internally; a non-admin rotating their own password works fine.

## Admin UI behaviour

`useAuth()` exposes an `isAdmin` flag derived from the login response (`/admin/api/auth/login` returns `{accessToken, isAdmin}`). The non-admin UI:

- Shows a yellow read-only banner at the top of every page: "You are signed in as a non-admin user. Mutations and secret reveals are hidden."
- Hides every mutating button — **Install**, **Start**, **Stop**, **Restart**, **Scale**, **Configure**, **Delete**, **Apply**, **Upload**, **Backup Now**, **Generate access key**, **Add user / group / policy**, **Attach policy**, …
- Hides every secret-reveal button — **Show password**, **Show admin password**, **Download access key**, **Show catalog connection**.
- Disables the patches dropzone and the IAM "Create user / group / policy" entry points.

This is consistent across all 14 component pages (Ontul, kiok, ShannonStore, NeoRunBase, ItdaStream, Mium, Postgres, Polaris, Kafka, Schema Registry, Trino, Trino Gateway, Spark, Flink, UI Proxy), plus the IAM page, the Backup page, the Topology page, and the Settings → Patches page. Read paths are untouched — every status, every metric, every list works the same as for an admin.

The UI is the convenience layer; the backend gates above are the authoritative ones. An attacker who builds a custom HTTP client and bypasses the UI still hits the 403.

## Why secret-reveal is on the same gate as mutation

Without the second gate, a non-admin user could call `GET /admin/api/iam/download-key/<id>` and walk away with another user's secret access key, even though they can not mutate IAM directly. Same for component passwords: `GET /admin/api/postgres/pg-main/password` would leak the postgres superuser password to anyone who could log in. Stage-1's working assumption is "read-only" means **no secrets**, not just no mutation.

## Bootstrap

The default `admin` user is the only admin out of the box. After the first password rotation, the operator typically:

1. Creates a per-human user (e.g. `alice`).
2. Adds `alice` to `admin-group`.
3. Logs in as `alice` from then on; uses the original `admin` only as a break-glass account.

Non-admin users are typically service principals — kiok DAGs, ansible runners, CI scripts — that only need to read cluster status. Issue them an access key from IAM (admin-only), and call the API with the bearer token derived from that key.

## Stage-2 (planned)

Stage-2 replaces the blanket admin / non-admin split with per-route `canPerform(user, action, resource)`:

- `chango:component:install`, `chango:component:start`, `chango:component:restart`, `chango:component:scale`, `chango:component:delete`
- `chango:iam:read`, `chango:iam:write`, `chango:iam:downloadKey`
- `chango:backup:run`, `chango:backup:configure`
- `chango:patch:upload`, `chango:patch:apply`, `chango:patch:rollback`
- `chango:kms:wrap`, `chango:kms:unwrap`

Until that ships, Stage-1 is the source of truth — and Stage-1 is enforced at both the backend (authoritative) and the admin UI (visible).
