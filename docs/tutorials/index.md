# Tutorials

These tutorials walk a working chango cluster through a real, phase-by-phase workload. They are written for operators who have just installed chango, for engineers new to Iceberg lakehouses, and for anyone who wants to see chango's RBAC + KMS + component lifecycle model exercised end-to-end with concrete commands.

## How the phases are structured

Each phase **brings up only the components it needs** and stops the heavy ones it does not. This keeps the tutorial runnable on a single host (e.g. a docker test cluster on amd64 emulation) without exhausting memory.

| Phase | Focus | Always ON | Stop before this phase | Stop at the end |
|---|---|---|---|---|
| [0](phase-0-foundation.md) | Foundation install (Ontul · PostgreSQL · ShannonStore · Polaris) | — | — | — |
| [1](phase-1-trino-iceberg-rbac.md) | Trino + Trino Gateway + Iceberg complex queries + Ontul RBAC | Foundation | — | (next phase stops Trino cluster) |
| [2](phase-2-spark-iceberg.md) | Spark `cluster-mode` submit writing Iceberg → read back through Trino | Foundation | Trino cluster | Spark |
| [3](phase-3-kiok-spark.md) | kiok DAG scheduling a Spark submit (via SSH-to-master) | Foundation + Spark | Trino cluster | kiok · Spark |
| [4](phase-4-iceberg-maintenance.md) | Ontul Iceberg table maintenance (snapshot expire, orphan cleanup, compaction) | Foundation | Trino · Spark · kiok | — |
| [5](phase-5-kafka-flink-iceberg.md) | Kafka → Flink → Iceberg streaming + RBAC | Foundation | Trino · Spark · kiok | Kafka · Flink |

> **Foundation** refers to the four components installed in Phase 0 — Ontul, PostgreSQL, ShannonStore, Polaris. Every later phase assumes those are running.

## Prerequisites

These tutorials assume you have finished [Installation](../installation/index.md). Specifically:

- master + at least two node managers are ready — `/admin/api/cluster/info` returns `ready: true`
- you can log in to the admin UI as `admin/admin` (or whatever you changed the password to)
- the operator is holding `CHANGO_MASTER_KEY` in a real secret manager

All examples assume the master's admin port is `8080` (`http://<master>:8080/admin/`).

## Common setup — get an admin token {#admin-token-setup}

Every phase below drives chango through the admin REST. Get a token once and reuse it for the whole tutorial.

```bash
BASE=http://<master-host>:8080

# 1) First time only: default admin/admin login. The response will set
#    requirePasswordChange: true the very first login.
curl -sS -X POST $BASE/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}'
# { "accessToken": "...", "requirePasswordChange": true }

# 2) If requirePasswordChange is true, change the password
TOK=<accessToken from step 1>
curl -sS -X POST $BASE/admin/api/auth/change-password \
  -H "Authorization: Bearer $TOK" \
  -H 'Content-Type: application/json' \
  -d '{"oldPassword":"admin","newPassword":"<your-strong-pw>"}'
# { "status": "ok" }

# 3) Log in again with the new password and save the token for the rest
#    of the tutorial.
TOK=$(curl -sS -X POST $BASE/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<your-strong-pw>"}' | jq -r .accessToken)
echo "Token length: ${#TOK}"
```

Every other admin call below uses `-H "Authorization: Bearer $TOK"`.

## Get the NM nodeIds

Component install requests target NMs by `nodeId`. List them first:

```bash
curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/nodes/node-managers \
  | jq '.[] | {nodeId, host, ready}'
```

Sample output:

```json
{ "nodeId": "nm-chango-n1-19998", "host": "chango-n1", "ready": true }
{ "nodeId": "nm-chango-n2-19998", "host": "chango-n2", "ready": true }
{ "nodeId": "nm-chango-n3-19998", "host": "chango-n3", "ready": true }
```

You will paste these into the per-component install requests in each phase.

## Next

Start with [Phase 0 — Foundation install](phase-0-foundation.md).
