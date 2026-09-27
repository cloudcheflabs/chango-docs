# Identity & Access Management

Chango ships with a built-in IAM layer that controls who can do what against the admin UI, the REST API, and any cluster-wide operation. It is implemented inside chango itself — no external identity provider is required to bring chango up, and one can be added afterwards without giving this up: see [Single Sign-On](sso.md), where a federated identity maps onto the same groups and policies described here. Components that need their own authorization (Trino, Spark, Flink, …) delegate to Ontul; chango's IAM governs the control plane.

Local passwords are stored as PBKDF2-HMAC-SHA256 hashes. Values written by an earlier version as an unsalted SHA-256 still verify and are rewritten on their owner's next successful login, so no migration step is required.

## Concepts

The model is intentionally close to AWS IAM, so policies port across cleanly.

| Entity | What it is |
|---|---|
| **User** | A principal with credentials. Identified by username; can hold a password and one or more access keys. |
| **Group** | A named bundle of policies. Users get permissions by belonging to groups. |
| **Policy** | A versioned set of `Statement` rules — `Effect` (Allow / Deny) × `Action` × `Resource` × optional `Columns` / `Condition`. |
| **Access Key** | A long-lived `(accessKeyId, secretAccessKey, token)` triple issued for a user. Used by service-to-service calls (Ontul authz plugins, S3 SigV4 against ShannonStore). |
| **Temporary Credentials** | Short-lived `(accessKeyId, secretAccessKey, sessionToken, expiration)` issued by the STS endpoint for a federated principal. |

A policy statement looks like:

```json
{
  "Version": "2024-01-01",
  "Statement": [
    {
      "Sid": "allow-events",
      "Effect": "Allow",
      "Action": ["data:Select"],
      "Resource": ["data:table:lake.db.events"]
    }
  ]
}
```

