# Phase 3b — kiok DAG via Livy REST (no SSH key)

This phase is the [Phase 3](phase-3-kiok-spark.md) flow rebuilt on top of Livy. Where Phase 3 used a kiok shell task that `ssh spark@chango-n2 'spark-submit …'` to run a Spark job, this phase submits the same workload as a Livy `POST /batches` call from the kiok worker. The DAG never needs an SSH key, never needs Spark binaries on the kiok host, and never needs to know which Spark host is the master — the Livy endpoint abstracts it.

By the end of the phase you will have:

1. A kiok cluster that **does not** distribute SSH keys.
2. A kiok **Connection** entry that holds the Livy URL plus any S3 credentials the batch jar reuses.
3. Three DAGs (YAML / Python SDK / Java SDK) that each `POST /batches` against Livy with an identical Spark + Iceberg workload — the same `iceberg.test.*` tables Phase 3 wrote.
4. Trino reading back the resulting tables unchanged.

## Pre-req

- Phase 2b complete (Spark cluster with a paired Livy server is `RUNNING`; `/sessions` returns 200; an S3-staged jar already ran via `/batches` successfully).
- Phase 3 complete (kiok cluster + git-sync repo + bundle path both wired, with at least the three `spark-iceberg-*` DAGs registered). We will **add three new DAGs** alongside the existing ones, not replace them.

## Variables

```bash
BASE=http://<master-host>:8080
TOK=<chango admin token>
KIOK=http://<kiok-master-host>:18400
KTOK=<kiok admin access token>

LIVY_HOST=<spark master host>          # from Phase 2b
LIVY_PORT=<Livy port, default 30000>
LIVY=http://$LIVY_HOST:$LIVY_PORT

SS_AK=<ShannonStore access key>
SS_SK=<ShannonStore secret key>
SS_ENDPOINT=http://chango-n2.chango.private:8080
POLARIS_REST=http://chango-n2.chango.private:8180/api/catalog
POLARIS_CRED="polaris-root:<clientSecret>"
```

## 1. Add a `livy` Connection to kiok

DAGs reference this connection by id (`Conn.ref("livy-spark")` in code, `${conn.livy-spark.<key>}` in YAML), so when the Livy URL or S3 credentials change you edit the Connection rather than every DAG.

### Via the kiok admin UI

1. **Settings → Connections → New connection**:
    - **Connection ID** — `livy-spark`
    - **Type** — `GENERIC` (Livy is HTTP, no driver class)
    - **Properties** (one per row):
        - `url` — `http://chango-n1.chango.private:30000`
        - `s3.endpoint` — `$SS_ENDPOINT`
        - `s3.access.key` — `$SS_AK`
        - `s3.secret.key` — `$SS_SK`
        - `polaris.rest` — `$POLARIS_REST`
        - `polaris.cred` — `$POLARIS_CRED`
2. Save. The `livy-spark` row appears alongside Phase 3's `s3-shannon` and `polaris-rest`.

### Via REST

```bash
curl -sS -X POST $KIOK/api/v1/connections \
  -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' \
  -d "{
    \"connectionId\":\"livy-spark\",
    \"type\":\"GENERIC\",
    \"description\":\"Livy REST for Spark + Iceberg\",
    \"properties\":{
      \"url\":            \"$LIVY\",
      \"s3.endpoint\":    \"$SS_ENDPOINT\",
      \"s3.access.key\":  \"$SS_AK\",
      \"s3.secret.key\":  \"$SS_SK\",
      \"polaris.rest\":   \"$POLARIS_REST\",
      \"polaris.cred\":   \"$POLARIS_CRED\"
    }
  }"
```

## 2. Pre-stage the IcebergTest uberjar in S3

Same jar Phase 2b uses. Stage it once; all three DAGs reference the same `s3a://` path.

```bash
aws --endpoint-url $SS_ENDPOINT s3 cp \
  target/iceberg-test-1.0.0.jar \
  s3://lakehouse/jars/iceberg-test-1.0.0.jar
```

## 3. Write the three DAGs

The DAG bodies are identical in intent — `POST` a JSON body to `${conn.livy-spark.url}/batches`, poll the batch state, fail loudly if the batch ends in `dead` or `killed`. The only differences are the SDK surface (YAML / Python / Java).

### 3.1 YAML — `src/main/yaml/livy_iceberg_dag.yaml`

