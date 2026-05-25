# Phase 0 — Foundation install

This phase brings up the four **foundation components** every later phase depends on.

| Component | Role | Depends on |
|---|---|---|
| **Ontul** | IAM authority — Trino / Spark / Flink delegate every authz decision to Ontul. | none (self-contained ZK bundle) |
| **PostgreSQL** | Polaris's metastore + Trino's Resource Group backend. | none |
| **ShannonStore** | S3-compatible object storage — Iceberg data + Trino exchange spill. | none |
| **Polaris** | Apache Polaris (Iceberg REST catalog). | PostgreSQL + ShannonStore |

The order matters — **Polaris only installs cleanly when PG + ShannonStore are RUNNING**. Ontul / PG / ShannonStore have no dependencies on each other so they could be installed in any order, but this tutorial follows the table order.

## Topology

The walk-through assumes a three-NM cluster (`n1`, `n2`, `n3`). To save resources we use the smallest number of instances each component supports.

| Component | Instances | Placement |
|---|---|---|
| Ontul | ZK x 1 + Master x 1 + Worker x 1 | ZK=n1, Master=n1, Worker=n2 |
| PostgreSQL | single instance `pg-main` | n3 |
| ShannonStore | ZK x 1 + API x 1 + Data x 3 + EC(2,1) | ZK=n1, API=n2, Data=n1·n2·n3 |
| Polaris | Server x 1 | n3 |

> Production placements are different — ZK 3 or 5, ShannonStore Data ≥ (k+m), Polaris at least 2 servers. The minimal layout here is verification-grade only; see [Components → Catalog](../components/catalog.md) for production guidance.

## Variables this phase needs

