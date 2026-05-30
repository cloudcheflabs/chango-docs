# Phase 7 — kiok DAG: trino operator (via Trino Gateway) + ontul operator (S3-hosted Python)

By the end of Phase 4 the lakehouse holds a working Iceberg table (`iceberg.test.maint_demo`, 6 rows, sum=1400) and Ontul's Maintenance scheduler has been verified. Phase 7 puts kiok in front of all of it: a single DAG triggers an Iceberg query against Trino **through the Trino Gateway**, runs a BATCH SQL job on Ontul, and dispatches an S3-hosted Python script to an Ontul worker.

This phase is the **end-to-end engine integration test** for kiok — every other tutorial exercises one engine at a time; here three runners share a DAG.

## Topology

Everything from Phase 4 stays up, **plus** kiok and trino-gateway:

| Component | Why |
|---|---|
| ShannonStore (S3) | hosts the iceberg data files + the Python script |
| PostgreSQL | Polaris metastore |
| Polaris | Iceberg REST catalog |
| Ontul (master + workers) | runs the BATCH SQL + PYTHON jobs |
| Trino (coord + workers) | runs the Iceberg query |
| **Trino Gateway** | fronts Trino with `ontul` Basic-auth — kiok's `trino` operator targets the gateway, not the coordinator directly |
| **kiok** (master + workers) | schedules + dispatches the DAG |

## Variables carried over (Phase 0/1/4) + new for Phase 7

```bash
BASE=http://<master-host>:8080
TOK=<chango admin token>

# From Phase 4 — Ontul admin endpoint + admin user JWT/OTOK
ONTUL_ADMIN=http://<host>:<ontul-master-admin-port>    # e.g. http://172.31.11.123:19220
ONTUL_JWT=<JWT from POST $ONTUL_ADMIN/admin/auth/login>

# From Phase 1 / Iceberg e2e — admin user IAM access key on Ontul (raw AK:SK)
ADMIN_AKSK=<accessKeyId>:<secretAccessKey>             # used as Basic password against the Trino Gateway

# New for Phase 7
TGW_URL=http://<host>:8680                             # trino-gateway public endpoint
KIOK_ADMIN=http://<host>:18400                         # kiok master admin port
KTOK=<JWT from POST $KIOK_ADMIN/api/v1/auth/login user="admin">
```

## 1. Wire the Trino Gateway

The gateway needs **three** chango-side records before any query routes:

```bash
# 1a. Register trino-main as a gateway backend (mark it activated).
curl -sS -X POST $BASE/admin/api/gateway/clusters \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $TOK" \
  -d '{"clusterName":"trino-main","url":"http://<trino-coord-host>:8480","activated":true}'

# 1b. Register a cluster-group with the backend.
curl -sS -X POST $BASE/admin/api/gateway/cluster-groups \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $TOK" \
  -d '{"groupName":"default","trinoClusterIds":["trino-main"]}'

# 1c. Push an authz token into the gateway's config so it can call Ontul.
#     Re-use the OTOK the trino install already minted (it's an admin-equivalent
#     service principal on Ontul) — store it on the cluster:
SERVICE_OTOK=<OTOK… string from trino's ontulAuthzToken setting>
curl -sS -X POST $BASE/admin/api/trino-gateway/tgw-main/config \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $TOK" \
  -d "{\"properties\":{\"gateway.ontul.authz.token\":\"$SERVICE_OTOK\"}}"
```

Restart the gateway after each step (`POST /admin/api/trino-gateway/tgw-main/restart`) so it pulls the topology from the chango master and picks up the new `gateway.ontul.authz.token`.

Smoke-test from inside the cluster:

```bash
# Basic-auth username is informational; the password is "<accessKey>:<secretKey>".
curl -sS -u "admin:$ADMIN_AKSK" -X POST "$TGW_URL/v1/statement" \
     -H 'Content-Type: text/plain' \
     --data 'SELECT count(*), sum(amount) FROM iceberg.test.maint_demo'
# → follow the nextUri until state=FINISHED, expect [[6,1400]]
```

If you get `401 invalid credentials` the gateway's authz token is missing; if you get `no active cluster in group 'default'` the cluster-group has not yet propagated — restart the gateway one more time.

## 2. Register an S3 connection on Ontul

Ontul needs a named ConnectionStore entry to resolve `s3://…` URIs at job time (script paths, dep jars):