```yaml
name: spark-iceberg-via-livy-yaml
schedule: null    # manual trigger
tasks:
  - id: submit-and-wait
    type: shell
    command: |
      set -euo pipefail
      BATCH=$(curl -sSf -X POST "${conn.livy-spark.url}/batches" \
        -H 'Content-Type: application/json' \
        -d "{
          \"file\":      \"s3a://lakehouse/jars/iceberg-test-1.0.0.jar\",
          \"className\": \"com.chango.test.IcebergTest\",
          \"args\":      [\"iceberg.test.yaml_dag_livy_smoke\"],
          \"name\":      \"kiok-yaml-livy\",
          \"conf\": {
            \"spark.hadoop.fs.s3a.endpoint\":     \"${conn.livy-spark.s3.endpoint}\",
            \"spark.hadoop.fs.s3a.access.key\":   \"${conn.livy-spark.s3.access.key}\",
            \"spark.hadoop.fs.s3a.secret.key\":   \"${conn.livy-spark.s3.secret.key}\",
            \"spark.hadoop.fs.s3a.path.style.access\": \"true\"
          }
        }" | jq -r .id)
      echo "batch id: $BATCH"
      while true; do
        STATE=$(curl -sSf "${conn.livy-spark.url}/batches/$BATCH" | jq -r .state)
        echo "[$(date +%T)] state=$STATE"
        case "$STATE" in
          success) exit 0 ;;
          dead|killed)
            curl -sS "${conn.livy-spark.url}/batches/$BATCH/log" | jq -r '.log[]' | tail -50
            exit 1 ;;
        esac
        sleep 10
      done
```

### 3.2 Python SDK — `src/main/python/python_livy_iceberg_dag.py`

```python
from kiok import Dag, Conn, shell_task

dag = Dag("spark-iceberg-via-livy-python")

dag.task(shell_task(
    id="submit-and-wait",
    command=fr"""
set -euo pipefail
LIVY={Conn.ref("livy-spark", "url")}
BATCH=$(curl -sSf -X POST "$LIVY/batches" -H 'Content-Type: application/json' -d '{{
  "file": "s3a://lakehouse/jars/iceberg-test-1.0.0.jar",
  "className": "com.chango.test.IcebergTest",
  "args": ["iceberg.test.py_dag_livy_smoke"],
  "name": "kiok-python-livy",
  "conf": {{
    "spark.hadoop.fs.s3a.endpoint":     "{Conn.ref("livy-spark", "s3.endpoint")}",
    "spark.hadoop.fs.s3a.access.key":   "{Conn.ref("livy-spark", "s3.access.key")}",
    "spark.hadoop.fs.s3a.secret.key":   "{Conn.ref("livy-spark", "s3.secret.key")}",
    "spark.hadoop.fs.s3a.path.style.access": "true"
  }}
}}' | jq -r .id)
echo "batch=$BATCH"
while :; do
  STATE=$(curl -sSf "$LIVY/batches/$BATCH" | jq -r .state)
  echo "$(date +%T) $STATE"
  [ "$STATE" = "success" ] && exit 0
  case "$STATE" in dead|killed)
    curl -sS "$LIVY/batches/$BATCH/log" | jq -r '.log[]' | tail -50
    exit 1
  ;; esac
  sleep 10
done
"""
))
```

### 3.3 Java SDK — `src/main/java/com/chango/dags/JavaLivyIcebergDag.java`

```java
package com.chango.dags;

import com.cloudcheflabs.kiok.dag.KiokDag;
import com.cloudcheflabs.kiok.dag.Conn;
import com.cloudcheflabs.kiok.dag.tasks.ShellTask;

public class JavaLivyIcebergDag implements KiokDag {

    @Override
    public String name() { return "spark-iceberg-via-livy-java"; }

    @Override
    public void build(DagBuilder b) {
        String livy = Conn.ref("livy-spark", "url");
        String ep   = Conn.ref("livy-spark", "s3.endpoint");
        String ak   = Conn.ref("livy-spark", "s3.access.key");
        String sk   = Conn.ref("livy-spark", "s3.secret.key");

        b.task(ShellTask.builder()
            .id("submit-and-wait")
            .command(String.format("""
                set -euo pipefail
                BATCH=$(curl -sSf -X POST "%s/batches" -H 'Content-Type: application/json' -d '{
                  "file": "s3a://lakehouse/jars/iceberg-test-1.0.0.jar",
                  "className": "com.chango.test.IcebergTest",
                  "args": ["iceberg.test.java_dag_livy_smoke"],
                  "name": "kiok-java-livy",
                  "conf": {
                    "spark.hadoop.fs.s3a.endpoint":     "%s",
                    "spark.hadoop.fs.s3a.access.key":   "%s",
                    "spark.hadoop.fs.s3a.secret.key":   "%s",
                    "spark.hadoop.fs.s3a.path.style.access": "true"
                  }
                }' | jq -r .id)
                echo "batch=$BATCH"
                while :; do
                  STATE=$(curl -sSf "%s/batches/$BATCH" | jq -r .state)
                  echo "$(date +%%T) $STATE"
                  [ "$STATE" = "success" ] && exit 0
                  case "$STATE" in dead|killed)
                    curl -sS "%s/batches/$BATCH/log" | jq -r '.log[]' | tail -50
                    exit 1
                  ;; esac
                  sleep 10
                done
                """, livy, ep, ak, sk, livy, livy))
            .build());
    }
}
```

