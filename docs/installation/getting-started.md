# Getting Started

You have a chango cluster up — masters running on the hosts in `chango_masters`, a bundled ZooKeeper quorum running on the hosts in `chango_zookeepers` (3 nodes by default), and a node manager on every host. The admin UI is reachable on `:8080`. This page walks through your first login, sanity-checking the topology, and installing the first managed component.

## First login

Open `http://<master-host>:8080/admin/` in a browser. Sign in with `admin / admin`. Chango will require a password change on first login.

You can also drive everything from the REST API:

```bash
BASE=http://<master-host>:8080
TOK=$(curl -s $BASE/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<your-password>"}' | jq -r .accessToken)
```

The rest of this page uses the admin UI; every action has an equivalent REST call.

## Verify cluster topology

From the admin UI's left sidebar, open **Cluster → Nodes**. You should see:

- One **Master** row with `ready = true`, `isLeader = true`.
- One **Node Manager** row per host listed in the inventory, all `ready = true`.

REST equivalent:

```bash
curl -s -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/masters
curl -s -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/node-managers
```

If a node is missing, tail its log on the host:

```bash
# master host
tail -f /var/log/chango/master.log
tail -f /var/log/chango/zookeeper.log

# any node manager host
tail -f /var/log/chango/nodemanager.log
```

## Install your first component — PostgreSQL

PostgreSQL is the smallest managed component chango ships, and several other layers (Polaris metastore, Trino resource groups, NeoRunBase coordinator catalog) can reuse the same instance.

1. Sidebar → **Components → PostgreSQL** → **Install**.
2. Pick a target node manager.
3. Set a strong PostgreSQL superuser password.
4. Click **Install**, then **Start**.

The status moves through `INSTALLED → STARTING → RUNNING`. The pid and live CPU / memory show up within seconds.

REST equivalent:

```bash
curl -sm 240 -X POST -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d '{"instanceId":"pg-1","nodeId":"<nm-nodeId>","password":"<strong-password>"}' \
  $BASE/admin/api/postgres

curl -s -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/postgres/pg-1/start
```

The component runs as a system user (`postgres`) and stores its data under `/opt/components/pg-1/data`. Chango remembers the superuser password and reuses it when another component (Polaris, NeoRunBase, …) asks for a chango-installed PG.

## Install a lakehouse stack — Ontul + ShannonStore + Polaris + Trino

For a minimum lakehouse stack, install these in order:

1. **Ontul** — IAM authority that the other components delegate authorization to.
2. **ShannonStore** — S3-compatible object storage for Iceberg data and Trino exchange.
3. **Polaris** — Iceberg REST catalog (uses the PostgreSQL you installed above).
4. **Trino** — Distributed SQL with exchange manager (ShannonStore), resource groups (PostgreSQL), and authz (Ontul) wired in.

Each component has its own admin UI panel. The dependencies are auto-discovered:

- Trino, Spark, Flink, and the Trino Gateway find Ontul automatically and only ask the operator for a long-lived OTOK token (issued from Ontul's IAM page).
- Polaris and the Trino resource-group manager find the chango-installed PostgreSQL from a dropdown — no need to type host/port/credentials.

See [Component Catalog](../components/catalog.md) for the full per-component install flow.

## Where things live

| Path on each host | What it is |
|---|---|
| `/opt/chango` | Chango master + node manager install dirs |
| `/opt/chango/bin/*.pid` | Chango process pid files (master / zk / nodemanager, one per running instance) |
| `/opt/components/<instanceId>` | Each managed component's install dir |
| `/var/lib/chango` | Chango master's RocksDB stores (KMS, IAM, metadata) |
| `/var/log/chango` | Chango master + NM + ZK logs |

Per-component logs live under `/opt/components/<instanceId>/logs/` (or the component-specific log path) and are also tailable from the admin UI's Logs panel.

## Day-2 lifecycle

Stop, restart, add another master, add another node manager — all done by the operator running shell scripts directly on the host, not through systemctl. See [Cluster Operations](../operations/cluster-operations.md).

## Next steps

- [Component Catalog](../components/catalog.md) — what each layer does and how to wire them together.
- [Cluster Topology](../features/topology.md) — multi-master, NM placement, co-location rules.
- [Cluster Operations](../operations/cluster-operations.md) — day-2 actions.
