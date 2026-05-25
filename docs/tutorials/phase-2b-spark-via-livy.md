# Phase 2b — Spark via Livy REST (paired install, batch + interactive)

This phase is a variant of [Phase 2](phase-2-spark-iceberg.md). Where Phase 2 used `spark-submit` from the chango Spark master host, this phase submits the same workload over **HTTP** through Apache Livy. The shape of the Iceberg write is identical — what changes is the entry point: any HTTP client (kiok DAGs, BI tools, oncall scripts) can submit Spark jobs without SSH access and without a local Spark CLI.

By the end of the phase you will have:

1. A Spark cluster paired with a Livy server (one `livyNodes` entry in the install request — chango co-locates Livy with the Spark master and auto-wires `livy.spark.master`).
2. A small Java uberjar staged in S3 and submitted via `POST /batches` (the Livy equivalent of `spark-submit`).
3. An interactive Scala session created via `POST /sessions` running ad-hoc statements against the same Iceberg catalog.
4. Both write paths landing the same `iceberg.test.*` table that Trino reads back unchanged.

## Pre-stop

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/trino/trino-main/stop || true
```

Trino can stay stopped — Phase 2b only re-flips it on at the read-back step.

## Variables carried over

```bash
BASE=http://<master-host>:8080
TOK=<chango admin token>
N1=nm-chango-n1-19998
N2=nm-chango-n2-19998

# From Phase 0
ONTUL_HOST=<chango-n1>
ONTUL_PORT=<ontul-master adminPort>
ONTUL_OTOK=<service-principal OTOK from Ontul>
SS_AK=<ShannonStore access key>
SS_SK=<ShannonStore secret key>
SS_ENDPOINT=http://chango-n2.chango.private:8080

# From Phase 1
POLARIS_REST=http://chango-n2.chango.private:8180/api/catalog
POLARIS_CRED="polaris-root:<clientSecret>"
```

## 1. Install Spark with a paired Livy server

`SparkClusterRequest` takes a new `livyNodes` list. **Each Livy node must be co-located on the same NM as one of the Spark masters** — chango uses that master's install dir as Livy's `SPARK_HOME` so Livy can fork `spark-submit` against local binaries. Without co-location the install request is rejected with a clear error.

### Via the chango admin UI

1. **Spark** in the sidebar → **Install new Spark cluster**:
    - **Cluster ID** — `spark-main`
    - **Master nodes** — `chango-n1`
    - **Worker nodes** — `chango-n2`
    - **Livy nodes** — `chango-n1` (same NM as a Master).
    - **Ontul authz endpoint / token** — same OTOK Phase 2 used.
2. Click **Install** then **Start**. After ~30 s the cluster card lists four `RUNNING` roles: master, worker, livy, and (optional) history-server.

### Via REST

```bash
curl -sS -X POST $BASE/admin/api/spark \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "{
    \"clusterId\":           \"spark-main\",
    \"masterNodes\":         [\"$N1\"],
    \"workerNodes\":         [\"$N2\"],
    \"livyNodes\":           [\"$N1\"],
    \"ontulAuthzEndpoint\":  \"http://chango-n1.chango.private:18080\",
    \"ontulAuthzToken\":     \"$ONTUL_OTOK\"
  }"
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/spark/spark-main/start
```

Pin the Livy endpoint:

```bash
LIVY_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/spark | \
            jq -r '.[] | select(.clusterId=="spark-main") | .instances[] |
                   select(.role=="livy") | .host')
LIVY_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/spark | \
            jq -r '.[] | select(.clusterId=="spark-main") | .instances[] |
                   select(.role=="livy") | .config.port')