### Why all three are `shell` tasks

kiok's first-party task types are `shell`, `pyspark`, and `java` today. A native `livy` task type (with built-in retry / polling / log redirection) is a planned addition — for now `shell` + `curl` is the right tool. Once the native task lands, each of the bodies above shrinks to a one-line declaration.

## 4. Trigger + verify

### Via the kiok admin UI

1. **DAGs** → filter `livy` → click `spark-iceberg-via-livy-yaml` → **Trigger run**.
2. The **Run Log** view streams the curl-based polling output:
    ```
    batch id: 7
    [13:42:31] state=starting
    [13:42:41] state=running
    [13:43:01] state=running
    [13:43:11] state=success
    ```
3. Repeat for the Python and Java DAG.

### Via REST

```bash
for DAG in spark-iceberg-via-livy-yaml spark-iceberg-via-livy-python spark-iceberg-via-livy-java; do
  RID=$(curl -sSf -X POST "$KIOK/api/v1/dags/$DAG/runs" \
    -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' -d '{}' \
    | jq -r .runId)
  echo "$DAG → run $RID"
done
```

Poll any run's state with:

```bash
curl -sSf -H "Authorization: Bearer $KTOK" $KIOK/api/v1/runs/<runId> | jq '.state, .tasks'
```

Expected final state on each: `SUCCESS`, with the corresponding `iceberg.test.<dag>_dag_livy_smoke` table now holding three rows.

### Read back through Trino

```bash
trino --server $COORD_HOST:$COORD_PORT --user admin --catalog iceberg \
      --execute 'SELECT count(*) FROM test.yaml_dag_livy_smoke;
                  SELECT count(*) FROM test.py_dag_livy_smoke;
                  SELECT count(*) FROM test.java_dag_livy_smoke;'
```

Each query returns 3.

## 5. What changed vs Phase 3

| Aspect | Phase 3 (kiok → SSH → spark-submit) | Phase 3b (kiok → Livy REST) |
|---|---|---|
| kiok user's SSH key on Spark host | required | **not required** |
| Spark binaries on kiok host | required (for `spark-submit` CLI) | **not required** — kiok only calls HTTP |
| jar location | local FS on driver host or S3 | S3 only (Livy `/batches` requirement) |
| Knows which host is Spark master | yes (DAG hard-codes hostname) | **no** — Connection holds the Livy URL |
| Failure surface | SSH auth / sshd config / known_hosts | HTTP / DNS / Livy state |
| Auth | OS user (`spark`) | Livy (Trustless by default — front with chango UI Proxy / nginx) |

## Phase 3b exit checklist

- [ ] `GET /api/v1/connections | jq` lists `livy-spark` alongside `s3-shannon` and `polaris-rest`.
- [ ] `GET /api/v1/dags` lists the three new `…-via-livy-…` DAGs (origin `git` or `bundle`).
- [ ] Triggering each ends in `SUCCESS`; the corresponding `iceberg.test.<dag>_dag_livy_smoke` table holds three rows.
- [ ] Killing the Spark master temporarily makes the next DAG run fail in the polling loop (Livy returns `dead` for the batch) — the failure is visible in kiok's Run Log, not silent.

## Troubleshooting

- **`curl: (7) Failed to connect to … port 30000: Connection refused`** — Livy down. Restart it via chango admin (`POST /admin/api/spark/spark-main/restart`) or check the spark cluster status; the install may have skipped Livy if `livyNodes` was empty.
- **DAG run `SUCCESS` but Iceberg table is empty.** The batch jar didn't pick up the catalog config. Add `spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions` to the `/batches` `conf` map, or rebuild the uberjar with the Iceberg extension hard-coded in the `SparkSession.builder`.
- **`/batches` returns `Local path … cannot be added to user sessions`.** The `file` field must be `s3a://`, not `file:///`. Phase 3b is the path that forces every artifact into S3 by design.
- **Connection ref `${conn.livy-spark.url}` resolves to literal text.** kiok older than the Connection-resolver patch didn't substitute generic-typed connection properties; bump to the build that ships `src/main/{java,python,script,yaml}` convention (see kiok-gitsync) and re-trigger.
