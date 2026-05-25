# Phase 6 — kiok DAG (native `type: livy`) → Spark → Iceberg via Polaris REST

This phase verifies the full end-to-end path **kiok DAG → Livy → Spark → Iceberg (Polaris REST catalog) → ShannonStore S3**. It uses kiok 1.0.0's native `type: livy` task (no `shell` + `curl` workaround) and writes the same Spark job four ways — YAML, Python SDK, Java SDK with a cluster-mode uberjar, and a shell-task fallback. All four targets the same Polaris catalog that Ontul also reads (cross-engine verify).

> Why this phase, given Phase 3b already exists. Phase 3b was written before kiok shipped the native `type: livy` task — it wraps everything in `type: shell` + `curl`. Phase 6 uses the typed task directly, plus shows the cluster-mode-uberjar variant that Phase 3b omits.

## What you will end up with

- One kiok DAG bundle that ships **four** DAGs (YAML, Python, Java, Shell) — each runs the same Spark job through Livy and writes to the same Iceberg table
- A Java uberjar (~2 KB) staged in `s3a://<bucket>/jars/...`, submitted in **cluster deploy mode**
- A PySpark script staged in `s3a://<bucket>/scripts/...`, run in client deploy mode (PySpark cannot run cluster mode on Spark standalone)
- Iceberg writes landing under `s3://<polaris-warehouse>/<ns>/<table>-<uuid>/` (default base location from the Polaris catalog)
- Trino + Ontul both read the resulting table — cross-engine verification

## Prereqs

Complete:

- [Phase 0 — Foundation](phase-0-foundation.md) — Ontul + PostgreSQL + ShannonStore + Polaris + chango admin
- [Phase 1 — Trino + Iceberg + RBAC](phase-1-trino-iceberg-rbac.md) — Polaris catalog `lakehouse` (or your name) created with `stsUnavailable: true`, Ontul iceberg catalog registered, Trino iceberg catalog registered

Plus from chango admin:

- A Spark cluster installed **with Livy paired** — chango's Spark install accepts `livyNodes: [...]` (one entry per Livy server). The Livy host must be co-located with at least one Spark master so Livy can fork `spark-submit`.
- A kiok cluster installed and running (default admin credentials rotated; see [Phase 0](phase-0-foundation.md)).
- ShannonStore S3 access key + secret active (verify with `aws --endpoint-url <ss-api> s3 ls`).

## Variables

Shell prelude — paste once per terminal session:

```bash
# chango admin
export BASE=http://<chango-master>:8080
export CHANGO_USER=admin
export CHANGO_PW='<your chango admin password>'
export TOK=$(curl -sSf -X POST $BASE/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$CHANGO_USER\",\"password\":\"$CHANGO_PW\"}" \
  | jq -r .accessToken)

# kiok admin (JWT)
export KIOK=http://<kiok-master>:18400
export KIOK_USER=admin
export KIOK_PW='<your kiok admin password>'
export KTOK=$(curl -sSf -X POST $KIOK/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"user\":\"$KIOK_USER\",\"password\":\"$KIOK_PW\"}" \
  | jq -r .accessToken)

# Livy endpoint (the chango-provisioned Livy server)
export LIVY_URL=http://<spark-master-host>:30000

# Polaris REST catalog (chango-provisioned)
export POLARIS_REST=http://<polaris-host>:30000/api/catalog
export POLARIS_WAREHOUSE=lakehouse
export POLARIS_CID=polaris-root
export POLARIS_CS=<polaris client_secret from Phase 1>

# ShannonStore S3
export SS_ENDPOINT=http://<ss-api-host>:8080
export SS_REGION=us-east-1
export SS_BUCKET=chango-iceberg            # any bucket you own
export SS_AK=<live access key>
export SS_SK=<live secret key>

# Working bucket layout
export JAR_S3=s3a://$SS_BUCKET/jars/iceberg-demo-java-1.0.0.jar
export PY_S3=s3a://$SS_BUCKET/scripts/iceberg_polaris.py
```

> Bucket and key naming — pick whatever fits your environment. The values above are placeholders that match the rest of the doc.

## 1. Sanity-check the catalog

Confirm Polaris returns the **live** S3 keys for the warehouse (vending), and that the Ontul iceberg catalog points at the same warehouse:

```bash
# Polaris OAuth token
export PTOK=$(curl -sSf -X POST "$POLARIS_REST/v1/oauth/tokens" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=client_credentials \
  --data-urlencode client_id=$POLARIS_CID \
  --data-urlencode client_secret=$POLARIS_CS \
  --data-urlencode scope=PRINCIPAL_ROLE:ALL | jq -r .access_token)

# Vended defaults — s3.access-key-id MUST be the live key, not a stale one
curl -sSf -H "Authorization: Bearer $PTOK" \
  "$POLARIS_REST/v1/config?warehouse=$POLARIS_WAREHOUSE" | jq .defaults
```

> Trap — if `s3.access-key-id` here is the **old** key (from before a ShannonStore re-install), every Iceberg client will get `401 The AWS Access Key Id you provided does not exist`. Fix path is in the [Troubleshooting](#9-troubleshooting) section at the bottom — the Polaris JVM holds the keys as `-Daws.accessKeyId` system properties pinned at install time, so updating the catalog row alone is not enough.

## 2. Build the uberjar (Java)

`build.gradle` — Gradle Shadow plugin, `compileOnly` Spark + Iceberg so the jar carries only your business class:

```groovy
plugins {
  id 'java'
  id 'com.gradleup.shadow' version '8.3.6'
}
group = 'com.cloudcheflabs.sample'
version = '1.0.0'
java { toolchain { languageVersion = JavaLanguageVersion.of(11) } }
repositories { mavenCentral() }
dependencies {
  compileOnly 'org.apache.spark:spark-sql_2.12:3.5.8'
  compileOnly 'org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1'
}
shadowJar {
  archiveBaseName = 'iceberg-demo-java'
  archiveClassifier = ''
  manifest { attributes 'Main-Class': 'com.cloudcheflabs.sample.IcebergDemoJob' }
}
```

`src/main/java/com/cloudcheflabs/sample/IcebergDemoJob.java`:

```java
package com.cloudcheflabs.sample;

import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;

/** Hard-coded job — all catalog wiring is provided at submit time via --conf. */
public class IcebergDemoJob {
    public static void main(String[] args) {
        SparkSession spark = SparkSession.builder()
                .appName("kiok-livy-iceberg-polaris-java")
                .getOrCreate();
        System.out.println("##KIOK## SparkSession built");

        spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.maint");
        spark.sql("DROP TABLE IF EXISTS lakehouse.maint.java_orders");
        spark.sql(
            "CREATE TABLE lakehouse.maint.java_orders ("
          + "  id INT, amount DOUBLE, region STRING"
          + ") USING iceberg");
        System.out.println("##KIOK## table created");

        for (int i = 0; i < 5; i++) {
            spark.sql(
                "INSERT INTO lakehouse.maint.java_orders VALUES "
              + "(" + (i*10+1) + ", " + (i*10+1) * 1.5 + ", 'KR'), "
              + "(" + (i*10+2) + ", " + (i*10+2) * 1.5 + ", 'JP'), "
              + "(" + (i*10+3) + ", " + (i*10+3) * 1.5 + ", 'US')");
            System.out.println("##KIOK## INSERT batch " + (i+1));
        }
        long total = spark.sql("SELECT count(*) FROM lakehouse.maint.java_orders")
                .collectAsList().get(0).getLong(0);
        System.out.println("##KIOK## total rows = " + total);
        spark.stop();
    }
}
```

Build + stage:

```bash
./gradlew shadowJar
aws --endpoint-url $SS_ENDPOINT s3 cp \
    build/libs/iceberg-demo-java-1.0.0.jar  s3://$SS_BUCKET/jars/iceberg-demo-java-1.0.0.jar
```

## 3. Stage the PySpark script

`iceberg_polaris.py`:

```python
"""Same workload as the Java jar, but PySpark — runs in CLIENT deploy mode
(PySpark is not supported in cluster deploy mode on Spark standalone)."""
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("kiok-livy-iceberg-polaris-python")
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.lakehouse", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.lakehouse.type", "rest")
    .config("spark.sql.catalog.lakehouse.uri", "<POLARIS_REST>")
    .config("spark.sql.catalog.lakehouse.warehouse", "<POLARIS_WAREHOUSE>")
    .config("spark.sql.catalog.lakehouse.credential",
            "<POLARIS_CID>:<POLARIS_CS>")
    .config("spark.sql.catalog.lakehouse.scope", "PRINCIPAL_ROLE:ALL")
    # STS off — empty header disables Polaris vended-credentials, so Spark uses
    # the static S3 keys from the catalog properties (or below)
    .config("spark.sql.catalog.lakehouse.header.X-Iceberg-Access-Delegation", "")
    .config("spark.sql.catalog.lakehouse.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    .config("spark.sql.catalog.lakehouse.s3.endpoint",        "<SS_ENDPOINT>")
    .config("spark.sql.catalog.lakehouse.s3.access-key-id",   "<SS_AK>")
    .config("spark.sql.catalog.lakehouse.s3.secret-access-key", "<SS_SK>")
    .config("spark.sql.catalog.lakehouse.s3.path-style-access", "true")
    .config("spark.sql.catalog.lakehouse.s3.region",          "<SS_REGION>")
    .getOrCreate())

print("##KIOK## SparkSession built")
spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.maint")
spark.sql("DROP TABLE IF EXISTS lakehouse.maint.py_orders")
spark.sql("CREATE TABLE lakehouse.maint.py_orders "
          "(id INT, amount DOUBLE, region STRING) USING iceberg")
for i in range(5):
    spark.sql(f"INSERT INTO lakehouse.maint.py_orders VALUES "
              f"({i*10+1},{(i*10+1)*1.5},'KR'),"
              f"({i*10+2},{(i*10+2)*1.5},'JP'),"
              f"({i*10+3},{(i*10+3)*1.5},'US')")
    print(f"##KIOK## INSERT batch {i+1}")
total = spark.sql("SELECT count(*) FROM lakehouse.maint.py_orders").collect()[0][0]
print(f"##KIOK## total rows = {total}")
spark.stop()
```

Substitute placeholders and upload:

```bash
sed -e "s|<POLARIS_REST>|$POLARIS_REST|" \
    -e "s|<POLARIS_WAREHOUSE>|$POLARIS_WAREHOUSE|" \
    -e "s|<POLARIS_CID>|$POLARIS_CID|" \
    -e "s|<POLARIS_CS>|$POLARIS_CS|" \
    -e "s|<SS_ENDPOINT>|$SS_ENDPOINT|" \
    -e "s|<SS_AK>|$SS_AK|" \
    -e "s|<SS_SK>|$SS_SK|" \
    -e "s|<SS_REGION>|$SS_REGION|" \
    iceberg_polaris.py > /tmp/iceberg_polaris.rendered.py
aws --endpoint-url $SS_ENDPOINT s3 cp \
    /tmp/iceberg_polaris.rendered.py s3://$SS_BUCKET/scripts/iceberg_polaris.py
```

> Why the placeholders — the script is captured verbatim in your git history; the rendered copy with secrets only lives in S3.

## 4. Build the kiok DAG bundle — four variants

Layout:

```
iceberg-polaris-bundle/
├── src/main/yaml/livy_iceberg_yaml.yaml
├── src/main/python/livy_iceberg_python_dag.py
├── src/main/java/com/cloudcheflabs/iceberg/demo/LivyIcebergJavaDag.java
└── src/main/script/livy_iceberg_shell.sh
```

kiok's bundle scanner walks the whole zip and compiles by file extension. Below, each variant produces a distinct DAG id (so all four can coexist in the same bundle).

### 4.1 YAML — `src/main/yaml/livy_iceberg_yaml.yaml`

```yaml
dag:
  id: livy-iceberg-polaris-yaml
  defaultTimeoutMs: 600000
tasks:
  - id: spark_iceberg
    type: livy
    config:
      livy.url:  "<LIVY_URL>"
      livy.file: "<PY_S3>"
      livy.driverMemory:   "768m"
      livy.executorMemory: "768m"
      livy.pollIntervalMs: "3000"
      # When the script self-configures the catalog (as iceberg_polaris.py does),
      # leaving livy.conf empty is fine. Below are the s3a fallback creds used by
      # Spark's hadoop client (only required if the script references s3a:// at
      # runtime — for the catalog itself the script's own conf wins).
      livy.conf:
        spark.hadoop.fs.s3a.endpoint:               "<SS_ENDPOINT>"
        spark.hadoop.fs.s3a.access.key:             "<SS_AK>"
        spark.hadoop.fs.s3a.secret.key:             "<SS_SK>"
        spark.hadoop.fs.s3a.path.style.access:      "true"
        spark.hadoop.fs.s3a.connection.ssl.enabled: "false"
```

### 4.2 Python SDK — `src/main/python/livy_iceberg_python_dag.py`

```python
from kiok import Dag

LIVY = "<LIVY_URL>"
PY_S3 = "<PY_S3>"
SS_EP = "<SS_ENDPOINT>"
SS_AK = "<SS_AK>"
SS_SK = "<SS_SK>"

dag = Dag("livy-iceberg-polaris-python", default_timeout="10m")
dag.livy(
    "spark_iceberg",
    url=LIVY,
    file=PY_S3,
    conf={
        "spark.hadoop.fs.s3a.endpoint":               SS_EP,
        "spark.hadoop.fs.s3a.access.key":             SS_AK,
        "spark.hadoop.fs.s3a.secret.key":             SS_SK,
        "spark.hadoop.fs.s3a.path.style.access":      "true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
    },
    driver_memory="768m",
    executor_memory="768m",
    poll_interval_ms=3000,
)
```

### 4.3 Java SDK — `src/main/java/com/cloudcheflabs/iceberg/demo/LivyIcebergJavaDag.java`

The Java variant submits the **uberjar** (not a Python script) and uses the in-job catalog wiring (`--conf` from the DAG):

```java
package com.cloudcheflabs.iceberg.demo;

import com.cloudcheflabs.kiok.sdk.Dag;
import com.cloudcheflabs.kiok.sdk.KiokDag;

/**
 * Java DAG: Livy submits the uberjar; the SparkSession is built without any
 * catalog wiring in code — all Iceberg/Polaris/S3 conf comes from livy.conf.
 *
 * Cluster mode option: uncomment the spark.submit.deployMode line AND ensure
 * the Spark master/worker has access to the s3a:// uberjar (chango writes
 * conf/core-site.xml on every host so DriverRunner.downloadUserJar works).
 */
public class LivyIcebergJavaDag implements KiokDag {
    @Override
    public Dag define() {
        Dag dag = new Dag("livy-iceberg-polaris-java")
                .defaultTimeoutMs(10 * 60_000L);

        dag.task("spark_iceberg_java")
           .livy("<LIVY_URL>")
           .livyFile("<JAR_S3>")
           .livyClassName("com.cloudcheflabs.sample.IcebergDemoJob")
           .livyDriverMemory("768m")
           .livyExecutorMemory("768m")
           // Polaris REST catalog wiring (driver builds SparkSession without
           // these — they come via --conf so the same jar can target any
           // catalog without a rebuild).
           .livyConf("spark.sql.extensions",
                     "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
           .livyConf("spark.sql.catalog.lakehouse",            "org.apache.iceberg.spark.SparkCatalog")
           .livyConf("spark.sql.catalog.lakehouse.type",       "rest")
           .livyConf("spark.sql.catalog.lakehouse.uri",        "<POLARIS_REST>")
           .livyConf("spark.sql.catalog.lakehouse.warehouse",  "<POLARIS_WAREHOUSE>")
           .livyConf("spark.sql.catalog.lakehouse.credential", "<POLARIS_CID>:<POLARIS_CS>")
           .livyConf("spark.sql.catalog.lakehouse.scope",      "PRINCIPAL_ROLE:ALL")
           .livyConf("spark.sql.catalog.lakehouse.header.X-Iceberg-Access-Delegation", "")
           .livyConf("spark.sql.catalog.lakehouse.io-impl",          "org.apache.iceberg.aws.s3.S3FileIO")
           .livyConf("spark.sql.catalog.lakehouse.s3.endpoint",      "<SS_ENDPOINT>")
           .livyConf("spark.sql.catalog.lakehouse.s3.access-key-id", "<SS_AK>")
           .livyConf("spark.sql.catalog.lakehouse.s3.secret-access-key", "<SS_SK>")
           .livyConf("spark.sql.catalog.lakehouse.s3.path-style-access", "true")
           .livyConf("spark.sql.catalog.lakehouse.s3.region",        "<SS_REGION>")
           // Cluster mode (optional). Without it the driver runs inside the
           // Livy JVM (client mode) — fine for short jobs.
           // .livyConf("spark.submit.deployMode", "cluster")
           ;
        return dag;
    }
}
```

### 4.4 Shell DAG — `src/main/script/livy_iceberg_shell.sh`

The shell variant lets you wrap any pre-existing Livy / spark-submit recipe — useful for ops scripts that already exist. It uses kiok's `type: shell` task (with a `.sh` extension the bundle scanner treats it as a one-task DAG named after the file):

```bash
#!/bin/bash
set -euo pipefail

LIVY="<LIVY_URL>"
PY_S3="<PY_S3>"
SS_EP="<SS_ENDPOINT>"
SS_AK="<SS_AK>"
SS_SK="<SS_SK>"

BATCH=$(curl -sSf -X POST "$LIVY/batches" -H 'Content-Type: application/json' -d "{
  \"file\": \"$PY_S3\",
  \"driverMemory\": \"768m\",
  \"executorMemory\": \"768m\",
  \"conf\": {
    \"spark.hadoop.fs.s3a.endpoint\":               \"$SS_EP\",
    \"spark.hadoop.fs.s3a.access.key\":             \"$SS_AK\",
    \"spark.hadoop.fs.s3a.secret.key\":             \"$SS_SK\",
    \"spark.hadoop.fs.s3a.path.style.access\":      \"true\",
    \"spark.hadoop.fs.s3a.connection.ssl.enabled\": \"false\"
  }
}")
BID=$(echo "$BATCH" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "##KIOK## batch id=$BID"
for i in $(seq 1 60); do
  sleep 4
  STATE=$(curl -sSf "$LIVY/batches/$BID" | python3 -c "import sys,json;print(json.load(sys.stdin)['state'])")
  echo "##KIOK## state=$STATE"
  [ "$STATE" = "success" ] && exit 0
  [ "$STATE" = "dead" ] && { curl -sSf "$LIVY/batches/$BID/log?from=0&size=200"; exit 1; }
done
echo "##KIOK## TIMEOUT"; exit 2
```

> Why the shell variant — there is one less moving part (no `type: livy` SDK call), so when the typed task misbehaves you can A/B against it. The cost is your DAG hard-codes the polling loop.

## 5. Place-holder substitution + bundle

Substitute everywhere, zip, upload:

```bash
mkdir -p iceberg-polaris-bundle/src/main/{yaml,python,java/com/cloudcheflabs/iceberg/demo,script}
cp livy_iceberg_yaml.yaml         iceberg-polaris-bundle/src/main/yaml/
cp livy_iceberg_python_dag.py     iceberg-polaris-bundle/src/main/python/
cp LivyIcebergJavaDag.java        iceberg-polaris-bundle/src/main/java/com/cloudcheflabs/iceberg/demo/
cp livy_iceberg_shell.sh          iceberg-polaris-bundle/src/main/script/

find iceberg-polaris-bundle -type f \( -name '*.yaml' -o -name '*.py' -o -name '*.java' -o -name '*.sh' \) \
  -exec sed -i.bak \
    -e "s|<LIVY_URL>|$LIVY_URL|g" \
    -e "s|<PY_S3>|$PY_S3|g" \
    -e "s|<JAR_S3>|$JAR_S3|g" \
    -e "s|<POLARIS_REST>|$POLARIS_REST|g" \
    -e "s|<POLARIS_WAREHOUSE>|$POLARIS_WAREHOUSE|g" \
    -e "s|<POLARIS_CID>|$POLARIS_CID|g" \
    -e "s|<POLARIS_CS>|$POLARIS_CS|g" \
    -e "s|<SS_ENDPOINT>|$SS_ENDPOINT|g" \
    -e "s|<SS_AK>|$SS_AK|g" \
    -e "s|<SS_SK>|$SS_SK|g" \
    -e "s|<SS_REGION>|$SS_REGION|g" {} \;
find iceberg-polaris-bundle -name '*.bak' -delete

(cd iceberg-polaris-bundle && zip -r ../iceberg-polaris-bundle.zip src)
curl -sSf -X POST -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/zip' \
    --data-binary @iceberg-polaris-bundle.zip \
    $KIOK/api/v1/admin/bundles/iceberg-polaris
```

Verify all four compiled:

```bash
curl -sSf -H "Authorization: Bearer $KTOK" $KIOK/api/v1/admin/bundles | jq .
# expect: dagCount: 4, errors: []
```

## 6. Trigger + verify

Trigger each DAG:

```bash
for DAG in livy-iceberg-polaris-yaml \
           livy-iceberg-polaris-python \
           livy-iceberg-polaris-java \
           livy-iceberg-polaris-shell; do
  # The bundle scanner mangles the id with the bundle name + path; resolve it.
  REAL_ID=$(curl -sSf -H "Authorization: Bearer $KTOK" "$KIOK/api/v1/dags?q=$DAG" \
            | jq -r '.[0].id // empty')
  [ -z "$REAL_ID" ] && { echo "DAG $DAG not registered"; continue; }
  RID=$(curl -sSf -X POST -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' \
        -d '{}' "$KIOK/api/v1/dags/$REAL_ID/runs" | jq -r .runId)
  echo "$DAG -> $RID"
done
```

Poll a single run and tail its log:

```bash
curl -sSf -H "Authorization: Bearer $KTOK" "$KIOK/api/v1/runs/$RID" | jq .state
curl -sSf -H "Authorization: Bearer $KTOK" \
    "$KIOK/api/v1/runs/$RID/tasks/spark_iceberg/log" | grep '##KIOK##'
```

Expected markers (any of the variants):

```
##KIOK## SparkSession built
##KIOK## table created
##KIOK## INSERT batch 1
##KIOK## INSERT batch 5
##KIOK## total rows = 15
Livy batch N finished with state=success
```

S3 listing under the Polaris warehouse — each variant writes a separate table so all four land their own layout side by side:

```bash
aws --endpoint-url $SS_ENDPOINT s3 ls s3://$POLARIS_WAREHOUSE/maint/ --recursive | head -40
# Expect, per table:
#   .../maint/<table>-<uuid>/data/...parquet
#   .../maint/<table>-<uuid>/metadata/v<N>.metadata.json
#   .../maint/<table>-<uuid>/metadata/snap-...avro
```

## 7. Cross-engine verify (Trino + Ontul)

Trino — same Polaris catalog registered in [Phase 1](phase-1-trino-iceberg-rbac.md) as `ice`:

```bash
curl -sSf -X POST http://<trino-coordinator>:8480/v1/statement \
  -H 'X-Trino-User: admin' \
  -H 'Content-Type: text/plain' \
  --data 'SELECT region, count(*), sum(amount) FROM ice.maint.py_orders GROUP BY region ORDER BY region'
# follow nextUri until data
```

Ontul — same Polaris catalog registered as `iceberg` (Phase 4):

```bash
curl -sSf -X POST http://<ontul-master>:19220/v1/api/sql \
  -H "Authorization: Token $ONTUL_OTOK" \
  -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT region, count(*), sum(amount) FROM iceberg.maint.py_orders GROUP BY region ORDER BY region"}'
```

Both should report 15 rows split 5 per region.

## 8. Cluster deploy mode for the Java variant (optional)

The Java DAG can be flipped from client to cluster mode by:

1. Setting `livy.spark.deploy-mode = cluster` on the Spark+Livy cluster (chango admin → Spark page → Configure → Livy Overrides → add `livy.spark.deploy-mode = cluster`; the cluster restarts).
2. **Not** setting `spark.submit.deployMode` in the DAG — Livy hardcodes a `Blacklisted configuration values` reject for that key in session config. The server-side default (step 1) is the only supported lever.
3. Ensuring chango has emitted `conf/core-site.xml` on every Spark master + worker — this is automatic once the cluster's `s3Endpoint / s3AccessKey / s3SecretKey` are populated (chango admin → Spark → Configure → Job Log on S3 → Update). The driver bootstrap on the worker uses core-site.xml to fetch the `s3a://` uberjar before SparkConf is built.

PySpark cannot run in cluster mode on Spark standalone — keep the Python variant in client mode.

## 9. Troubleshooting

### S3 `401 The AWS Access Key Id you provided does not exist`

Polaris JVM pins `-Daws.accessKeyId` at install time. If your ShannonStore IAM was re-installed (or the original access key was deleted), the JVM still holds the dead key and every server-side I/O (metadata.json commit) fails — even when the catalog's `properties.s3.access-key-id` row is updated.

Workaround until chango ships a `polaris/<id>/credentials` endpoint:

```bash
# Trigger chango createCatalog with the live keys — its credsChanged branch
# also pushes them onto every Polaris instance's POLARIS_JAVA_OPTS and restarts.
curl -sSf -X POST -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  "$BASE/admin/api/polaris/polaris-main/catalogs" \
  -d "{\"name\":\"_creds_refresh_$(date +%s)\",
       \"s3Bucket\":\"_creds_refresh\",
       \"s3Endpoint\":\"$SS_ENDPOINT\",
       \"s3Region\":\"$SS_REGION\",
       \"s3AccessKey\":\"$SS_AK\",
       \"s3SecretKey\":\"$SS_SK\",
       \"s3PathStyleAccess\":true}"
```

The new throwaway catalog can be ignored; the side effect (JVM env + restart) is what you want.

### Polaris `Forbidden ... not authorized for op CREATE_TABLE_DIRECT_WITH_WRITE_DELEGATION`

You set `header.X-Iceberg-Access-Delegation: "vended-credentials"` and the Polaris principal does not have the write-delegation grant. Either set the header to empty (`""`) and rely on static credentials (the recipe in this phase), or grant the principal the necessary role on Polaris (`polaris-cli` or its REST API — out of scope here).

### Livy `Rejected, Reason: Blacklisted configuration values in session config: spark.submit.deployMode`

Livy 0.8 hard-codes a server-side block on `spark.submit.deployMode` from session conf, even when both blacklist properties are empty. Use chango's livyOverrides to set the cluster-wide `livy.spark.deploy-mode` instead — see section 8 above.

### Ontul `Could not initialize class org.apache.arrow.memory.util.MemoryUtil`

ontul-master on JDK 17 needs Arrow's `--add-opens` flags. Add to `/opt/components/ontul-main-master-1/conf/jvm.conf`:

```
--add-opens=java.base/java.nio=ALL-UNNAMED
--add-opens=java.base/java.lang=ALL-UNNAMED
--add-opens=java.base/java.lang.invoke=ALL-UNNAMED
--add-opens=java.base/java.util=ALL-UNNAMED
--add-opens=java.base/sun.nio.ch=ALL-UNNAMED
```

Then restart `ontul-main` from the chango admin UI.

### Cluster-mode driver bootstrap `s3a://...jar : 403 Forbidden`

The driver bootstrap on the worker uses hadoop's `core-site.xml`, not SparkConf. chango writes that file when `s3Endpoint / s3AccessKey / s3SecretKey` are populated; verify with:

```bash
ssh <worker-host> sudo cat /opt/components/spark-<cluster>-worker-N/conf/core-site.xml
```

If empty or stale, run `Configure → Job Log on S3 → Update` from the chango admin UI to re-emit the file across every Spark instance.

## Phase 6 exit checklist

- [ ] Bundle uploaded — `dagCount: 4, errors: []`
- [ ] Each DAG run finished with `state=SUCCESS`
- [ ] S3 layout under `s3://<warehouse>/maint/{yaml_orders,py_orders,java_orders,shell_orders}-<uuid>/` exists
- [ ] Trino `SELECT count(*)` returns 15 for at least one table
- [ ] Ontul `SELECT count(*)` returns 15 for at least one table

## What changed vs Phase 3b

| | Phase 3b | Phase 6 |
|---|---|---|
| Task type | `type: shell` + curl | Native `type: livy` |
| Variants | YAML / Python / Java (all wrap shell) | YAML / Python / Java / Shell (native + escape hatch) |
| Java SDK imports | `com.cloudcheflabs.kiok.dag.*` (pre-1.0 SDK) | `com.cloudcheflabs.kiok.sdk.*` (1.0 SDK) |
| Cluster mode | not covered | section 8 |
| Polaris cred rotation pitfall | not covered | section 9 |
