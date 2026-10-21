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

### 1. Confirm the routing target

A Trino cluster installed by chango **registers itself** — the coordinator URL
is something chango already knows, so it is not worth retyping. Check it:

```bash
BASE=http://<master>:8080
TOK=$(curl -s -X POST $BASE/admin/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{"username":"admin","password":"…"}' | jq -r .accessToken)

curl -sS $BASE/admin/api/gateway/clusters -H "Authorization: Bearer $TOK"
#   [{"clusterName":"trino-main","clusterType":"trino",
#     "url":"http://<coordinator-host>:<httpPort>","activated":true}]
```

Register by hand only when the entry is absent — an **external** Trino cluster
chango did not install, or a cluster installed before the gateway existed. The
admin UI has the same thing under the gateway page's **Routing Targets**.

```bash
curl -sS -X POST $BASE/admin/api/gateway/clusters \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{
    "clusterName": "trino-main",
    "url": "http://<coordinator-host>:<httpPort>",
    "activated": true
  }'
```

!!! note "Registration is not membership"
    A registered cluster routes nothing until a cluster-group lists it (step 2).
    chango never creates or widens a group — not even `default`. Several Trino
    clusters can sit behind one gateway, so a new cluster quietly joining the
    group `admin` routes to would scatter operator queries across clusters sized
    for different work.

!!! warning "`activated` is the operator's drain switch"
    Turn it off and new queries go to the group's other clusters while running
    ones finish — that is how a backend is replaced without a maintenance
    window. **chango writes this field once, at registration, and never
    again**, so a cluster you drained stays drained. The one thing it keeps
    following is `url`, for when a coordinator moves; deleting the Trino
    cluster removes the entry.

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

Creating a cluster-group also creates an Ontul group of the same name (chango
writes to Ontul first and aborts if that fails, so the two cannot drift). Open
the **Ontul** admin UI, find that group, and add the users who should route
through it. A user in no group has no route.

Confirm the mirror landed:

```bash
curl -sS $BASE/admin/api/gateway/user-groups -H "Authorization: Bearer $TOK"
#   {"admin":["admin-group"],"analyst":["analyst-group"]}
```

!!! note "The group is created empty — membership is not permission"
    A group with no policy attached routes fine and then denies every table.
    `SELECT 1` succeeds, `SELECT … FROM <table>` is a `403`. Routing and
    authorization are separate axes: the cluster-group decides *which engine*,
    the policy decides *what is visible*.

    `default` is the group `admin` routes to and is deliberately left empty —
    the operator's own access comes from `admin-group`'s `AdministratorAccess`.
    Put users in purpose-built groups instead, so that separating a user-facing
    engine later does not move the operator path with it.

## The client surface — nginx, and it is always TLS

Clients do not talk to a gateway instance. They talk to an nginx surface in
front of the gateways, and **chango does not create it at install** — apply it
after the cluster is up.

```bash
curl -sS $BASE/admin/api/trino-gateway/<clusterId>/nginx -H "Authorization: Bearer $TOK"
#   gateways[] / nodeManagers[](nginxInstalled) / recommendedNode

curl -sS -X POST $BASE/admin/api/trino-gateway/<clusterId>/nginx \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"nodeId":"<nm nodeId>","listenPort":0,
       "gatewayInstanceIds":["tg-1-gateway-1","tg-1-gateway-2"]}'
#   nginxPort     19300
#   nginxApplied  host-a:8680,host-b:8680     ← should list every gateway
```

`listenPort: 0` auto-allocates from a dedicated band. A port given explicitly is
honoured only after it is confirmed free — nginx binding silently fails
otherwise, which leaves a surface that reports success and refuses connections.

TLS is not a choice here: **Trino's JDBC driver refuses to send Basic
credentials over plain HTTP**, so a plaintext surface cannot be used by the
clients that matter, and any tool that does connect sends access keys in the
clear. chango generates a self-signed certificate for the surface.

### Trusting the certificate

`curl -k` skips verification. Clients that cannot — the JDBC driver, the
workflow's SQL task — fail like this:

```
PKIX path building failed: unable to find valid certification path to requested target
```

That message reads like a wrong address or wrong credentials. It means the
client has nothing to verify against. Fetch the certificate and build a trust
store:

```bash
curl -sS $BASE/admin/api/trino-gateway/<clusterId>/nginx/certificate \
  -H "Authorization: Bearer $TOK"
#   {"endpoint":"https://<nginx host>:19300",
#    "certificate":"-----BEGIN CERTIFICATE-----…"}
```

The endpoint comes back with it because there are two distinct failures — "cannot
verify" and "verified, but reached by a name the certificate does not cover" —
and the certificate covers the host's FQDN, its address and `localhost`.

```bash
JDK=$(ls -d /opt/*jdk-17* | head -1)
sudo mkdir -p /etc/chango && sudo chmod 755 /etc/chango
sudo cp -n $JDK/lib/security/cacerts /etc/chango/truststore.jks   # copy, don't create
sudo chmod 644 /etc/chango/truststore.jks
sudo $JDK/bin/keytool -importcert -noprompt -trustcacerts \
     -alias chango-trino-gateway -file /tmp/gw.crt \
     -keystore /etc/chango/truststore.jks -storepass changeit
```

!!! warning "Copy `cacerts` — never hand a JVM an empty trust store"
    A fresh keystore holding only this certificate makes that JVM lose every
    public CA, and its other outbound HTTPS calls start failing quietly.

!!! danger "Not under `/opt/chango/conf`"
    On master nodes that directory is `750` — it holds the master key — so
    component accounts cannot read it. The JVM then falls back to an **empty**
    trust store and fails PKIX while the file plainly exists with a matching
    fingerprint. Only master nodes are affected, so it presents as an
    intermittent network problem:

    ```
    DAG run 1) SUCCESS  driver=worker-on-nm-only-node     ← conf is 755 there
    DAG run 2) FAILED   driver=worker-on-master-node
    DAG run 3) FAILED   driver=worker-on-master-node
    ```

    Keep it somewhere component accounts can read, and check as that account:
    `sudo -n -u kiok test -r /etc/chango/truststore.jks`.

Point the consuming component's JVM at it. For the workflow engine set **both**
roles — tasks execute on workers, and the master is on the path too:

```bash
curl -sS -X POST $BASE/admin/api/kiok/<clusterId>/config \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{
  "masterJvm":{"extra":{
    "-Djavax.net.ssl.trustStore":"/etc/chango/truststore.jks",
    "-Djavax.net.ssl.trustStorePassword":"changeit"}},
  "workerJvm":{"extra":{
    "-Djavax.net.ssl.trustStore":"/etc/chango/truststore.jks",
    "-Djavax.net.ssl.trustStorePassword":"changeit"}}}'
```

Verify by running the same job **several times**: one success only proves the
node it happened to land on. Every worker should appear as the driver.

Re-applying nginx reuses the existing certificate, so the fingerprint is stable
and trust stores stay valid. Deleting `/etc/nginx/ssl/<conf>.crt` and
re-applying generates a new one — rebuild the trust stores then.

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
| `GET` / `POST` | `/admin/api/trino-gateway/<id>/nginx` | The client surface — candidates, then apply |
| `GET` | `/admin/api/trino-gateway/<id>/nginx/certificate` | Its certificate + the endpoint it is valid for |
| `POST` | `/admin/api/trino-gateway/<id>/attached-groups` | Which groups this gateway serves — **replaces the whole list** |

!!! warning "`attached-groups` replaces, it does not add"
    Sending only the new group drops the others — including `default`, which
    stops operator queries. Send the full list every time.
