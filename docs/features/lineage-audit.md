# Data Lineage & Audit

Every query that runs on a chango-managed engine passes through a first-party authorization plugin. Since 3.0.0 those plugins do not only *decide* — they also **report**. Each authorization outcome becomes an **audit event**, and every successful write becomes a **lineage edge**, both pushed into Ontul's replicated store. The result is one cross-engine record of *who touched which table, with which action, from which engine, and where the data came from* — without deploying a separate lineage collector, agent, or log shipper.

This page describes what is collected, how it gets there, what each engine can and cannot contribute, and how to verify it on a live cluster.

## Why it lives in the authz plugin

The authorization plugin is the only place in an engine that is guaranteed to see **every** table access, before execution, with the resolved identity attached. Log scraping sees SQL text but not the resolved principal or the post-planning table set; a metastore listener sees writes but not reads. By emitting from the authz hook, audit and lineage inherit the same completeness guarantee as the access check itself.

```
   Trino / Spark / Flink
          │
          │  authz check: POST /v1/api/authz/check-batch   (synchronous, blocking)
          ▼
    ┌────────────┐        ALLOW / DENY / ABSTAIN
    │   Ontul    │◀───────────────────────────────┐
    │ IAM + store│                                │
    └────────────┘                                │
          ▲                                       │
          │  POST /v1/api/audit     (async, best-effort)
          │  POST /v1/api/lineage   (async, best-effort)
          └───────────────────────  LineageAuditReporter (bounded background pool)
```

Both reporting calls reuse the **same** long-lived Ontul service credential the plugin already holds for the authz check — sent as `Authorization: Token <OTOK>`. The chango installer wires that credential into the engine at cluster-install time, so there is nothing extra to configure.

