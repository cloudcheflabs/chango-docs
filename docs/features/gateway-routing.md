# Trino Gateway Routing

A [Trino Gateway](../components/catalog.md#trino-gateway) cluster installed by chango starts with **no routes**. Installing it puts the process on a host; it does not tell it which Trino clusters exist or who may reach them. Until the routing topology is registered, every query through the gateway fails — typically with a `401`, which reads like an authentication problem and is not one.

This is the step most often missed after an install, so it is worth being explicit about what has to exist and where each piece lives.

## Who owns what

The topology is split across two products, and that split is the thing to understand first.

| | Owned by | Managed through |
|---|---|---|
| Clusters — where a Trino coordinator is | **chango** | `/admin/api/gateway/clusters` |
| Cluster groups — which clusters a group of users may route to | **chango** | `/admin/api/gateway/cluster-groups` |
| Resource groups — query concurrency and memory limits | **chango** | `/admin/api/gateway/resource-groups` |
| **User → group membership** | **Ontul** | The Ontul admin UI |

chango master is the authoritative store for the first three. It persists them through the replicated metadata store (KMS-encrypted, leader-written, synced to followers) and the stateless gateway instances pull the assembled topology from `GET /api/v1/gateway/topology`.

Membership is different. It used to live in chango and no longer does:

!!! warning "User-group membership moved to Ontul"
    `POST` and `DELETE` on `/admin/api/gateway/user-groups` answer **`410 Gone`**:

    ```
    user-group assignment moved to ontul IAM — manage groups + membership
    via the ontul admin UI; chango mirrors them automatically
    ```

    Create the group in chango (`cluster-groups`), then add users to the matching Ontul group in the **Ontul** admin UI. chango mirrors the membership.

    `GET /admin/api/gateway/user-groups` still works and is the quickest way to see the mirrored result.

Creating a cluster-group in chango creates the corresponding Ontul group as a side effect, so the name is shared. Adding *people* to it is Ontul's job.

## Minimum viable topology

Three things, in this order.

### 1. Register the Trino cluster

The gateway needs a name and a URL. The name must match the chango Trino `clusterId`, because a cluster-group refers to clusters by that name.

```bash
BASE=http://<master>:8080
TOK=$(curl -s -X POST $BASE/admin/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{"username":"admin","password":"…"}' | jq -r .accessToken)

curl -sS -X POST $BASE/admin/api/gateway/clusters \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{
    "clusterName": "trino-main",
    "url": "http://<coordinator-host>:<httpPort>"
  }'
```

### 2. Create a cluster group

Every route needs at least one. Routing is owned by groups, not by raw `host:port` backends — a gateway with a registered cluster but no group still has nowhere to send a query.

```bash
curl -sS -X POST $BASE/admin/api/gateway/cluster-groups \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{
    "groupName": "default",
    "trinoClusterIds": ["trino-main"]
  }'
```

`trinoClusterIds` holds the names registered in step 1.

### 3. Add users to the group — in Ontul

Open the **Ontul** admin UI, find the group named `default`, and add the users who should route through it. A user in no group has no route.

Confirm the mirror landed:

```bash
curl -sS $BASE/admin/api/gateway/user-groups -H "Authorization: Bearer $TOK"
```

## Why a missing route looks like an auth failure

The gateway authenticates the caller first, then asks which cluster-group that identity belongs to, then routes. A user with valid credentials and no group membership fails at the second step — and the response the client sees is a `401`.

So when a freshly installed gateway rejects a correct username and password, check membership before checking the password. The [kiok tutorial](../tutorials/phase-7-kiok-dag-trino-ontul-via-gateway.md) walks the same path with a DAG in front of it.

## Resource groups

Optional. They cap concurrency and memory per group of queries:

```bash
curl -sS -X POST $BASE/admin/api/gateway/resource-groups \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"name": "adhoc", "…": "…"}'
```

Values are stored opaquely — chango persists whatever JSON is posted and hands it to the gateway, which owns the schema. Without a resource group the gateway applies its own defaults.

## Where the topology lives

Under `gateway.*` keys in the replicated metadata store:

| Key | Holds |
|---|---|
| `gateway.cluster.<name>` | Cluster JSON |
| `gateway.cgroup.<name>` | Cluster-group JSON |
| `gateway.rgroup.<name>` | Resource-group JSON |
| `gateway.usergroup.<user>` | The user's cluster-group name, mirrored from Ontul |

Two consequences worth knowing:

- It is **covered by the chango master backup**. A restored master brings its routing back with it — see [Backup & Restore](backup.md).
- It is **leader-written**. Mutating calls against a follower answer `421` with the leader's address rather than writing to a store that trails.

## API summary

| Method | Path | Notes |
|---|---|---|
| `GET` / `POST` / `DELETE` | `/admin/api/gateway/clusters[/<name>]` | Backend Trino clusters |
| `GET` / `POST` / `DELETE` | `/admin/api/gateway/cluster-groups[/<name>]` | Routing groups; POST also creates the Ontul group |
| `GET` / `POST` / `DELETE` | `/admin/api/gateway/resource-groups[/<name>]` | Concurrency / memory limits |
| `GET` | `/admin/api/gateway/user-groups` | Membership, mirrored from Ontul |
| ~~`POST` / `DELETE`~~ | ~~`/admin/api/gateway/user-groups`~~ | **`410 Gone`** — manage membership in Ontul |
