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
- Change **their own** password — from the key icon (*Change password*) in the console header. See [below](#changing-your-own-password).

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
| `GET /admin/api/credentials/download?component=&clusterId=&field=` | One named credential, as a file download. |
| `GET /admin/api/<comp>/<id>/credentials` | PostgreSQL's superuser password, Polaris's root and per-catalog client secrets. |
| `GET /admin/api/<comp>/<id>/password` | The component's superuser / admin password (Postgres, Shannonstore, Ontul, Kiok, NeoRunBase, Mium). |
| `GET /admin/api/<comp>/<id>/admin-password` | Same, for components that distinguish admin-password from a sweep-discovered password. |
| `GET /admin/api/polaris/<id>/catalog-config` | Polaris catalog body including the S3 secret-access-key. |
| `GET /admin/api/polaris/<id>/catalog-connection` | Same. |

Both gates are in `AdminApiHandler.handle()`:

```java
boolean mutating       = !"GET".equals(method);
boolean revealsSecret  = rest.startsWith("iam/download-key/")
                      || rest.startsWith("credentials/download")
                      || rest.endsWith("/credentials")
                      || rest.endsWith("/admin-password")
                      || rest.endsWith("/password")
                      || rest.endsWith("/catalog-config")
                      || rest.endsWith("/catalog-connection")
                      || …;
if ((mutating || revealsSecret) && !rest.startsWith("auth/") && !isAdmin(authUser))
    return 403;
```

`…/<id>/credentials` was missing from that list for a while. It is a plain
`GET`, the console hid the buttons from a read-only user, and the route did
not — so a non-admin could fetch the PostgreSQL superuser password and
Polaris's catalog secrets by asking for them directly. Hiding a button is not
a gate.

### 3. Secrets are not in the cluster JSON at all

`GET /admin/api/<comp>` used to return `adminPassword` and `adminOtok` in the
settings, and the console rendered them behind an eye toggle. The toggle hid
them from the screen and from nobody else: the value had already been sent, so
it sat in the response body for anyone with the browser's network tab open, in
any HAR capture, and in whatever proxy log was in between.

So the response does not carry them. One function decides what a secret is —
by the shape of the key name (`secret`, `password`, `passwd`, `passphrase`,
`credential`, `privatekey`, or a name ending in `token`/`otok`), with an
explicit list of the few names that read like one and are not: access key ids,
client ids, user names. Those stay visible on purpose, because hiding them
leaves the operator unable to tell *which* credential is in use.

Each stripped key comes back as `<key>Present`, so the console can tell "not
issued yet" — the platform rotates these on a timer after a cluster reaches
RUNNING — from "stored, download it". The credential card shows
*stored — download to read* with one button, and the button goes to
`credentials/download`, which serves exactly one credential from a fixed list
and logs who asked. The fixed list matters: the same records hold the cluster
master key, and a route that reads an arbitrary setting name is a route that
reads that.

A name-shape rule replaced a list of names because the list leaked every time a
component grew a credential. It predated the admin password and service token;
`catalogPrincipalClientSecret.<catalog>` needed a second prefix-matching list
bolted on; and `exchangeS3SecretKey` and `eventLogS3SecretKey` — the query
engine's and the processing engine's object-storage keys — were never added at
all. There were also four separate functions building that JSON, each with its
own copy of the list, which is how `polarisJson` came to strip three keys and
pass a live per-catalog credential straight through.

### 4. Free-form config bodies are masked too

Catalog properties are a text blob, not key/value rows, so opening a Trino
catalog in the console printed its object-storage secret key on screen. Nobody
opens a catalog to read that value.

`listCatalogs` masks every property whose key is a secret and reports which keys
are hidden. The write-back is where this kind of masking usually goes wrong, so
`applyCatalog` reads the mask as *keep what is stored* and restores the real
value — saving the mask would put `********` in the catalog file and the catalog
would stop reaching its storage at the next restart, far from the edit. A mask
sent for a property that has no stored value is refused rather than saved empty.

### 5. Settings responses that used to carry secrets

The same "strip, report `<key>Present`" rule now also covers three responses
that bypassed it:

- `GET /admin/api/spark/<id>/config` returned the cluster settings whole —
  including `ontulAuthzToken` (the IAM engine service token) and the S3 secret
  keys, in plain text. Secrets are now omitted and flagged `<key>Present`. Access
  key ids (`s3AccessKey`, `eventLogS3AccessKey`, …) stay visible, as they do in
  the cluster JSON. Sending an empty value back means *keep the stored one*, so
  the Configure drawer still saves.
- `GET /admin/api/components` and the single-instance read serialised each
  instance's `env`, which for PostgreSQL holds the superuser password. Values of
  env keys ending in `PASSWORD`, `SECRET`, `SECRET_KEY`, `ACCESS_KEY`, `_TOKEN`
  or `MASTER_KEY` now come back as `***`; the keys stay, so the console can still
  tell that one is set. The credential download route still returns the real
  value.
- Polaris's server-wide S3 settings no longer return the secret key; they return
  `s3SecretKeySet` (`true`/`false`). The **S3 Credentials** tab shows the field as
  a password input, *set — leave empty to keep* or *not set*.

Polaris's per-catalog principal secret — the credential Trino, Spark and Flink
use against a catalog — is downloadable one at a time:
`GET /admin/api/credentials/download?component=polaris&clusterId=<id>&field=catalogPrincipalClientSecret.<catalog>`.
The catalog list carries `principalClientId` and `principalSecretPresent`, and
the **Iceberg Catalogs** panel shows the id with a download button on each row.

## Changing your own password

`auth/*` (login, refresh, session, logout, change-password) stays open — that's how a user reaches the admin UI in the first place. `change-password` runs `requireLeader()` internally; a non-admin rotating their own password works fine.

Every signed-in user, admin or not, has a **Change password** button (key icon)
in the console header next to **Sign out**, in both the main layout and the
Settings layout. It opens the same dialog as the first-login gate — **Current
Password**, **New Password**, **Confirm New Password** — and changes the password
of the user who is signed in. The new password must be at least 6 characters and
differ from the current one.

```bash
curl -s -X POST $BASE/admin/api/auth/change-password \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"oldPassword":"<current>","newPassword":"<new>"}'
```

Until this button existed the only entry point was **Change Admin Password** on
the KMS screen, which a non-admin sees as *Access Restricted* — the backend
allowed the change and the console offered no way to it.

## Admin UI behaviour

`useAuth()` exposes an `isAdmin` flag derived from the login response (`/admin/api/auth/login` returns `{accessToken, isAdmin}`). The non-admin UI:

- Shows a yellow banner at the top of every page: "Read-only mode — without admin rights, changes, actions and secret lookups are disabled."
- Hides every mutating button — **Install**, **Start**, **Stop**, **Restart**, **Scale**, **Configure**, **Delete**, **Apply**, **Upload**, **Backup Now**, **Generate access key**, **Add user / group / policy**, **Attach policy**, …
- Hides every secret-reveal button — **Show password**, **Show admin password**, **Download access key**, **Show catalog connection**.
- Disables the patches dropzone and the IAM "Create user / group / policy" entry points.
- Disables the inputs on the **SSO** page, not only its save button — a form you can edit but not save leaves you changing values without knowing why nothing sticks.

The row actions are where this slips: Trino's resource-group **Delete** and
Trino Gateway's backend **Delete** were outside the admin-only wrapper while the
**Edit** next to them was inside, so a non-admin saw buttons the backend then
refused with `403`. Both are hidden now. Every icon-only button also carries an
accessible name (`aria-label` / `title`) — of the 98 that had none, 38 were
deletes.

This is consistent across all 14 component pages (Ontul, kiok, ShannonStore, NeoRunBase, ItdaStream, Mium, Postgres, Polaris, Kafka, Schema Registry, Trino, Trino Gateway, Spark, Flink, UI Proxy), plus the IAM page, the Backup page, the Topology page, and the Settings → Patches page. Read paths are untouched — every status, every metric, every list works the same as for an admin.

The UI is the convenience layer; the backend gates above are the authoritative ones. An attacker who builds a custom HTTP client and bypasses the UI still hits the 403.

## Why secret-reveal is on the same gate as mutation

Without the second gate, a non-admin user could call `GET /admin/api/iam/download-key/<id>` and walk away with another user's secret access key, even though they can not mutate IAM directly. Same for component passwords: `GET /admin/api/postgres/pg-main/password` would leak the postgres superuser password to anyone who could log in. Stage-1's working assumption is "read-only" means **no secrets**, not just no mutation.

## Bootstrap

The default `admin` user is the only admin out of the box. After the first password rotation, the operator typically:

1. Creates a per-human user (e.g. `alice`).
2. Adds `alice` to `admin-group`.
3. Logs in as `alice` from then on; uses the original `admin` only as a break-glass account.

Non-admin console users are **read-only observers**: they sign in with a
password (or through [SSO](sso.md)) to look at topology, status, metrics and
history, and they can change their own password. chango deliberately offers no
self-service access keys — a non-admin cannot issue, list or download keys, and
the admin REST API authenticates with the bearer token from
`POST /admin/api/auth/login`, not with an access key.

## Stage-2 (planned)

Stage-2 replaces the blanket admin / non-admin split with per-route `canPerform(user, action, resource)`:

- `chango:component:install`, `chango:component:start`, `chango:component:restart`, `chango:component:scale`, `chango:component:delete`
- `chango:iam:read`, `chango:iam:write`, `chango:iam:downloadKey`
- `chango:backup:run`, `chango:backup:configure`
- `chango:patch:upload`, `chango:patch:apply`, `chango:patch:rollback`
- `chango:kms:wrap`, `chango:kms:unwrap`

Until that ships, Stage-1 is the source of truth — and Stage-1 is enforced at both the backend (authoritative) and the admin UI (visible).
