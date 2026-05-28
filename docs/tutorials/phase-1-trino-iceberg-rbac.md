# Phase 1 — Trino + Iceberg + RBAC

[Phase 0](phase-0-foundation.md) must be complete (Ontul + PG + ShannonStore + Polaris all RUNNING). In this phase you will:

1. Install a **Trino cluster** wired to ShannonStore exchange + PostgreSQL Resource Group + Ontul authz.
2. Put a **Trino Gateway** in front of it so clients have a single endpoint.
3. Confirm Polaris's `lakehouse` catalog auto-registers in Trino.
4. Run **complex Iceberg queries** — CTAS, MERGE, time travel, partition pruning, window functions, multi-way joins.
5. Verify **Ontul RBAC** is enforced through the Gateway, down to row and column level.

## Topology

| Component | Instances | Placement |
|---|---|---|
| Trino Coordinator | 1 | n1 |
| Trino Worker | 2 | n2, n3 |
| Trino Gateway | 1 | n1 |

> Production layouts give the coordinator its own host, run more workers, and run at least two Gateway instances. The layout below is the verification-grade minimum.

## Variables carried over from Phase 0

```bash
BASE=http://<master-host>:8080
TOK=<token from the overview>
N1=nm-chango-n1-19998
N2=nm-chango-n2-19998
N3=nm-chango-n3-19998

# From Phase 0
OTOK=<ontul service token>
SS_ENDPOINT=http://<api-host>:<api-port>
SS_AK=<shannonstore access key>
SS_SK=<shannonstore secret key>
```

## 1. Install the Trino cluster

### Via the chango admin UI