```bash
curl -sS -X POST $ONTUL_ADMIN/admin/connections \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $ONTUL_JWT" \
  -d '{
    "connectionId": "lakehouse",
    "type": "s3",
    "description": "shannon S3 — admin AKIA",
    "properties": {
      "endpoint":  "http://<shannon-api>:8081",
      "accessKey": "<shannon admin AKIA>",
      "secretKey": "<shannon admin SK>",
      "region":    "us-east-1",
      "pathStyle": "true"
    }
  }'
```

The connection's properties **must use bare keys** (`accessKey`, `secretKey`, `endpoint`, `region`, `pathStyle`) — not the dotted `s3.accessKey` form. Ontul's `S3DepFetcher` reads them by bare names; the dotted variant raises `connection 'lakehouse' is missing accessKey/secretKey`.

Optionally promote it to the default deps connection so jobs that omit `ontul.deps.s3.connectionId` still work:

```bash
curl -sS -X POST $ONTUL_ADMIN/admin/config/storage \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $ONTUL_JWT" \
  -d '{"deps.connectionId":"lakehouse","deps.s3Prefix":"s3://lakehouse/deps/"}'
```

## 3. Upload the Python script

```bash
cat > /tmp/hello.py <<'PY'
import sys, os
print("[py] hello from S3-hosted python")
print("[py] argv:", sys.argv)
print("[py] env ONTUL_JOB_ID:", os.environ.get("ONTUL_JOB_ID", "<unset>"))
print("[py] python version:", sys.version.split()[0])
print("[py] OK")
PY

AWS_ACCESS_KEY_ID=<shannon admin AKIA> \
AWS_SECRET_ACCESS_KEY=<shannon admin SK> \
aws --endpoint-url http://<shannon-api>:8081 \
    s3 cp /tmp/hello.py s3://lakehouse/scripts/hello.py
```

The bucket owner is whoever created it — if that's the shannon admin user, mint an IAM access key for *that* user (not a separate `chango` user) and reuse those credentials for Ontul's `lakehouse` connection. The cleaner alternative is to attach the built-in `AdministratorAccess` policy to a dedicated service user via `POST /admin/iam/attach-user-policy` on shannon; do not chase ad-hoc bucket policies.

## 4. The DAG

```yaml
dag:
  id: ontul_trino_smoke
  default_timeout: 10m

tasks:
  - id: trino_via_gateway
    type: trino
    timeout: 5m
    config:
      # Hit the gateway, not the coordinator. Basic-auth password = AK:SK.
      trino.url:        "http://<host>:8680"
      trino.user:       "admin"          # informational — gateway ignores it
      trino.password:   "<accessKeyId>:<secretAccessKey>"
      trino.catalog:    "iceberg"
      trino.schema:     "test"
      trino.pollIntervalMs: "1000"
    script: |
      SELECT count(*) AS cnt, sum(amount) AS total FROM iceberg.test.maint_demo

  - id: ontul_batch_sql
    type: ontul
    requires: [trino_via_gateway]
    timeout: 5m
    config:
      ontul.url:        "http://<host>:19220"
      ontul.token:      "<ontul admin JWT>"
      ontul.jobType:    "BATCH"
      ontul.pollIntervalMs: "1500"
    script: |
      SELECT count(*) AS cnt, sum(amount) AS total FROM iceberg.test.maint_demo

  - id: ontul_python_s3
    type: ontul
    requires: [ontul_batch_sql]
    timeout: 5m
    config:
      ontul.url:        "http://<host>:19220"
      ontul.token:      "<ontul admin JWT>"
      ontul.jobType:    "PYTHON"
      ontul.scriptPath: "s3://lakehouse/scripts/hello.py"
      # kiok's depsConnectionId only matters when kiok uploads LOCAL files;
      # for an s3:// scriptPath ontul needs to know which connection to use
      # when it fetches the script. Pass it inside ontul.jobConfig.
      ontul.depsConnectionId: "lakehouse"
      ontul.pollIntervalMs:   "1500"
      ontul.jobConfig: |
        {"ontul.deps.s3.connectionId": "lakehouse"}
```

Three reserved-word gotchas worth calling out:

- `SELECT count(*) AS rows, …` fails in Ontul (Calcite parser) with `Encountered "rows"`. Use a different alias (`cnt`).
- Bare `accessKey`/`secretKey` in the Ontul connection (no `s3.` prefix); the dotted variant is for ontul-iceberg-connector config, not ConnectionStore.
- `ontul.deps.s3.connectionId` must be passed per-job in `ontul.jobConfig`. kiok's `ontul.depsConnectionId` field controls *kiok-side* upload only.

## 5. Register + run