LIVY=http://$LIVY_HOST:$LIVY_PORT
curl -sS $LIVY/sessions | jq .   # { "from":0, "total":0, "sessions":[] }
```

The chango installer wires Livy with:

- `livy.spark.master = spark://<master-host>:<master-port>` — auto-discovered from the co-located Spark master.
- `livy.spark.deploy-mode = client` — interactive Livy RSC needs the driver inside Livy's JVM; `/batches` can override per request when the jar is S3-staged.
- 12 `--add-opens` for `spark.driver.extraJavaOptions` and `spark.executor.extraJavaOptions` (a sane default; Spark + Livy in chango run on Java 11 specifically so Livy 0.8's `SerializedLambda` reflection works).
- A minimal `conf/log4j.properties` so `logs/livy-spark-server.out` has actionable detail.

> **Java 11, not 17.** chango Spark targets JDK 11 because Livy 0.8 (the latest released line) was built against Java 8/11 and trips on the Java 17 module-system close-down at `java.lang.invoke.SerializedLambda`. Anything that the Livy session loads — including chango's own `chango-spark-authz` plugin jar — must therefore be compiled with `targetCompatibility = 11`.

## 2. Interactive session — Scala REPL with Iceberg

Livy interactive sessions are the cheapest way to verify the catalog + plugin wiring is alive. The session driver runs inside the Livy JVM (`client` deploy mode), so it picks up the Spark master's `jars/` (which already includes `iceberg-spark-runtime`, `iceberg-aws-bundle`, `hadoop-aws`, `aws-java-sdk-bundle`, and chango-spark-authz).

### 2.1 Create the session

```bash
SID=$(curl -sS -X POST $LIVY/sessions \
  -H 'Content-Type: application/json' \
  -d '{"kind":"spark","name":"phase2b-scala"}' | jq -r .id)
echo "session: $SID"

while true; do
  S=$(curl -sS $LIVY/sessions/$SID | jq -r .state)
  echo "state: $S"
  [ "$S" = "idle" ] && break
  [ "$S" = "dead" ] && { echo "FAILED — see logs/livy-spark-server.out"; exit 1; }
  sleep 5
done
```

Healthy progression: `starting` for ~20–30 s while spark-submit forks + the Livy RSC driver registers back, then `idle`. `dead` within ~5 s is almost always a `chango-spark-authz` class-version mismatch (the plugin jar was compiled against Java 17; rebuild with `targetCompatibility = 11`).

### 2.2 Write an Iceberg table from the session

The session shares one `SparkSession` across statements, so the catalog registration is done once:

```bash
register_catalog() {
  cat <<EOF
spark.conf.set("spark.sql.catalog.iceberg",                  "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.iceberg.catalog-impl",     "org.apache.iceberg.rest.RESTCatalog")
spark.conf.set("spark.sql.catalog.iceberg.uri",              "$POLARIS_REST")
spark.conf.set("spark.sql.catalog.iceberg.warehouse",        "lakehouse")
spark.conf.set("spark.sql.catalog.iceberg.credential",       "$POLARIS_CRED")
spark.conf.set("spark.sql.catalog.iceberg.io-impl",          "org.apache.iceberg.aws.s3.S3FileIO")
spark.conf.set("spark.sql.catalog.iceberg.s3.endpoint",      "$SS_ENDPOINT")
spark.conf.set("spark.sql.catalog.iceberg.s3.access-key-id", "$SS_AK")
spark.conf.set("spark.sql.catalog.iceberg.s3.secret-access-key", "$SS_SK")
spark.conf.set("spark.sql.catalog.iceberg.s3.path-style-access", "true")
spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.test")
spark.sql("CREATE TABLE IF NOT EXISTS iceberg.test.livy_session_smoke (id INT, label STRING) USING iceberg")
EOF
}

post_stmt() {
  local code=$1
  jq -n --arg c "$code" '{code:$c}' | \
    curl -sS -X POST $LIVY/sessions/$SID/statements \
      -H 'Content-Type: application/json' --data @-
}

post_stmt "$(register_catalog)" | jq -r .id
post_stmt "spark.sql(\"INSERT INTO iceberg.test.livy_session_smoke VALUES (1,'livy-1'),(2,'livy-2'),(3,'livy-3')\")" | jq -r .id
post_stmt "spark.sql(\"SELECT * FROM iceberg.test.livy_session_smoke ORDER BY id\").show()" | jq -r .id
```

Poll the last statement until `state: available`:

```bash
curl -sS $LIVY/sessions/$SID/statements/2 | jq '.state, .output.data."text/plain"'
```

Expected:

```
"available"
"+---+------+\n| id| label|\n+---+------+\n|  1|livy-1|\n|  2|livy-2|\n|  3|livy-3|\n+---+------+\n"
```

The three rows are in Iceberg, partitioned and snapshotted exactly the same way Phase 2's `spark-submit` write was.

### 2.3 Tear down the session

```bash
curl -sS -X DELETE $LIVY/sessions/$SID
```

## 3. Batch submission — `POST /batches` with an S3-staged jar

`/batches` is the spark-submit equivalent. Livy refuses local jar paths for batch (`Local path ... cannot be added to user sessions`) — the jar must be reachable from the Spark master's classpath at submit time. The easiest path: stage it in ShannonStore S3 with the same AK/SK already in use.

### 3.1 Build the same `IcebergTest` uberjar Phase 2 used

Identical `pom.xml` + `IcebergTest.java` as Phase 2 (Maven shade, `provided` for Spark/Iceberg/AWS, `package` → `target/iceberg-test-1.0.0.jar`).

### 3.2 Stage in S3

```bash
aws --endpoint-url $SS_ENDPOINT s3 cp \
  target/iceberg-test-1.0.0.jar \
  s3://lakehouse/jars/iceberg-test-1.0.0.jar
```

### 3.3 Submit via `/batches`

```bash
BATCH_ID=$(curl -sS -X POST $LIVY/batches \
  -H 'Content-Type: application/json' \
  -d "{
    \"file\":      \"s3a://lakehouse/jars/iceberg-test-1.0.0.jar\",
    \"className\": \"com.chango.test.IcebergTest\",
    \"args\":      [],
    \"name\":      \"phase2b-batch\",
    \"conf\": {
      \"spark.hadoop.fs.s3a.endpoint\":     \"$SS_ENDPOINT\",
      \"spark.hadoop.fs.s3a.access.key\":   \"$SS_AK\",
      \"spark.hadoop.fs.s3a.secret.key\":   \"$SS_SK\",
      \"spark.hadoop.fs.s3a.path.style.access\": \"true\"
    }
  }" | jq -r .id)
echo "batch: $BATCH_ID"

while true; do
  S=$(curl -sS $LIVY/batches/$BATCH_ID | jq -r .state)
  echo "state: $S"
  [ "$S" = "success" ] && break
  [ "$S" = "dead" ] || [ "$S" = "killed" ] && {
    curl -sS $LIVY/batches/$BATCH_ID/log | jq .
    exit 1
  }
  sleep 5
done
```

Expected: `starting` (~20 s) → `running` (~15 s while spark-submit + executors run + Iceberg commits) → `success`. The output of the Java main lives at `GET /batches/<id>/log`.

## 4. Read back through Trino

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/trino/trino-main/start
# wait READY

trino --server $COORD_HOST:$COORD_PORT --user admin --catalog iceberg \
      --execute 'SELECT id, label FROM test.livy_session_smoke ORDER BY id'
#  id |  label
# ----+--------
#   1 | livy-1
#   2 | livy-2
#   3 | livy-3
```

The same SQL works for the `IcebergTest` table from the batch path.

## 5. Differences from Phase 2

| Aspect | Phase 2 (`spark-submit`) | Phase 2b (Livy REST) |
|---|---|---|
| Entry point | Spark CLI on master host | HTTP POST from anywhere |
| Local jar | OK (`./target/...jar`) | Rejected; must be S3-staged for `/batches` |
| Driver placement | Cluster mode → spawned on worker | Client mode (Livy JVM) |
| Interactive REPL | N/A | `POST /sessions` + statements |
| Auth surface | OS / SSH to driver host | HTTP (Livy ships no auth by default — front with chango UI Proxy / nginx) |
| chango-spark-authz | Same plugin, same Ontul checks | Same plugin, same Ontul checks |

## Phase 2b exit checklist

- [ ] `curl /admin/api/spark/spark-main | jq '.instances[].role'` lists `master`, `worker`, `livy`.
- [ ] `curl $LIVY/sessions` returns 200 with an empty `sessions` array.
- [ ] Interactive session goes `starting → idle`, and the `SELECT * FROM iceberg.test.livy_session_smoke` statement returns three rows.
- [ ] `/batches` submission reaches `state:success` and Trino sees the resulting table.
- [ ] `chango-spark-authz` denials still fire for an Ontul user without `data:Insert` on the table — Livy entry point does not bypass the plugin.

## Troubleshooting

- **Session goes `dead` immediately + `livy-spark-server.out` shows `UnsupportedClassVersionError ... only recognizes class file versions up to 55.0`.** `chango-spark-authz` was compiled with `targetCompatibility = 17`; rebuild against 11 (chango Spark daemons run on JDK 11).
- **`POST /sessions` returns 200 but state stays `starting` for >2 min.** Spark master + worker reachable from the Livy host? `livy.spark.master` URL valid? Check `Connecting to master spark://...` in `livy-spark-server.out`; a `Connection refused` here means the master is on a different host or hasn't come up.
- **`POST /batches` returns `Local path ... cannot be added to user sessions`.** You passed `file:///...`; Livy whitelists local paths only via `livy.file.local-dir-whitelist`. The safe answer is to stage the jar in S3 and pass `s3a://`.
- **Batch `dead` with `IcebergSparkSessionExtensions ClassNotFoundException`.** The jar didn't pick up the chango-managed `spark-defaults.conf` `spark.sql.extensions` entry. Add it explicitly to the `/batches` `conf` map.

## Next

[Phase 3](phase-3-kiok-spark.md) used kiok → SSH → spark-submit. [Phase 3b — kiok → Livy DAGs](phase-3b-kiok-via-livy.md) replays the same DAG flow over Livy REST instead of SSH; that's the natural next step after Phase 2b.