> Actions live in the `data:` namespace and table resources in `data:table:` — see [Ontul IAM](https://cloudcheflabs.github.io/ontul-docs/1.0.0/features/iam/) for the full vocabulary plus the `Effect:"Deny"` / `Effect:"Mask"` (`MaskedColumns`) / `Condition` extensions that the chango-trino-authz plugin enforces on every query.

Statements are evaluated as a flat set across every policy attached (directly or via group) to the calling user. The order is the standard AWS one: explicit `Deny` always wins, otherwise the action must match at least one `Allow`.

## How chango uses it

Three places inside chango itself:

- **Admin UI login** — username + password against the IAM user table. The bootstrap creates an `admin` user with the default password `admin` and the `AdministratorAccess` policy attached; the first login forces a password change.
- **Admin REST API** — every request carries `Authorization: Bearer <accessToken>`. The token is issued at login by `AdminTokenService` and verified per request. Mutating routes (KMS / IAM / cluster install) are leader-only — followers return `421` with the leader's address.
- **STS for service principals** — `POST /admin/api/sts/assume-role` issues short-lived credentials that scripts can use without a long-lived password. Used internally by chango's own provisioners.

## How components use it

Chango is the master copy of IAM state, but the actual data-plane components (Trino, Spark, Flink) delegate authorization to **Ontul** — Ontul is the IAM authority that holds the user / group / policy graph for query-time decisions.

- The chango installer wires every Trino / Spark / Flink cluster to an Ontul endpoint + a long-lived access key (OTOK).
- Inside the engine, the first-party authz plugin (`chango-trino-authz`, `chango-spark-authz`, `chango-flink-authz`) calls `POST <ontul>/v1/api/authz/check-batch` for every query, with `(user, action, resource)` tuples and gets back `ALLOW` / `DENY` / `ABSTAIN` decisions.
- The same plugin then reports the outcome to Ontul's audit + lineage store (`POST <ontul>/v1/api/audit`, `/v1/api/lineage`) so activity from every engine is collected centrally. **Both allowed and denied accesses are audited** — a refused query is recorded with `decision=DENY` (and the refusal reason) before the plugin fails it, so a probing or misconfigured user leaves a trail. Lineage edges (`sources → target`) are emitted only for successful writes (CTAS / `INSERT`), never for a denied one. See [Data Lineage & Audit](lineage-audit.md) for what each event carries, the per-engine coverage differences, the `lineage.audit.enabled` switch, and how to verify it on a live cluster — and [Ontul Audit Log](https://cloudcheflabs.github.io/ontul-docs/1.0.0/features/audit-log/) for the collected schema and the `decision` field.

So chango's own IAM governs the admin UI and the REST API. Ontul's IAM governs query-time access to the data. Chango and Ontul are deliberately separate authorities — chango can be re-provisioned without invalidating Ontul tokens, and Ontul can be re-bootstrapped without re-issuing chango admin sessions.

## Engine coverage {#engine-coverage}

All three data-plane engines delegate to the same Ontul authz model, but they do **not** all enforce the same *granularity*. It depends on the plan-rewrite surface each engine exposes to its first-party plugin:

| Engine | Plugin | Granularity |
|---|---|---|
| Trino | `chango-trino-authz` | Allow / Deny **plus** row-filter (`Condition`) and column-mask (`Columns` / `MaskedColumns`), enforced by rewriting the query plan before execution. |
| Spark | `chango-spark-authz` | Table-level Allow / Deny on `data:Select` / `data:Insert`. |
| Flink | `chango-flink-authz` | Table-level Allow / Deny on `data:Select` / `data:Insert` — **no** row-filter or column-mask. |

Only Trino exposes a plan-rewrite hook the plugin can use to inject row filters and column masks without re-implementing Calcite. Spark and Flink authorize at the table level: a policy's `Condition` and `Columns` fields are simply ignored for those engines. For fine-grained control on a streaming (Flink) read, filter at the source instead — e.g. a topic-per-tenant layout with Kafka ACLs.

Ontul's **own** SQL engine (queries issued directly to Ontul over Arrow Flight SQL / REST, not through Trino/Spark/Flink) enforces the same policy graph, and does so fail-closed on both the tables a statement **reads** (`data:Select` on each source) and the table it **writes** — `INSERT` / `CREATE TABLE … AS SELECT` / `MERGE` need `data:Insert` on the target, `UPDATE` needs `data:Update`, `DELETE` needs `data:Delete`. A `data:Select` grant alone therefore never permits a write. See [Ontul IAM — query-time enforcement](https://cloudcheflabs.github.io/ontul-docs/1.0.0/features/iam/#query-time-enforcement-reads-and-writes) for the full read/write authorization matrix.

## Default bootstrap

On the very first start of a fresh cluster, the leader creates exactly one user / group / policy:

- User `admin` / password `admin` (must be changed on first login).
- Group `admin-group` with the `AdministratorAccess` policy attached (`Action: *`, `Resource: *`).
- The `admin` user belongs to `admin-group`.

If the leader's IAM RocksDB ever looks empty on a non-first boot (disk corruption, accidental wipe), chango **refuses to recreate the defaults** — your real IAM cannot be silently overwritten back to `admin/admin`. Restore from backup instead.

## Where state lives

IAM state is one of three RocksDB stores the chango master keeps locally:

- `<chango.base.data.dir>/master/iam` on a master (`chango.master.iam.rocksdb.path`) and
  `<chango.base.data.dir>/nm/iam` on a node manager (`chango.nm.iam.rocksdb.path`). With the
  packaged default `chango.base.data.dir = ./data` and an install at `/opt/chango`, the master's
  store is `/opt/chango/data/master/iam`. The two roles use separate sub-trees on purpose — they
  are co-located on most hosts and would otherwise contend for the same RocksDB `LOCK`.
- The store is plain RocksDB — no KMS envelope on read, since the leader needs synchronous access. Sensitive fields (password hashes, access key secrets) are stored hashed / encrypted at the field level.
- Followers and node managers cache the state and pull a fresh copy from the leader on every restart and on every change at runtime — single source of truth.

The IAM RocksDB is included in chango's [Backup & Restore](backup.md) artifact alongside the KMS and metadata RocksDB.

## REST surface

| Endpoint | Purpose |
|---|---|
| `POST /admin/api/auth/login` | Username + password → access + refresh token |
| `POST /admin/api/auth/refresh` | Refresh token → new access token |
| `POST /admin/api/auth/change-password` | Rotate the current user's password |
| `GET  /admin/api/iam/users` | List users |
| `POST /admin/api/iam/users` | Create user |
| `GET  /admin/api/iam/groups` | List groups |
| `POST /admin/api/iam/groups` | Create group |
| `GET  /admin/api/iam/policies` | List policies (full document) |
| `POST /admin/api/iam/policies` | Create policy |
| `POST /admin/api/iam/attach-group-policy` | Attach a policy to a group |
| `POST /admin/api/iam/add-user-to-group` | Add a user to a group |
| `POST /admin/api/iam/access-keys` | Issue an access key for a user |
| `POST /admin/api/sts/assume-role` | Issue short-lived credentials |

All routes (except `auth/login` and `auth/refresh`) require a Bearer access token. Mutating routes additionally require leader status — on a follower master the entire request is transparently forwarded to the leader (see [Leader Forwarding](leader-forward.md)).

## Stage-1 RBAC

The chango control plane currently runs in **Stage-1 RBAC** mode: an authenticated user is either **admin** (holds the `AdministratorAccess` policy directly or via a group) or **read-only**. Mutations and **secret-reveal `GET`s** — `iam/download-key/*`, `/password`, `/admin-password`, `/catalog-config`, `/catalog-connection` — are blocked for non-admins at the backend; the admin UI hides the corresponding buttons. Reads otherwise work for every authenticated user.

See [Role-Based Access (Stage 1)](role-based-access.md) for the full surface and the planned Stage-2 fine-grained model.