Ontul routes all four paths to its **leader** (audit lives in the leader's RocksDB, lineage in the replicated metadata store); a follower transparently forwards. Both ingest endpoints are POST-only, and `/v1/api/audit` accepts either a single event object or an array of them.

## Guarantees and non-guarantees

| Property | Behaviour |
|---|---|
| **Never blocks a query** | Reporting is submitted to a small bounded thread pool (core 1 / max 2, queue 4096) and runs off the authorization path. |
| **Never fails a query** | Every post is wrapped — a network error, an Ontul 5xx, or a saturated pool is swallowed and logged at most. Authorization stays exact; reporting is advisory. |
| **Lossy under extreme pressure** | The pool's saturation policy is `DiscardOldest`. If an engine outruns Ontul's ingest, the oldest queued reports are dropped rather than growing memory without bound. Audit is not a transaction log — do not build billing on it. |
| **Deny is recorded** | A refused access is audited with `decision=DENY` **before** the plugin throws. A probing or misconfigured user always leaves a trail. |
| **No lineage on deny** | Nothing was written, so no edge is emitted. Lineage only ever describes data that actually moved. |

## What an audit event carries

`POST <ontul>/v1/api/audit`:

| Field | Meaning |
|---|---|
| `source` | The engine that produced the event — `trino`, `spark`, or `flink`. |
| `userId` | The resolved principal the engine authorized as. |
| `action` | The IAM action — `data:Select`, `data:Insert`, `data:CreateTable`, … |
| `resource` | Fully-qualified `catalog.schema.table` (the `data:table:` prefix is stripped before reporting). |
| `tables` | The table set the event concerns — a single-element list for the per-table engines. |
| `decision` | `ALLOW` for an authorized access, `DENY` for a refused one. |
| `details` | Which plugin emitted it, plus Ontul's raw verdict on a deny — e.g. `trino authz plugin (ontul: ABSTAIN)`. |
| `query` | The SQL text, when the engine exposes it at this layer. Trino's `SystemAccessControl` SPI does **not**, so Trino events omit it; who / engine / table / action are always present. |

A `DENY` event distinguishes the two ways an access can be refused: an explicit `Effect: "Deny"` statement (`ontul: DENY`) and *no matching statement at all* (`ontul: ABSTAIN`). Both are failures for the user, but only the second usually means "the policy was never granted", which is the far more common misconfiguration.

## What a lineage edge carries

`POST <ontul>/v1/api/lineage`:

| Field | Meaning |
|---|---|
| `target` | The table that was written — fully qualified. |
| `sources` | The set of tables read to produce it. |
| `operation` | `CTAS` (`CREATE TABLE … AS SELECT`), `INSERT`, or `EXTERNAL` when the engine could not classify it. |

Ontul's lineage ingest **replaces** the target's source set on each POST rather than appending. That is what makes the re-emission strategy below safe.

## Per-engine coverage

| Engine | Audit | Lineage | Why |
|---|---|---|---|
| **Trino** | Every allowed access (one event per table) + every denied one | `sources → target` per `queryId` | The plugin correlates per-query source reads with the write target. |
| **Spark** | Every target in the authorized plan + every denied one | `sources → target` for `INSERT` / `MERGE` | The plugin authorizes the whole analyzed plan at once, so sources and targets are known in a single shot. |
| **Flink** | Every authorized `TableLoader` (source and sink) + every denied one | *Not yet* | Each loader authorizes independently on its own TaskManager with no shared job key to correlate them. Job-level wiring is a planned follow-up. |

### Trino — callback ordering

Trino does **not** guarantee that the source `SELECT` checks precede the write-target check. For `CREATE TABLE … AS SELECT` it invokes `checkCanCreateTable` *before* `checkCanSelectFromColumns`. A naive implementation that emits the edge from the write-target callback therefore sees an empty source set and emits nothing usable.

The reporter instead keeps both the target *and* the accumulating sources on a per-`queryId` accumulator, and **re-emits the full source set every time it holds a target plus at least one source**. Because Ontul replaces the target's source set on each POST, the repeated emissions converge on the complete edge no matter which order Trino fires the callbacks in. The accumulator is bounded (20 000 queries) and self-evicting (5-minute TTL) so a long-running or abandoned query cannot leak memory.

### Spark

`AuthzCheckRule` holds the entire plan's target list, so `report()` audits every `(action, table)` pair and emits one edge per write target from the plan's `SELECT` sources — no accumulator and no ordering hazard.

### Flink

`ChangoAuthzTableLoader` audits each source and sink table as it authorizes it. Lineage is deliberately not emitted: Flink authorizes each loader independently on the TaskManager that owns it, and the plugin has no job-scoped key to join a source loader on one TM with a sink loader on another. Emitting a partial edge would be worse than emitting none.

## Configuration

Reporting is **on by default** on all three engines. The chango installer sets nothing extra; the key exists so an operator can turn reporting off (for a benchmark run, or while Ontul is being maintained) without removing the authz plugin.

| Engine | Key | Where | Default |
|---|---|---|---|
| Trino | `lineage.audit.enabled` | `etc/access-control.properties` (the same file that carries the plugin's Ontul URL and token) | `true` |
| Spark | `spark.chango.authz.lineage.audit.enabled` | Spark conf (`spark-defaults.conf`, `--conf`, or the chango cluster's properties map) | `true` |
| Flink | `lineageAuditEnabled` on `OntulAuthzConfig` | Carried by `ChangoAuthzTableLoader` in the job wiring | `true` |

Setting it to `false` disables **both** audit and lineage for that engine. It does not affect the authorization check itself — access control keeps working exactly as before.

Editing the Trino key is a normal [component configuration](../operations/component-operations.md) change: open the cluster, **Configure**, edit `access-control.properties`, and restart the coordinator. The edit is refused only while the coordinator is starting or stopping — see [Config Change Gate](config-runtime-only.md).

## Verifying on a live cluster

1. **Run an allowed query** as a non-admin user through Trino:

    ```sql
    CREATE TABLE lakehouse.demo.top_customers AS
    SELECT c_custkey, c_name FROM lakehouse.demo.customer WHERE c_acctbal > 9000;
    ```

2. **Run a query you expect to be refused** — a table the user has no `data:Select` grant on:

    ```sql
    SELECT * FROM lakehouse.restricted.payroll;
    ```

    The query must fail with an access-denied error.

3. **Read the audit log back from Ontul.** `/v1/api/audit` and `/v1/api/lineage` are ingest-only (POST); the read surface is Ontul's admin API, so authenticate with an Ontul admin bearer token. Both queries should appear — the first as `decision=ALLOW` rows (one per table touched), the second as a single `decision=DENY` row whose `details` names the Ontul verdict:

    ```bash
    curl -s -H "Authorization: Bearer $ONTUL_TOKEN" \
      "$ONTUL/admin/audit?limit=50&engine=trino" \
      | jq '.[] | {source, userId, action, resource, decision, details}'
    ```

    `GET /admin/audit` filters on `limit` (default 200), `user`, `engine`, `table`, `action`, `query`, and a `from` / `to` epoch-millis window — enough to answer "everything alice did against `payroll` yesterday" without exporting the log.

4. **Read the lineage edge.** Ontul exposes the graph, not the raw edge list:

    ```bash
    curl -s -H "Authorization: Bearer $ONTUL_TOKEN" \
      "$ONTUL/admin/lineage/graph?root=lakehouse.demo.top_customers&depth=2&direction=up" | jq .
    ```

    `direction=up` walks upstream (where did this table come from), `down` walks downstream, `both` returns the neighbourhood. Two companion endpoints answer the questions operators actually ask:

    ```bash
    # Which columns of this table came from where?
    curl -s -H "Authorization: Bearer $ONTUL_TOKEN" "$ONTUL/admin/lineage/columns?table=lakehouse.demo.top_customers"
    # If I change this table, what breaks?
    curl -s -H "Authorization: Bearer $ONTUL_TOKEN" "$ONTUL/admin/lineage/impact?table=lakehouse.demo.customer"
    ```

    The denied query contributes nothing to the graph — nothing was written.

See [Ontul Audit Log](https://cloudcheflabs.github.io/ontul-docs/1.0.0/features/audit-log/) for the stored schema, retention, and the optional Iceberg tiering of the audit table, and [Ontul Data Lineage](https://cloudcheflabs.github.io/ontul-docs/1.0.0/features/data-lineage/) for the graph model the edges feed.

## Troubleshooting

- **Audit events appear but no lineage edge for a CTAS.** Confirm both the source `SELECT` and the write target were authorized in the same statement — an `INSERT` from a client-side literal set has no source and correctly produces no edge. If sources exist but the edge is missing, check that the plugin JAR is the 3.0.0 build: earlier builds emitted the edge only from the write-target callback and lost it on Trino's CTAS ordering.
- **Nothing at all reaches Ontul.** The reporter shares the authz client, so if authorization works, connectivity works. Check `lineage.audit.enabled` first, then the engine log for `chango-*-lineage-audit` thread warnings.
- **Denied queries are missing from the audit log.** Deny auditing landed with the 3.0.0 plugins. An older plugin JAR reports only allowed accesses — swap the JAR (see [Patch System](patch-system.md), which does exactly this without a reinstall) and restart the engine.
- **Audit volume is overwhelming Ontul.** Every table of every query produces an event. Turn reporting off on the noisiest engine, or scale Ontul's ingest — the plugins will silently drop rather than back-pressure the engine.

## Related

- [Identity & Access Management](iam.md) — the authorization model these plugins enforce, and the per-engine granularity table.
- [Role-Based Access (Stage 1)](role-based-access.md) — chango's own control-plane RBAC, which is separate from engine-level authz.
- [Patch System](patch-system.md) — how to roll a new plugin JAR onto a running engine.