The [Tutorials overview](index.md#admin-token-setup) sets `BASE` and `TOK`. Pin the NM nodeIds too:

```bash
BASE=http://<master-host>:8080
TOK=<access token from the overview>

N1=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/node-managers \
       | jq -r '.[] | select(.host | endswith("n1") or endswith("n1.chango.private")) | .nodeId')
N2=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/node-managers \
       | jq -r '.[] | select(.host | endswith("n2") or endswith("n2.chango.private")) | .nodeId')
N3=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/node-managers \
       | jq -r '.[] | select(.host | endswith("n3") or endswith("n3.chango.private")) | .nodeId')
echo "N1=$N1   N2=$N2   N3=$N3"
```

## 1. Install Ontul

Ontul ships with its own bundled ZooKeeper. Its master key encrypts Ontul's own state and is **different** from the chango cluster master key — the operator generates it separately (32 chars or more).

### Via the chango admin UI

1. Open `http://<master-host>:8080/admin/` and sign in as the chango admin.
2. In the left sidebar's **Lakehouse Engines** group click **Ontul**.
3. Click **Install new Ontul cluster**. A modal opens with these fields:
    - **Cluster ID** — type `ontul-main`.
    - **Master key** — click **Generate** for a random 48-character URL-safe string. Copy it into your secret manager *before* you close the modal; chango stores it KMS-encrypted but never shows it again.
    - **ZooKeeper nodes** — pick `chango-n1`. (Odd count rule — 1, 3, or 5.)
    - **Master nodes** — pick `chango-n1`.
    - **Worker nodes** — pick `chango-n2`.
4. Click **Install**. The cluster card flips through `INSTALLING` → `STOPPED`.
5. Click the **Start** button on the cluster card. Each ZK / Master / Worker instance turns `RUNNING` over the next 1–3 minutes.

### Via REST

```bash
ONTUL_KEY=$(openssl rand -base64 48 | head -c 48)

curl -sS -X POST $BASE/admin/api/ontul \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"clusterId\":   \"ontul-main\",
    \"masterKey\":   \"$ONTUL_KEY\",
    \"zkNodes\":     [\"$N1\"],
    \"masterNodes\": [\"$N1\"],
    \"workerNodes\": [\"$N2\"]
  }"
```

> `ONTUL_KEY` is Ontul's KMS master key. **Move it into the same secret manager you used for `CHANGO_MASTER_KEY`** — every Ontul restart and every Ontul scale-out needs the same value.

### Wait for RUNNING

Component installs are asynchronous. Poll until every instance is `RUNNING`:

```bash
while true; do
  STATE=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/ontul | \
           jq -r '.[] | select(.clusterId=="ontul-main") | [.instances[].state] | unique | join(",")')
  echo "$(date +%T) ontul-main: $STATE"
  [ "$STATE" = "RUNNING" ] && break
  sleep 5
done
```

Typical time: 1–3 minutes. ZK must reach RUNNING before the master can join the quorum; the master must reach RUNNING before the worker registers.

### Mint an Ontul service token (OTOK)

Trino / Spark / Flink will need a long-lived **OTOK** to authenticate to Ontul. Mint it once now and save it.

#### Via the Ontul admin UI

1. From the chango admin UI's **Ontul** page, click the **Open admin UI** button on the `ontul-main` card. A new tab opens at `http://chango-n1:<adminPort>/admin/`.
2. The login screen accepts `admin` / `admin`. Submit it; you'll be redirected to a **Change password** form (the only allowed page until you rotate).
3. Enter the new admin password twice and submit. Log back in with the new password.
4. In the sidebar click **IAM → Users**. Click **New user** and create:
    - **Username** — `trino-system`
    - **Password** — any value (we won't use password-auth for this user)
5. Click into the new user, open the **Access keys** tab, click **Mint access key**:
    - **Lifetime** — `365d` (or longer; pick something you can rotate later)
    - **Description** — `chango service token for Trino/Spark/Flink → Ontul authz`
6. The dialog reveals the **Access key**, **Secret**, and **OTOK**. Copy the **OTOK** value — it's the only thing the downstream engines need — and stash it in your secret manager. Closing this dialog discards the secret view forever.

#### Via REST

```bash
# Find the Ontul master's admin port
ONTUL_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/ontul | \
              jq -r '.[] | select(.clusterId=="ontul-main") | .instances[] | select(.role=="MASTER") | .host')
ONTUL_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/ontul | \
              jq -r '.[] | select(.clusterId=="ontul-main") | .instances[] | select(.role=="MASTER") | .adminPort')

# Log in to Ontul's own admin (default admin/admin → forced password change on first
# login, identical flow to chango admin).
ONTUL_TOK=$(curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<ontul-admin-pw>"}' | jq -r .accessToken)

OTOK=$(curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/api/iam/access-keys \
        -H "Authorization: Bearer $ONTUL_TOK" \
        -H 'Content-Type: application/json' \
        -d '{"username":"trino-system","lifetime":"365d"}' | jq -r .otok)
echo "$OTOK" > ~/chango-secrets/ontul-otok-trino
```

> The OTOK is a *service token* used by Trino / Spark / Flink to call Ontul's authz endpoint. Treat it like any other long-lived credential and keep it in your secret manager.

## 2. Install PostgreSQL

A single instance `pg-main` on `n3`. Both Polaris and Trino RG will reuse it.

### Via the chango admin UI

1. In the sidebar's **Foundation** group click **PostgreSQL**.
2. Click **Install new PostgreSQL instance**:
    - **Instance ID** — `pg-main`
    - **Node** — `chango-n3`
    - **Port** — `5432`
    - **Superuser password** — click **Generate** for a strong random value. chango will envelope-encrypt it under the chango master key; you do not need to copy it out (downstream installers like Polaris pull it from chango automatically when you reference `pgInstanceId: pg-main`).
3. Click **Install** then **Start**. The card flips to `RUNNING` within ~30 seconds.

### Via REST

```bash
PG_PASSWORD=$(openssl rand -base64 24 | tr -d '/+' | head -c 24)

curl -sS -X POST $BASE/admin/api/postgres \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"instanceId\": \"pg-main\",
    \"nodeId\":     \"$N3\",
    \"port\":       5432,
    \"password\":   \"$PG_PASSWORD\"
  }"
```

Check:

```bash
curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/postgres | \
  jq '.[] | select(.instanceId=="pg-main") | {instanceId, state, host, port}'
# { "instanceId":"pg-main", "state":"RUNNING", "host":"chango-n3", "port":5432 }
```

> Chango envelope-encrypts the PostgreSQL superuser password under its own KMS. When you later install Polaris and pass `pgInstanceId: "pg-main"`, chango fills in the PG password itself — you never type it twice.

## 3. Install ShannonStore

S3-compatible object storage. We use EC(2,1) — 2 data shards + 1 parity shard — which means we need at least 3 Data nodes. Spread Data across `n1`, `n2`, `n3`.

### Via the chango admin UI

1. In the sidebar's **Foundation** group click **ShannonStore**.
2. Click **Install new ShannonStore cluster**:
    - **Cluster ID** — `shannon-main`
    - **Master key** — **Generate** for a random 48-char string. Stash it in your secret manager (separate from the Ontul key).
    - **ZooKeeper nodes** — `chango-n1`.
    - **API nodes** — `chango-n2`.
    - **Data nodes** — `chango-n1`, `chango-n2`, `chango-n3` (three for EC(2,1)).
    - **EC data shards / parity shards** — `2` / `1`.
3. Click **Install** then **Start**. The cluster card flips to `RUNNING` over the next 1–3 minutes.

### Via REST

```bash
SHANNON_KEY=$(openssl rand -base64 48 | head -c 48)

curl -sS -X POST $BASE/admin/api/clusters \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"clusterId\":      \"shannon-main\",
    \"masterKey\":      \"$SHANNON_KEY\",
    \"zkNodes\":        [\"$N1\"],
    \"apiNodes\":       [\"$N2\"],
    \"dataNodes\":      [\"$N1\", \"$N2\", \"$N3\"],
    \"ecDataShards\":   2,
    \"ecParityShards\": 1
  }"
```

Wait:

```bash
while true; do
  STATE=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/clusters | \
           jq -r '.[] | select(.clusterId=="shannon-main") | [.instances[].state] | unique | join(",")')
  echo "$(date +%T) shannon-main: $STATE"
  [ "$STATE" = "RUNNING" ] && break
  sleep 5
done
```

### Mint an S3 access key + create buckets

ShannonStore exposes its own admin REST on each API node's `adminPort` (separate from chango's admin REST). Polaris / Trino / Spark / Flink will all use the same access key pair against the same two buckets.

#### Via the ShannonStore admin UI

1. From the chango admin UI's **ShannonStore** page, click the **Open admin UI** button on `shannon-main`. A new tab opens at `http://<api-host>:<adminPort>/admin/`.
2. The login screen accepts `admin` / `admin`. Submit it; you'll be forced through the same change-password flow as Ontul. Set a strong password and re-login.
3. In the sidebar click **IAM → Access Keys**. Click **Mint access key** under user `admin`. The dialog reveals the **Access key** + **Secret** pair — copy both, you'll reuse them for Polaris (Step 4) and every later phase.
4. In the sidebar click **Browser → Buckets**. Click **New bucket** twice:
    - **Name** — `lakehouse` (the Iceberg warehouse root)
    - **Name** — `trino-exchange` (Trino's spill bucket; you'll wire it up in Phase 1)
5. Both buckets appear in the list with `0 objects`.

#### Via REST

```bash
# Pull the API + admin endpoints
SS_API_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/clusters/shannon-main | \
              jq -r '.nodes[] | select(.role=="api") | .nodeId as $n | .config.s3Port as $p
                     | "\(.nodeId) \(.config.s3Port) \(.config.adminPort)"' \
              | head -1)
read NM_ID SS_S3_PORT SS_ADMIN_PORT <<< "$SS_API_HOST"
SS_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/node-managers | \
           jq -r ".[] | select(.nodeId==\"$NM_ID\") | .host")
SS_ENDPOINT="http://$SS_HOST:$SS_S3_PORT"
SS_ADMIN="http://$SS_HOST:$SS_ADMIN_PORT"
echo "S3 endpoint: $SS_ENDPOINT"
echo "Admin endpoint: $SS_ADMIN"

# Log in to ShannonStore admin (default admin/admin → forced password change on first
# login). The login body field is userId (not username).
SS_ADMIN_TOK=$(curl -sS -X POST $SS_ADMIN/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"userId":"admin","password":"admin"}' | jq -r .token)

# Change the admin password first if requirePasswordChange came back true,
# then re-login with the new password. Same flow as chango admin.

# Mint an access key pair for the chango-managed lakehouse identity
read SS_AK SS_SK < <(curl -sS -X POST $SS_ADMIN/admin/iam/keys \
  -H "Authorization: Bearer $SS_ADMIN_TOK" \
  -H 'Content-Type: application/json' \
  -d '{"userId":"admin"}' | jq -r '"\(.accessKey) \(.secretKey)"')

# Create the two buckets we will use end-to-end
for b in lakehouse trino-exchange; do
  curl -sS -X POST $SS_ADMIN/admin/browser/buckets \
    -H "Authorization: Bearer $SS_ADMIN_TOK" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"$b\"}"
done
```

> ShannonStore IAM is independent of chango's IAM. The access key pair you just minted is the lakehouse-wide S3 credential — keep it in the same secret store you use for the chango master key.

## 4. Install Polaris

Wire PG metastore + ShannonStore S3 endpoint.

### Via the chango admin UI

1. In the sidebar's **Lakehouse Engines** group click **Polaris**.
2. Click **Install new Polaris cluster**:
    - **Cluster ID** — `polaris-main`
    - **Server nodes** — `chango-n3`
    - **PostgreSQL instance** — pick `pg-main` from the dropdown (chango injects the encrypted password automatically; you do not need to type it again).
    - **PG database** — `polaris` (chango creates it during install).
    - **S3 endpoint** — paste the ShannonStore S3 endpoint from Step 3 (e.g., `http://chango-n2.chango.private:8080`).
    - **S3 access key / secret key** — paste the AK/SK pair you minted in Step 3.
    - **S3 region** — `us-east-1`.
3. Click **Install** then **Start**. The cluster card flips to `RUNNING` within 1–2 minutes.

### Via REST

```bash
curl -sS -X POST $BASE/admin/api/polaris \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"clusterId\":    \"polaris-main\",
    \"serverNodes\":  [\"$N3\"],
    \"pgInstanceId\": \"pg-main\",
    \"pgDatabase\":   \"polaris\",
    \"s3Endpoint\":   \"$SS_ENDPOINT\",
    \"s3AccessKey\":  \"$SS_AK\",
    \"s3SecretKey\":  \"$SS_SK\",
    \"s3Region\":     \"us-east-1\"
  }"
```

Wait:

```bash
while true; do
  STATE=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/polaris | \
           jq -r '.[] | select(.clusterId=="polaris-main") | [.instances[].state] | unique | join(",")')
  echo "$(date +%T) polaris-main: $STATE"
  [ "$STATE" = "RUNNING" ] && break
  sleep 5
done
```

### Create the first catalog

A Polaris server can host many Iceberg catalogs. We use a single one called `lakehouse` for the rest of the tutorial.

#### Via the chango admin UI

1. From the chango admin UI's **Polaris** page, click into the `polaris-main` cluster card and open the **Catalogs** tab.
2. Click **New catalog**:
    - **Name** — `lakehouse`
    - **Storage type** — `S3`
    - **Default base location** — `s3://lakehouse/`
    - **S3 endpoint / access key / secret key / region** — same values you used to install Polaris (chango pre-fills them from the cluster's stored settings).
3. Click **Create**. The catalog appears in the list. Click **OAuth credential** to reveal the client id + secret pair (e.g. `polaris-root:<secret>`) — copy them; Phase 1 needs them to register the catalog in Trino.

#### Via REST

```bash
POLARIS_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/polaris | \
                jq -r '.[] | select(.clusterId=="polaris-main") | .instances[0].host')
POLARIS_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/polaris | \
                jq -r '.[] | select(.clusterId=="polaris-main") | .instances[0].catalogPort')

curl -sS -X POST $BASE/admin/api/polaris/polaris-main/catalogs \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"name\":               \"lakehouse\",
    \"storageType\":        \"S3\",
    \"defaultBaseLocation\": \"s3://lakehouse/\",
    \"s3Endpoint\":         \"$SS_ENDPOINT\",
    \"s3Region\":           \"us-east-1\",
    \"s3AccessKey\":        \"$SS_AK\",
    \"s3SecretKey\":        \"$SS_SK\"
  }"
```

Verify:

```bash
curl -sS http://$POLARIS_HOST:$POLARIS_PORT/api/management/v1/catalogs | jq '.catalogs[].name'
# "lakehouse"
```

## Phase 0 exit checklist

All four below must be RUNNING before moving to Phase 1.

```bash
# Cluster-shaped components (ontul / polaris / shannonstore-clusters)
for ep in ontul polaris clusters; do
  curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/$ep | \
    jq -r '.[] | "\(.clusterId)\t\(.status)"'
done
# Standalone (postgres)
curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/postgres | \
  jq -r '.[] | "\(.instanceId)\t\(.status)"'
```

Expected:

```
ontul-main      RUNNING
pg-main         RUNNING
shannon-main    RUNNING
polaris-main    RUNNING
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A component stuck at `FAILED_TO_START` | Tail `/var/log/chango/nodemanager.log` on the placement NM. The component's own stdout under `/opt/components/<instanceId>/logs/` has the real reason 99% of the time. |
| Polaris cannot connect to PG | Confirm chango's PG install accepts the NM subnet (chango defaults `pg_hba.conf` to `0.0.0.0/0 scram-sha-256`). If `password` was omitted in the PG install request, only local peer auth works and Polaris will fail. |
| ShannonStore never reaches RUNNING (Data nodes short) | `ecDataShards + ecParityShards` must be ≤ Data node count. The tutorial uses EC(2,1) → 3 Data nodes. |
| Ontul OTOK mint returns 401 | The Ontul admin password hasn't been changed yet. Log in to the Ontul master at `http://$ONTUL_HOST:$ONTUL_PORT/admin/` as `admin/admin`, change the password, retry. |

## Next

Continue with [Phase 1 — Trino + Iceberg + RBAC](phase-1-trino-iceberg-rbac.md).