```bash
KTOK=$(curl -sS -X POST $KIOK_ADMIN/api/v1/auth/login \
        -H 'Content-Type: application/json' \
        -d '{"user":"admin","password":"<kiok admin password>"}' \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])')

curl -sS -X POST $KIOK_ADMIN/api/v1/dags \
     -H 'Content-Type: application/x-yaml' -H "Authorization: Bearer $KTOK" \
     --data-binary @ontul_trino_smoke.yaml

RUN_ID=$(curl -sS -X POST $KIOK_ADMIN/api/v1/dags/ontul_trino_smoke/runs \
              -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' \
              -d '{}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["runId"])')

# poll
for i in $(seq 1 18); do
  sleep 5
  STATE=$(curl -sS $KIOK_ADMIN/api/v1/runs/$RUN_ID -H "Authorization: Bearer $KTOK" \
          | python3 -c 'import json,sys;print(json.load(sys.stdin)["state"])')
  echo "[$((i*5))s] $STATE"
  [[ "$STATE" == "SUCCESS" || "$STATE" == "FAILED" ]] && break
done

# tail each task's log to confirm the full lifecycle landed
for t in trino_via_gateway ontul_batch_sql ontul_python_s3; do
  echo "==== $t ===="
  curl -sS "$KIOK_ADMIN/api/v1/runs/$RUN_ID/tasks/$t/log?offset=0" \
       -H "Authorization: Bearer $KTOK" | python3 -c 'import sys,json;print(json.load(sys.stdin)["text"])'
done
```

A healthy run looks like:

```
FINAL STATE: SUCCESS
  trino_via_gateway SUCCESS exit=0 externalId=20260529_235501_00022_jh8cu
  ontul_batch_sql   SUCCESS exit=0 externalId=dbb2adf2-c57b-4efd-91b4-8e3f456490a8
  ontul_python_s3   SUCCESS exit=0 externalId=30fda0e8-b7c8-4b15-9130-744d2ecfad76

==== trino_via_gateway ====
[out] POST http://<host>:8680/v1/statement (user=admin, catalog=iceberg, schema=test, auth=basic)
[out] Trino query submitted: id=…
[out] state=QUEUED
[out] state=FINISHED
[out] [6,1400]

==== ontul_batch_sql ====
[out] POST http://<host>:19220/v1/api/job/submit (type=BATCH, auth=bearer)
[out] Ontul status: COMPLETED

==== ontul_python_s3 ====
[out] POST http://<host>:19220/v1/api/job/submit (type=PYTHON, auth=bearer)
[out] [master] PYTHON job starting: s3://lakehouse/scripts/hello.py
[out] [master] Dispatched to worker: <worker-host>:18200
[out] Ontul status: COMPLETED
```

The kiok task log streams the **full lifecycle** for every task (submit → dispatched → RUNNING → COMPLETED/FINISHED). The Python script's own stdout lands in the Ontul worker job log, not back in kiok — pull it with `GET $ONTUL_ADMIN/v1/api/job/status/$JOB_ID` if you need the script output for debugging.

## Failure-mode cheat sheet

| Symptom | Where to look | Fix |
|---|---|---|
| trino task → `401 invalid credentials` from gateway | `gateway.ontul.authz.token` missing in the gateway config | step 1c above |
| trino task → `no active cluster in group 'default'` | gateway hasn't fetched topology yet | restart the gateway, wait one pull cycle |
| ontul BATCH → `Object 'iceberg' not found` | Ontul's iceberg catalog hasn't refreshed since Trino created the table | `POST $ONTUL_ADMIN/admin/catalogs/iceberg/refresh` |
| ontul BATCH → `Encountered "rows"` | Calcite reserved-word alias | rename the alias, e.g. `cnt` |
| ontul PYTHON → `ontul.deps.s3.connectionId is required` | the deps connection isn't being threaded through | both `ontul.depsConnectionId` (kiok-side) *and* `ontul.jobConfig` `{"ontul.deps.s3.connectionId":"…"}` (ontul-side) |
| ontul PYTHON → `connection '…' is missing accessKey/secretKey` | ConnectionStore properties use the dotted (`s3.accessKey`) form | re-register with bare keys |

## Related

- [Phase 1 — Trino + Iceberg + RBAC](phase-1-trino-iceberg-rbac.md) — the user/group/policy setup the gateway uses for Basic-auth.
- [Phase 4 — Iceberg table maintenance](phase-4-iceberg-maintenance.md) — Ontul's Maintenance scheduler the BATCH task in this phase queries against.
- [Phase 6 — kiok native livy task → Spark → Iceberg via Polaris](phase-6-kiok-livy-spark-iceberg-polaris.md) — the other kiok-driven shape for Spark workloads.