1. In the sidebar's **Lakehouse Engines** group click **Trino**.
2. Click **Install new Trino cluster**:
    - **Cluster ID** — `trino-main`
    - **Coordinator nodes** — `chango-n1`
    - **Worker nodes** — `chango-n2`, `chango-n3`
    - **Query memory** — `4GB` total, `1GB` per node
    - **Retry policy** — `QUERY` (enables fault-tolerant execution)
    - **Exchange manager** — toggle **Enable**. Fill the exchange S3 panel:
        - **Base directory** — `s3://trino-exchange/`
        - **S3 endpoint / region / access key / secret key** — values from Phase 0 (the ShannonStore AK/SK pair).
    - **Ontul authz token** — paste the **OTOK** you minted in Phase 0 (the `trino-system` user's OTOK). chango auto-discovers the Ontul authz endpoint from the running `ontul-main` cluster.
    - **Resource group** — toggle **Enable**:
        - **PostgreSQL instance** — pick `pg-main`. chango re-uses its stored superuser password to create the `trino_rg` database + a `trino` login role automatically — you don't type a PG admin password.
        - **DB name** — `trino_rg`, **DB user** — `trino`, **DB password** — click **Generate** for a strong random value.
3. Click **Install** then **Start**. The cluster card flips to `RUNNING` over the next 1–3 minutes.

### Via REST

```bash
curl -sS -X POST $BASE/admin/api/trino \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"clusterId\":             \"trino-main\",
    \"coordinatorNodes\":      [\"$N1\"],
    \"workerNodes\":           [\"$N2\", \"$N3\"],
    \"queryMaxMemory\":        \"4GB\",
    \"queryMaxMemoryPerNode\": \"1GB\",
    \"retryPolicy\":           \"QUERY\",

    \"exchangeManagerEnabled\": true,
    \"exchangeBaseDirectory\":  \"s3://trino-exchange/\",
    \"exchangeS3Endpoint\":     \"$SS_ENDPOINT\",
    \"exchangeS3Region\":       \"us-east-1\",
    \"exchangeS3AccessKey\":    \"$SS_AK\",
    \"exchangeS3SecretKey\":    \"$SS_SK\",

    \"ontulAuthzToken\":       \"$OTOK\",

    \"resourceGroupEnabled\":      true,
    \"resourceGroupPgInstanceId\": \"pg-main\",
    \"resourceGroupDbName\":       \"trino_rg\",
    \"resourceGroupDbUser\":       \"trino\",
    \"resourceGroupDbPassword\":   \"<rg-password>\"
  }"
```

What each block means:

| Field group | Effect |
|---|---|
| `exchangeManagerEnabled` + `exchange*` | Fault-tolerant execution spills to `s3://trino-exchange/` on ShannonStore. A coordinator or worker crash no longer fails the query — it retries. |
| `ontulAuthzToken` | The coordinator's `chango-trino-authz` SystemAccessControl plugin authenticates to Ontul with this OTOK. The Ontul endpoint itself is auto-discovered from the running `ontul-main` master. |
| `resourceGroup*` + `resourceGroupPgInstanceId=pg-main` | Chango knows `pg-main`'s superuser password, creates `trino_rg` database + a `trino` login role itself, and wires the coordinator's `resource-groups.properties`. The operator never types a PG admin password. |

Wait for RUNNING and pin the coordinator host/port:

```bash
while true; do
  STATE=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/trino | \
           jq -r '.[] | select(.clusterId=="trino-main") | [.instances[].state] | unique | join(",")')
  echo "$(date +%T) trino-main: $STATE"
  [ "$STATE" = "RUNNING" ] && break
  sleep 5
done

COORD_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/trino | \
              jq -r '.[] | select(.clusterId=="trino-main") | .instances[] | select(.role=="COORDINATOR") | .host')
COORD_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/trino | \
              jq -r '.[] | select(.clusterId=="trino-main") | .instances[] | select(.role=="COORDINATOR") | .httpPort')
echo "coordinator: $COORD_HOST:$COORD_PORT"
```

## 2. Install Trino Gateway

### Via the chango admin UI

1. In the sidebar's **Lakehouse Engines** group click **Trino Gateway**.
2. Click **Install new Trino Gateway cluster**:
    - **Cluster ID** — `trino-gw`
    - **Gateway nodes** — `chango-n1`
    - **JVM Heap (optional)** — leave blank for the launcher defaults, or set `-Xms` / `-Xmx` (e.g. `256m` / `512m`) which chango writes into the gateway's `conf/jvm.conf` and sources via `JAVA_OPTS` at start.
3. Click **Install** then **Start**. The cluster card flips to `RUNNING` within ~30 seconds.
4. Open the cluster detail and the **Cluster Groups** sub-page; create a `default` cluster-group that contains `trino-main`. **Every Gateway route needs at least one cluster-group** — routing topology is owned by `default` (and any other groups you attach), not by raw `host:port` backends. Also register the gateway-side cluster entry under `/admin/api/gateway/clusters` with `clusterName: trino-main` (matching the chango Trino clusterId) and `url: http://<coord-host>:<httpPort>` — the cluster-group's `trinoClusterIds` list looks the cluster up by that name.

### Via REST

```bash
curl -sS -X POST $BASE/admin/api/trino-gateway \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"clusterId\":     \"trino-gw\",
    \"gatewayNodes\":  [\"$N1\"]
  }"

# Register trino-main in gateway/clusters + add it to cluster-group 'default'.
curl -sS -X POST $BASE/admin/api/gateway/clusters \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d "{\"clusterName\":\"trino-main\",\"clusterType\":\"trino\",
       \"url\":\"http://$COORD_HOST:$COORD_PORT\",
       \"activated\":true,\"groupName\":\"default\"}"
curl -sS -X POST $BASE/admin/api/gateway/cluster-groups \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"groupName":"default","trinoClusterIds":["trino-main"]}'
```

> The legacy `trinoBackends` field (a raw `host:port` CSV on the install body) was removed — routing is now driven entirely by cluster-groups + the registered gateway clusters that share their `clusterName` with the chango Trino `clusterId`. Each Gateway's `attachedClusterGroups` setting (defaults to `default`) controls which groups it serves.

Pin the Gateway endpoint — this is what every client uses from now on:

```bash
GW_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/trino-gateway | \
           jq -r '.[] | select(.clusterId=="trino-gw") | .instances[0].host')
GW_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/trino-gateway | \
           jq -r '.[] | select(.clusterId=="trino-gw") | .instances[0].listenPort')
echo "gateway: $GW_HOST:$GW_PORT"
```

## 3. Register the Polaris catalog in Trino

The Polaris `lakehouse` catalog **does not auto-register in Trino**. Apply the catalog explicitly so Trino loads its `etc/catalog/iceberg.properties`. Chango ships a one-shot REST that pulls the OAuth client and endpoint from the running Polaris cluster, writes the properties file on every Trino node, and rolling-restarts the cluster.

### 3.1 Read the Polaris connection

```bash
curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/polaris/polaris-main/credentials
# {
#   "clientId":            "polaris-root",
#   "clientSecret":        "...",
#   "realm":               "polaris-main",
#   "icebergRestEndpoint": "http://chango-n2.chango.private:8180/api/catalog",
#   "managementEndpoint":  "http://chango-n2.chango.private:8180/api/management/v1",
#   "oauthTokenEndpoint":  "http://chango-n2.chango.private:8180/api/catalog/v1/oauth/tokens"
# }
```

### 3.2 Build the Iceberg catalog properties

Replace the placeholders with the Polaris connection values + the ShannonStore S3 credentials minted in Phase 0:

```bash
POLARIS_REST=http://chango-n2.chango.private:8180/api/catalog
CLIENT_SECRET=<clientSecret from above>

PROPS="connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=$POLARIS_REST
iceberg.rest-catalog.warehouse=lakehouse
iceberg.rest-catalog.security=OAUTH2
iceberg.rest-catalog.oauth2.credential=polaris-root:$CLIENT_SECRET
iceberg.rest-catalog.oauth2.scope=PRINCIPAL_ROLE:ALL
fs.native-s3.enabled=true
s3.endpoint=$SS_ENDPOINT
s3.region=us-east-1
s3.aws-access-key=$SS_AK
s3.aws-secret-key=$SS_SK
s3.path-style-access=true"
```

### 3.3 Apply the catalog to Trino

#### Via the chango admin UI

1. From the chango admin UI's **Trino** page, click into the `trino-main` cluster card and open the **Catalogs** tab.
2. Click **Add catalog**:
    - **Name** — `iceberg`
    - **Properties** — paste the full multi-line `iceberg.properties` body from above into the text area.
3. Click **Apply**. The card shows a rolling-restart progress bar. After ~30 seconds the catalog appears in the list.

#### Via REST

```bash
jq -n --arg props "$PROPS" \
    '{op:"add", name:"iceberg", properties:$props}' \
  | curl -sS -X POST $BASE/admin/api/trino/trino-main/catalog \
      -H "Authorization: Bearer $TOK" \
      -H 'Content-Type: application/json' \
      -d @-
```

Chango writes `etc/catalog/iceberg.properties` to every coordinator + worker and rolling-restarts the cluster. After ~30 seconds the new catalog is visible.

### 3.4 Verify

```bash
trino --server http://$COORD_HOST:$COORD_PORT --user admin --execute 'SHOW CATALOGS'
# "iceberg"
# "jmx"
# "system"
# "tpcds"
# "tpch"
```

> **Trino CLI binary** — Trino's Maven coordinates use the latest stable line. Replace `<v>` with the published version (e.g. `470`):
> `curl -L -o /usr/local/bin/trino https://repo1.maven.org/maven2/io/trino/trino-cli/<v>/trino-cli-<v>-executable.jar && chmod +x /usr/local/bin/trino`

> **Trino Gateway routing model** — the Gateway picks a backend Trino coordinator per query in three steps:
>
> 1. The submitting user's Ontul IAM group membership is read from the topology snapshot (Ontul is the source of truth — chango master mirrors it via the periodic sync).
> 2. That ordered group list is intersected with the chango **cluster-groups** present in the topology. The first match wins. If none matches, the Gateway falls back to a cluster-group literally named `default` when one exists.
> 3. The picked cluster-group's `trinoClusterIds` list is consulted; an active member backend is chosen and the query is forwarded to it.
>
> A fresh chango install has zero cluster-groups, so every Gateway request fails with `no cluster-group matches user '<user>'`. Before pointing clients at the Gateway, register at least one cluster-group through `POST /admin/api/gateway/cluster-groups` (or the admin UI's **Trino Gateway → Cluster Groups** page). The chango master mirrors that group to Ontul automatically — you do **not** manage the Ontul group separately.
>
> ```bash
> curl -sS -X POST -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
>   $BASE/admin/api/gateway/cluster-groups \
>   -d '{"groupName":"default","description":"Default","trinoClusterIds":["trino-main"]}'
> ```
>
> Until that POST returns 200, query the Trino coordinator directly using `$COORD_HOST:$COORD_PORT`.

> **Per-gateway routing scope** — each Trino Gateway cluster can optionally restrict itself to a subset of cluster-groups (the admin UI's **Trino Gateway → cluster detail → Attached Cluster Groups** panel, or `POST /admin/api/trino-gateway/<id>/attached-groups`). When the attached list is empty the Gateway routes every group in the topology; when it is non-empty, only those groups can route through this Gateway. Leaving it empty is the right default for a single-Gateway tenant; tighten it when fronting multiple Gateways with different routing responsibilities.

## 4. Complex Iceberg queries

Every SQL below runs through Trino. Use the coordinator endpoint directly while you have not configured Trino Gateway cluster groups yet — once those are configured, swap `$COORD_HOST:$COORD_PORT` for `$GW_HOST:$GW_PORT` and the same queries work unchanged.

```bash
trino --server http://$COORD_HOST:$COORD_PORT --user admin \
      --catalog iceberg
```

> Pipe each block below into a here-doc or save to a `.sql` file and run with `trino -f <file>` — Trino's SQL uses **single-quoted string literals**, which the shell often mangles in `--execute "..."` form. The `.sql` file form is robust.

### 4.1 Schema + table with partitioning and nested types

```sql
CREATE SCHEMA IF NOT EXISTS sales;

CREATE TABLE sales.orders (
    order_id      BIGINT,
    customer_id   BIGINT,
    order_ts      TIMESTAMP(6) WITH TIME ZONE,
    country       VARCHAR,
    items         ARRAY(ROW(sku VARCHAR, qty INTEGER, price DECIMAL(10,2))),
    total_amount  DECIMAL(12,2)
)
WITH (
    partitioning = ARRAY['country', 'day(order_ts)'],
    format       = 'PARQUET'
);
```

### 4.2 Multi-row INSERT

```sql
INSERT INTO sales.orders VALUES
  (1, 100, TIMESTAMP '2026-05-20 09:15:00 UTC', 'KR',
     ARRAY[ROW('SKU-A', 2, 12.50), ROW('SKU-B', 1, 33.00)], 58.00),
  (2, 101, TIMESTAMP '2026-05-20 13:42:00 UTC', 'KR',
     ARRAY[ROW('SKU-A', 1, 12.50)], 12.50),
  (3, 200, TIMESTAMP '2026-05-21 08:00:00 UTC', 'JP',
     ARRAY[ROW('SKU-C', 3, 9.90)],  29.70),
  (4, 200, TIMESTAMP '2026-05-22 17:30:00 UTC', 'JP',
     ARRAY[ROW('SKU-B', 5, 33.00)], 165.00);
```

### 4.3 CTAS (Create Table As Select)

```sql
CREATE TABLE sales.daily_country_revenue
WITH (partitioning = ARRAY['country']) AS
SELECT
    country,
    date(order_ts AT TIME ZONE 'UTC')      AS d,
    SUM(total_amount)                      AS revenue,
    COUNT(*)                               AS orders,
    APPROX_PERCENTILE(total_amount, 0.95)  AS p95
FROM sales.orders
GROUP BY country, date(order_ts AT TIME ZONE 'UTC');

SELECT * FROM sales.daily_country_revenue ORDER BY country, d;
```

Expected:

```
 country |     d      | revenue | orders |  p95
---------+------------+---------+--------+-------
 JP      | 2026-05-21 |  29.70  |   1    | 29.70
 JP      | 2026-05-22 | 165.00  |   1    | 165.00
 KR      | 2026-05-20 |  70.50  |   2    | 58.00
```

### 4.4 MERGE (upsert)

```sql
CREATE TABLE sales.customer_totals (
    customer_id  BIGINT,
    total_spent  DECIMAL(14,2)
);

INSERT INTO sales.customer_totals VALUES (100, 100.00), (200, 50.00);

MERGE INTO sales.customer_totals t
USING (
    SELECT customer_id, SUM(total_amount) AS spent
    FROM sales.orders
    GROUP BY customer_id
) s ON t.customer_id = s.customer_id
WHEN MATCHED     THEN UPDATE SET total_spent = t.total_spent + s.spent
WHEN NOT MATCHED THEN INSERT (customer_id, total_spent) VALUES (s.customer_id, s.spent);

SELECT * FROM sales.customer_totals ORDER BY customer_id;
```

### 4.5 Window functions

```sql
SELECT
    order_id,
    customer_id,
    total_amount,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_ts) AS purchase_seq,
    SUM(total_amount)
        OVER (PARTITION BY customer_id ORDER BY order_ts
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)     AS cumulative_total
FROM sales.orders
ORDER BY customer_id, order_ts;
```

### 4.6 Partition pruning

```sql
EXPLAIN
SELECT * FROM sales.orders
WHERE country = 'KR'
  AND order_ts >= TIMESTAMP '2026-05-20 00:00:00 UTC'
  AND order_ts <  TIMESTAMP '2026-05-21 00:00:00 UTC';
```

Look for a `ScanFilterProject` node with something like:

```
predicate           = (country = VARCHAR 'KR') AND ...
filtered partitions : 1
```

That confirms Trino pruned the `country` + `day(order_ts)` partitions instead of scanning the whole table.

### 4.7 Time travel

```sql
-- List snapshots — column names match Iceberg's snapshots metadata table
SELECT snapshot_id, committed_at, operation
FROM sales."orders$snapshots"
ORDER BY committed_at DESC;

-- Query an older snapshot (e.g. the one before the latest INSERT)
SELECT COUNT(*) FROM sales.orders FOR VERSION AS OF <snapshot_id>;
-- "0"

-- Or by timestamp
SELECT COUNT(*) FROM sales.orders FOR TIMESTAMP AS OF TIMESTAMP '2026-05-22 00:00:00 UTC';
```

### 4.8 Schema evolution

```sql
ALTER TABLE sales.orders ADD COLUMN promo_code VARCHAR;

INSERT INTO sales.orders (order_id, customer_id, order_ts, country, items, total_amount, promo_code)
VALUES (5, 100, TIMESTAMP '2026-05-23 11:00:00 UTC', 'KR',
        ARRAY[ROW('SKU-D', 1, 99.99)], 99.99, 'SUMMER10');

SELECT order_id, promo_code FROM sales.orders WHERE promo_code IS NOT NULL;
```

The new column is NULL for the existing rows — Iceberg handles this with a metadata-only change.

### 4.9 Multi-way join (CTE + 4-way join)

Trino's planner rejects correlated subqueries in `JOIN ... ON` (`Given correlated subquery is not supported`). Use a `DISTINCT` mapping CTE instead — semantically identical, planner-friendly:

```sql
WITH
order_summary AS (
    SELECT customer_id, SUM(total_amount) AS spent, COUNT(*) AS n_orders
    FROM sales.orders
    GROUP BY customer_id
),
cust_country AS (
    SELECT DISTINCT customer_id, country FROM sales.orders
)
SELECT
    t.customer_id, t.total_spent, s.n_orders, d.country, d.revenue
FROM sales.customer_totals t
JOIN order_summary s   ON t.customer_id = s.customer_id
JOIN cust_country  c   ON c.customer_id = t.customer_id
JOIN sales.daily_country_revenue d ON d.country = c.country
ORDER BY t.total_spent DESC;
```

Expected: 4 rows joining `customer_totals × order_summary × cust_country × daily_country_revenue`.

## 5. Ontul RBAC

Create two users in Ontul — `analyst-kr` (only KR rows) and `analyst-jp` (only JP rows) — and prove the Gateway enforces it.

Ontul exposes its admin REST on the master's `adminPort` — discovered from `chango admin REST` at `/admin/api/ontul/<id>` and reachable directly from the chango cluster network. Default admin credentials are `admin/admin` with a forced first-login password change (same flow as chango).

### Via the Ontul admin UI

Sections 5.1 + 5.2 below are easiest to do click-by-click in Ontul's own admin UI (sidebar **IAM → Users / Groups / Policies**), so this UI subsection covers them both:

1. From the chango admin UI's **Ontul** page click **Open admin UI** on `ontul-main`. Sign in with the admin password you set in Phase 0.
2. **IAM → Users** → **New user** → `analyst-kr` / a password → **Save**. Repeat for `analyst-jp`.
3. **IAM → Groups** → **New group** → `analyst-kr-grp` → **Save**. Repeat for `analyst-jp-grp`. On each group's detail page click **Add user** to put the matching `analyst-*` user in.
4. **IAM → Policies** → **New policy** → paste the Statement document below (Section 5.2 shows the JSON for `sales-kr-read`). Repeat for `sales-jp-read`, swapping `'KR'` → `'JP'` in the Condition.
5. Back on each group's detail page click **Attach policy** and pick the matching `sales-*-read` policy.

You can verify the policy attachment by clicking the group → **Effective permissions** tab, which shows the merged statements.

### Via REST

```bash
# Ontul admin endpoints
ONTUL_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/ontul/ontul-main \
              | jq -r '.nodes[] | select(.role=="master") | .nodeId' \
              | xargs -I {} curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/node-managers \
              | jq -r ".[] | select(.nodeId==\"{}\") | .host")
ONTUL_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/ontul/ontul-main \
              | jq -r '.nodes[] | select(.role=="master") | .config.adminPort')
ONTUL=http://$ONTUL_HOST:$ONTUL_PORT

# First login + change password
ONTUL_TOK=$(curl -sS -X POST $ONTUL/admin/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}' | jq -r .accessToken)
curl -sS -X POST $ONTUL/admin/auth/change-password \
  -H "Authorization: Bearer $ONTUL_TOK" -H 'Content-Type: application/json' \
  -d '{"oldPassword":"admin","newPassword":"<ontul-admin-pw>"}'
ONTUL_TOK=$(curl -sS -X POST $ONTUL/admin/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"<ontul-admin-pw>"}' | jq -r .accessToken)
```

### 5.1 Create user + group

```bash
curl -sS -X POST $ONTUL/admin/iam/users \
  -H "Authorization: Bearer $ONTUL_TOK" -H 'Content-Type: application/json' \
  -d '{"username":"analyst-kr","password":"analyst-kr-pw"}'

curl -sS -X POST $ONTUL/admin/iam/groups \
  -H "Authorization: Bearer $ONTUL_TOK" -H 'Content-Type: application/json' \
  -d '{"groupName":"analyst-kr-grp"}'

curl -sS -X POST $ONTUL/admin/iam/add-user-to-group \
  -H "Authorization: Bearer $ONTUL_TOK" -H 'Content-Type: application/json' \
  -d '{"username":"analyst-kr","groupName":"analyst-kr-grp"}'
```

### 5.2 Create a row-filter policy (AWS-style document)

#### Ontul IAM policy JSON schema in detail

Ontul policies adopt the **AWS IAM policy document** shape — a top-level `Version` + a list of `Statement` blocks. The chango-trino-authz plugin reads the user's effective policies (union of every policy attached to every group the user is in), evaluates them per resource on each query, and either allows / denies / rewrites the plan.

> **Field names are case-sensitive PascalCase** — `Version`, `Statement`, `Sid`, `Effect`, `Action`, `Resource`, `Condition`, `Columns`. Lowercase variants are silently ignored by the Jackson deserializer, which is the most common policy-create pitfall (a `policies` GET returns the policy with every PascalCase field `null` when this happens, because the deserializer never populated them). The REST envelope `{name, document}` itself uses lowercase keys (`name`, `document`) — the PascalCase rule applies inside `document`.

##### Top-level envelope (what `POST /admin/iam/policies` accepts)

```json
{
  "name":     "<policy-name>",
  "document": { ... AWS-IAM-style document ... }
}
```

| Field | Meaning |
|---|---|
| `name` | Unique policy name inside the tenant. Used by `attach-group-policy` / `attach-user-policy`. |
| `document` | The IAM-style document below. Stored as-is and re-evaluated on every query. |

##### Document body

```json
{
  "Version":   "2024-01-01",
  "Statement": [
    {
      "Sid":       "<human label>",
      "Effect":    "Allow" | "Deny",
      "Action":    ["data:Select", "data:Insert", ...],
      "Resource":  "data:table:iceberg.sales.*",
      "Columns":   ["order_id", "country"],
      "Condition": "country = 'KR'"
    },
    ...more statements...
  ]
}
```

| Field | Required | Type | Notes |
|---|---|---|---|
| `Version` | yes | string | `2024-01-01` — schema version Ontul understands today. |
| `Statement` | yes | array | One or more statement blocks. Statements are evaluated in array order; a `Deny` anywhere wins over any `Allow`. |
| `Sid` | optional | string | Statement label — surfaces in audit logs. Free-form text. |
| `Effect` | yes | enum | `Allow` or `Deny`. With no statement matching a request → **ABSTAIN** → fail-closed (request denied). |
| `Action` | yes | string \| array | One or more action verbs scoped to the chango authz space — see action catalog below. Wildcard `*` matches every action. |
| `Resource` | yes | string \| array | One or more **resource paths** in the form `<category>:<kind>:<dotted name>`. See resource grammar below. Wildcard `*` segments allowed. |
| `Condition` | optional | string | A SQL `WHERE` fragment chango-trino-authz **injects** into every query touching `Resource`. Use to row-filter (e.g. `country = 'KR'`). |
| `Columns` | optional | array | Whitelist of columns the user may project / filter on for `Resource`. Other columns are masked / removed from the plan. |

##### Action catalog (the common ones)

Actions are prefixed by category — `data:` for SQL/table actions, `admin:` for IAM mutations, `dag:` for kiok.

| Action | Surface |
|---|---|
| `data:Select` | SQL `SELECT` against a table / view. |
| `data:Insert` | `INSERT`. |
| `data:Update` | `UPDATE` / `MERGE` update branch. |
| `data:Delete` | `DELETE` / `MERGE` delete branch. |
| `data:Create` | `CREATE TABLE` (column DDL). |
| `data:Drop` | `DROP TABLE`. |
| `data:CreateSchema` / `data:DropSchema` | namespace / schema DDL. |
| `data:CreateCatalog` / `data:DropCatalog` | catalog-level DDL (rare; reserved for admins). |
| `*` | every action — used by `AdministratorAccess`. |

##### Resource grammar

```
<category>:<kind>:<dotted name>
```

| Category | Kind | Example | Matches |
|---|---|---|---|
| `data` | `catalog` | `data:catalog:iceberg` | the catalog itself (e.g. for `data:CreateSchema`). |
| `data` | `schema`  | `data:schema:iceberg.test` | one schema. |
| `data` | `table`   | `data:table:iceberg.test.orders` | one table. |
| `data` | `table`   | `data:table:iceberg.test.*` | every table in `iceberg.test`. |
| `data` | `table`   | `data:table:iceberg.*.*` | every table in every schema under `iceberg`. |
| `data` | `*`       | `data:*:iceberg.test.*` | every kind in `iceberg.test`. |
| `*`    | `*`       | `*` | everything (admin). |

Wildcards `*` are allowed in **path segments**, not in the middle of a name (`iceberg.te*` is not supported).

##### Evaluation flow (per query, per resource)

1. Trino coordinator computes the set of resources a query touches (catalogs, schemas, tables, columns).
2. chango-trino-authz asks Ontul: *"may user `<u>` perform `<action>` on `<resource>`?"* for each (action, resource) pair.
3. Ontul walks every statement of every policy attached to every group `<u>` is in:
    - Statement matches if `Action` ∋ action **and** `Resource` ∋ resource.
    - Matching `Deny` → immediate **Deny**.
    - Matching `Allow` → record. Later statements still evaluated for `Deny` overrides.
4. After all statements: any `Allow` recorded → **Allow** (with optional `Condition` injected, `Columns` projection enforced). No statements matched → **ABSTAIN** → fail-closed.

##### Worked examples

**(a) Read-only on one namespace** — `alice` may `SELECT` from anything under `iceberg.test`, nothing else:

```json
{
  "name": "iceberg-test-read",
  "document": {
    "Version": "2024-01-01",
    "Statement": [{
      "Sid":      "IcebergTestRead",
      "Effect":   "Allow",
      "Action":   ["data:Select"],
      "Resource": "data:table:iceberg.test.*"
    }]
  }
}
```

**(b) Read + write on the same namespace, plus the schema DDL** — `spark` (the OS user the kiok DAGs run as) needs to create the schema first and then `INSERT`:

```json
{
  "name": "iceberg-test-write",
  "document": {
    "Version": "2024-01-01",
    "Statement": [
      {
        "Sid":      "IcebergTestWrite",
        "Effect":   "Allow",
        "Action":   ["data:Select", "data:Insert", "data:Update",
                     "data:Delete", "data:Create", "data:Drop"],
        "Resource": "data:table:iceberg.test.*"
      },
      {
        "Sid":      "IcebergTestSchema",
        "Effect":   "Allow",
        "Action":   ["data:CreateSchema", "data:DropSchema"],
        "Resource": "data:schema:iceberg.test"
      }
    ]
  }
}
```

**(c) Row-filter policy** — `analyst-kr` may read sales rows for Korea only. The `Condition` clause is appended as a `WHERE` predicate to every query that touches `iceberg.sales.*`:

```json
{
  "name": "sales-kr-read",
  "document": {
    "Version": "2024-01-01",
    "Statement": [{
      "Sid":       "SalesKrRead",
      "Effect":    "Allow",
      "Action":    ["data:Select"],
      "Resource":  "data:table:iceberg.sales.*",
      "Condition": "country = 'KR'"
    }]
  }
}
```

A Trino `SELECT * FROM iceberg.sales.orders` issued as `analyst-kr` becomes `SELECT * FROM iceberg.sales.orders WHERE country = 'KR'` server-side. The user cannot see other countries, even with `WHERE country = 'JP'` typed manually (the chango-rewritten predicate `AND` s onto whatever the user wrote).

**(d) Column whitelist (column-mask)** — `analyst-kr` may read only three columns; `customer_id` is hidden:

```json
{
  "name": "sales-kr-read-cols",
  "document": {
    "Version": "2024-01-01",
    "Statement": [{
      "Sid":       "SalesKrReadCols",
      "Effect":    "Allow",
      "Action":    ["data:Select"],
      "Resource":  "data:table:iceberg.sales.orders",
      "Columns":   ["order_id", "country", "total_amount"],
      "Condition": "country = 'KR'"
    }]
  }
}
```

`SELECT *` returns only the three whitelisted columns. `SELECT customer_id FROM ...` returns `Access Denied: column customer_id not authorized`.

**(e) Allow + Deny on the same target** — `auditor` may read every sales table, but never `iceberg.sales.salary` even though it matches the broader Allow:

```json
{
  "name": "auditor-sales-read",
  "document": {
    "Version": "2024-01-01",
    "Statement": [
      { "Sid": "BroadRead",  "Effect": "Allow",
        "Action": ["data:Select"], "Resource": "data:table:iceberg.sales.*" },
      { "Sid": "BlockSalary", "Effect": "Deny",
        "Action": ["data:Select"], "Resource": "data:table:iceberg.sales.salary" }
    ]
  }
}
```

Because `Deny` short-circuits, the order of statements does not matter — `Deny` always wins.

**(f) Administrator** — the seeded `AdministratorAccess` policy:

```json
{ "Version": "2024-01-01",
  "Statement": [{ "Sid": "AdministratorAccess",
                  "Effect": "Allow", "Action": "*", "Resource": "*" }] }
```

##### POST + verify the policy

```bash
cat > /tmp/sales-kr-read.json <<'EOF'
{
  "name": "sales-kr-read",
  "document": {
    "Version": "2024-01-01",
    "Statement": [{
      "Sid":       "SalesKrRead",
      "Effect":    "Allow",
      "Action":    ["data:Select"],
      "Resource":  "data:table:iceberg.sales.*",
      "Condition": "country = 'KR'"
    }]
  }
}
EOF

curl -sS -X POST $ONTUL/admin/iam/policies \
  -H "Authorization: Bearer $ONTUL_TOK" -H 'Content-Type: application/json' \
  --data @/tmp/sales-kr-read.json
# {"status":"ok","policyName":"sales-kr-read"}

# Read back — every PascalCase field is populated; if `Statement` is `null`,
# the JSON used lowercase fields and the deserializer dropped them.
curl -sS -H "Authorization: Bearer $ONTUL_TOK" $ONTUL/admin/iam/policies \
  | jq '.["sales-kr-read"]'
```

A common failure mode is forgetting the `Version` field — the policy still saves but Ontul logs a deserialization warning and the policy never matches. Always verify the read-back shows your `Statement` array populated.

Ontul policies use AWS IAM document shape. **`Condition`** is a SQL `WHERE` fragment that chango's `chango-trino-authz` plugin lifts into a Trino `ViewExpression` via `getRowFilters()` for every query that touches `Resource`. **`Columns`** plus `Effect:"Deny"` blocks listed columns (Trino path NULL-masks them). For per-column SQL-expression rewrites use the separate **`Effect:"Mask"`** + `MaskedColumns` form — see §5.5 below.

Field-name reminder: actions are namespaced (`data:Select`, not `SELECT`) and table resources use the `data:table:<catalog>.<schema>.<table>` prefix. Lowercase or unprefixed forms are silently ignored.

```bash
cat > /tmp/sales-kr-read.json <<'EOF'
{
  "name": "sales-kr-read",
  "document": {
    "Version": "2024-01-01",
    "Statement": [
      {
        "Sid": "SalesKrRead",
        "Effect": "Allow",
        "Action": ["data:Select"],
        "Resource": "data:table:iceberg.sales.*",
        "Condition": "country = 'KR'"
      }
    ]
  }
}
EOF

curl -sS -X POST $ONTUL/admin/iam/policies \
  -H "Authorization: Bearer $ONTUL_TOK" -H 'Content-Type: application/json' \
  --data @/tmp/sales-kr-read.json

curl -sS -X POST $ONTUL/admin/iam/attach-group-policy \
  -H "Authorization: Bearer $ONTUL_TOK" -H 'Content-Type: application/json' \
  -d '{"groupName":"analyst-kr-grp","policyName":"sales-kr-read"}'
```

### 5.3 Verify through Trino

The `chango-trino-authz` plugin maps Trino's `X-Trino-User` header to an Ontul identity, evaluates the user's effective policies, and rewrites the query plan accordingly. No password / token is needed in the Trino CLI — chango's authz plugin trusts the coordinator's network boundary.

```bash
# admin — no filter
trino --server http://$COORD_HOST:$COORD_PORT --user admin --catalog iceberg \
      --execute 'SELECT country, COUNT(*) FROM sales.orders GROUP BY country'
# "KR","2"
# "JP","2"

# analyst-kr — Condition `country = 'KR'` injected → KR rows only
trino --server http://$COORD_HOST:$COORD_PORT --user analyst-kr --catalog iceberg \
      --execute 'SELECT country, COUNT(*) FROM sales.orders GROUP BY country'
# "KR","2"
```

### 5.4 Column-level Deny (NULL-mask sensitive columns)

`Columns` listed on a Statement with `Effect:"Deny"` blocks those columns from the user's view of `Resource`. The chango-trino-authz plugin implements this via Trino's native `getColumnMasks()` API, replacing the value with `NULL` while keeping the column name + type in the result schema — joins, group-by, and BI dashboards keep working but the raw value never leaves the coordinator. Example — hide `customer_id` from `analyst-kr` on the orders table while keeping the existing allow + row filter:

```json
{
  "name": "sales-kr-hide-pii",
  "document": {
    "Version": "2024-01-01",
    "Statement": [
      {
        "Sid": "SalesKrRead",
        "Effect": "Allow",
        "Action": ["data:Select"],
        "Resource": "data:table:iceberg.sales.orders",
        "Condition": "country = 'KR'"
      },
      {
        "Sid": "HidePii",
        "Effect": "Deny",
        "Action": ["data:Select"],
        "Resource": "data:table:iceberg.sales.orders",
        "Columns": ["customer_id"]
      }
    ]
  }
}
```

A `SELECT * FROM sales.orders` for that user returns rows with `customer_id = NULL`; the column still appears in `DESCRIBE` and the result schema, just always null.

### 5.5 Column Mask (rewrite values with a SQL expression)

For partial reveal patterns — last-4-of-card, hashed email, bucketed salary, role-aware unmasking — use `Effect:"Mask"` + `MaskedColumns`. Ontul stores the policy with per-column Trino-dialect SQL expressions and resolves any `${user.*}` substitutions before responding; the chango-trino-authz plugin lifts each `(column, expr)` pair into a Trino `ViewExpression`, so the planner evaluates the mask at the worker on every row.

```json
{
  "name": "sales-kr-mask",
  "document": {
    "Version": "2024-01-01",
    "Statement": [{
      "Sid": "MaskCustomerPii",
      "Effect": "Mask",
      "Action": ["data:Select"],
      "Resource": "data:table:iceberg.sales.customers",
      "MaskedColumns": {
        "phone":   "'***-***-XXXX'",
        "email":   "MD5(email)",
        "salary":  "ROUND(salary, -3)"
      }
    }]
  }
}
```

`analyst-kr` running `SELECT email, phone, salary FROM sales.customers` then sees the masked values:

```
email                            | phone         | salary
---------------------------------+---------------+-------
5d41402abc4b2a76b9719d911017c592 | ***-***-XXXX  | 75000
…
```

The columns still exist with their original names + types; only the values are rewritten in the projection. Mask expressions can call any function Trino's expression engine knows (`CASE WHEN`, `MD5`, `ROUND`, `SUBSTR`, concat via `||`, etc.). See [Ontul IAM — Column Masking](https://cloudcheflabs.github.io/ontul-docs/1.0.0/features/iam/#column-masking) for the full mask-expression catalog and the user-context templating tokens (`${user.id}`, `${user.roles}`, `${user.attr.<key>}`).

**Precedence** (per Ontul docs and the chango plugin): `Deny > Mask > Allow`. A column listed in both a Deny statement and a Mask statement is NULL-masked — the SQL expression is dropped. Use Deny for "this column must not be reasoned about", Mask for "this column stays useful but the raw value is sensitive".

### 5.6 DENY check

Without an explicit `INSERT` / `DELETE` action in the policy, mutating statements are denied:

```bash
trino --server http://$COORD_HOST:$COORD_PORT --user analyst-kr --catalog iceberg \
      --execute "DELETE FROM sales.orders WHERE order_id=1"
# Query failed: Access Denied: ...
```

## 6. Connect with DBeaver (nginx → Trino Gateway → Trino)

Every JDBC / BI client (DBeaver, Tableau, Superset, Looker, …) talks to the Trino Gateway over HTTP. So far the Gateway has been reached on its allocator-assigned port (`$GW_PORT`, typically in the 19xxx band) — fine for ad-hoc curl but awkward to hand to analysts. The recommended chain is:

```
client (DBeaver)
   └─► nginx                    (single well-known listen port per Gateway cluster)
         └─► Trino Gateway      (picks a backend by Ontul group → cluster-group)
               └─► Trino        (executes; chango-trino-authz enforces row / column rules)
```

nginx in chango is a per-cluster feature reconciled by the leader — when a Gateway instance comes or goes, the upstream block re-renders within ~30 seconds. See [Nginx Reverse Proxy](../operations/nginx-proxy.md) for the operations background; this section is the wire-up specific to DBeaver.

### 6.1 Front the Gateway with nginx

#### Via the chango admin UI

1. From the chango admin UI's **Trino Gateway** page click into the `trino-gw` cluster.
2. Open the **Nginx Proxy** panel.
3. **Host** — pick `chango-n1` (or any NM with sufficient network reachability for clients).
4. **Instances** — leave all checked (there is only the one Gateway instance in this lab).
5. Click **Apply**. The panel writes `/etc/nginx/conf.d/chango_trino-gateway_trino-gw.conf` and reloads nginx. After a few seconds the **Current Proxy URL** banner appears with the public-facing URL — e.g. `http://chango-n1.chango.private:19180`.

#### Via REST

```bash
curl -sS -X POST $BASE/admin/api/clusters/trino-gw/nginx \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d "{\"nginxNode\":\"$N1\",\"instances\":[\"trino-gw-gateway-1\"]}"
```

### 6.2 Pin the nginx URL

```bash
NGX_HOST=$(curl -sS -H "Authorization: Bearer $TOK" \
  $BASE/admin/api/clusters/trino-gw/nginx | jq -r .nginxHost)
NGX_PORT=$(curl -sS -H "Authorization: Bearer $TOK" \
  $BASE/admin/api/clusters/trino-gw/nginx | jq -r .nginxPort)
echo "nginx: $NGX_HOST:$NGX_PORT"
```

Sanity-check from the operator shell — the nginx layer is transparent, so the same Trino REST works:

```bash
curl -sS -u admin: "http://$NGX_HOST:$NGX_PORT/v1/info" | jq .nodeVersion
# "<trino-version>"
```

> **Hostname reachability** — `chango-n1.chango.private` is the FQHN chango writes into `/etc/hosts` on every node. From an analyst laptop outside the chango network, either add the entry to the laptop's hosts file or substitute the raw IP / public DNS that maps to the nginx host. DBeaver does not care which form, but the host segment must resolve from where DBeaver runs.

### 6.3 Configure DBeaver

#### 6.3.1 Driver

DBeaver ships a Trino driver out of the box (search "Trino" in **Database → Driver Manager** to confirm). If you need a specific Trino version (e.g. to match the cluster), in **Driver Manager → Trino → Libraries** add `io.trino:trino-jdbc:<v>` from Maven and remove the bundled one. Use the same version that the cluster reported under `.nodeVersion`.

#### 6.3.2 New connection

In **Database → New Database Connection**, pick **Trino**, click **Next**, and fill the **Main** tab:

| Field | Value |
|---|---|
| **Host** | `chango-n1.chango.private` (from `$NGX_HOST`) |
| **Port** | `19180` (from `$NGX_PORT` — the **nginx** port, not the Gateway's `$GW_PORT`) |
| **Database / Catalog** | `iceberg` (or leave blank to land in the default schema-less context) |
| **Username** | `analyst-kr` (any Ontul user — see Phase 1 §5.1) |
| **Password** | **empty** — chango ships Trino with the Insecure Authenticator by default. The username on the wire is what chango-trino-authz resolves against Ontul. |

Open **Driver properties** and add:

| Property | Value | Why |
|---|---|---|
| `SSL` | `false` | nginx is HTTP-only in this lab. Set `true` after you terminate TLS on nginx for production. |
| `source` | `dbeaver` | shows up in Trino's `query_history` and Gateway routing logs — invaluable for "who is hammering us." |
| `clientTags` | (optional) — e.g. `bi` | If you set up cluster-group routing rules keyed on tags, this is how the Gateway routes the connection. |
| `applicationNamePrefix` | (optional) `chango-` | distinguishes BI traffic in coordinator logs. |

Leave everything else default. JDBC URL DBeaver constructs:

```
jdbc:trino://chango-n1.chango.private:19180/iceberg?SSL=false&source=dbeaver
```

#### 6.3.3 Test the connection

Click **Test Connection**. DBeaver opens a `GET /v1/info`, gets a `200`, and shows the version banner — the request walked through nginx → Gateway → coordinator → back. Click **Finish**.

In the SQL editor, run:

```sql
SHOW CATALOGS;
```

You should see `iceberg`, `jmx`, `system`, `tpcds`, `tpch` — same list `$COORD_HOST:$COORD_PORT` returned in §3.4.

### 6.4 Verify RBAC end-to-end through the JDBC chain

Open the **analyst-kr** connection's SQL editor:

```sql
SELECT order_id, country, total_amount
FROM iceberg.sales.orders
ORDER BY order_id;
```

Returns only the KR rows — `chango-trino-authz` injected `WHERE country = 'KR'` server-side, exactly as the `trino` CLI verified in §5.3.

Now repeat the connection wizard with **Username = `analyst-jp`** + the same nginx host/port, and run the same query:

```sql
SELECT order_id, country, total_amount
FROM iceberg.sales.orders
ORDER BY order_id;
```

Returns only the JP rows.

If you applied the §5.4 Deny policy, `SELECT *` from `analyst-kr` shows `customer_id` as `NULL`; the column stays in the schema but its values never reach the client. If you applied the §5.5 Mask policy instead, `phone` / `email` / `salary` come back rewritten by their SQL expressions (`'***-***-XXXX'`, `MD5(email)`, `ROUND(salary, -3)`). The chain — DBeaver, nginx, Gateway, coordinator, chango-trino-authz, Ontul — collapses the policy decision before a single byte leaves the coordinator.

### 6.5 Request chain summary

```
DBeaver
  │ HTTP POST /v1/statement (X-Trino-User: analyst-kr)
  ▼
nginx :19180 (proxy_pass to GW:$GW_PORT)
  │
  ▼
Trino Gateway :$GW_PORT
  │ Look up Ontul groups for analyst-kr → resolve cluster-group → pick trino-main
  ▼
Trino coordinator :$COORD_PORT
  │ Parse + plan
  │ chango-trino-authz asks Ontul: { user=analyst-kr, action=data:Select, resource=data:table:iceberg.sales.orders }
  │ Inject Condition (`country = 'KR'`) into the plan
  │ Project only whitelisted Columns
  ▼
Trino workers execute filtered + projected plan
  │ Stream rows back up the chain
  ▼
DBeaver result grid
```

Three things to remember about this chain:

1. **The nginx layer is policy-free** — every Allow / Deny / row-filter / column-mask decision still happens at the Trino coordinator. nginx is purely a TCP/HTTP fan-in.
2. **The Gateway layer is routing-only** — picking which backend executes the query. RBAC is not applied at the Gateway either.
3. **Once you flip on TLS at nginx**, you do not have to change anything Trino-side. Flip `SSL=true` in the DBeaver driver properties, point the JDBC URL at the HTTPS port, and the rest of the chain stays put.

## Phase 1 exit checklist

- [ ] `trino-main` all instances RUNNING (coordinator + 2 workers)
- [ ] `trino-gw` RUNNING
- [ ] `SHOW CATALOGS` through the Gateway lists `iceberg`
- [ ] CTAS, MERGE, window, partition prune, time travel, schema evolution, multi-join all pass
- [ ] `analyst-kr` sees only KR rows; `analyst-jp` sees only JP rows; mutation is denied

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `iceberg` missing from `SHOW CATALOGS` | Is Polaris RUNNING, and was the `lakehouse` catalog created (see Phase 0 → 4.1)? Check `etc/catalog/iceberg.properties` on the Trino coordinator. |
| `Access Denied` even as `admin` | Either `ontulAuthzToken` was not supplied at install time, or the OTOK has expired. Update Trino's config via the admin REST to refresh the token. |
| Exchange errors (`Failed to upload …`) | Does the `s3://trino-exchange/` bucket exist on ShannonStore? Does the access key have write permission on it? |
| MERGE fails with `Iceberg merge not enabled` | The connector option `iceberg.merge` is on by default in chango's Trino install. Older Trino versions (< 479) have MERGE limitations. |

## Stop Trino before moving on

Phase 2 (Spark) needs the headroom. Stop the Trino cluster (keep the Gateway running — it is stateless and lightweight):

```bash
curl -sS -X POST $BASE/admin/api/trino/trino-main/stop \
  -H "Authorization: Bearer $TOK"
```

Continue with the [Tutorials overview](index.md) for Phase 2 onward.
