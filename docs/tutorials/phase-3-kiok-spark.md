# Phase 3 — kiok DAG scheduling a Spark submit (via SSH-to-master)

[Phase 2](phase-2-spark-iceberg.md) proved you can `spark-submit` a PySpark job (client mode) and a Java uberjar (cluster mode) by hand against a chango-managed Spark cluster, writing into Iceberg tables backed by ShannonStore. In this phase you will turn that same workload into a **DAG owned by kiok** — chango's workflow orchestrator — and let kiok schedule and trigger it on demand.

You will:

1. Install a kiok cluster (ZK + Master + Worker) on the same chango footprint.
2. Bridge kiok ↔ Spark with **passwordless SSH** so each kiok task `ssh`es into the Spark master and runs `spark-submit` there — kiok Workers carry no `SPARK_HOME` of their own.
3. Stash the S3 (ShannonStore) and Polaris (REST catalog) credentials inside kiok [Connections](https://cloudcheflabs.github.io/kiok-docs/features/connections/) so the DAG sources never carry plaintext secrets.
4. Author the same DAG three ways — **YAML**, **Python SDK**, **Java SDK** — and lay them out under `src/main/{script,python,java}/`. No `pom.xml`, no `gradle`, no pre-built jar: kiok's leader compiles every `.java` source in-process at sync time.
5. Deploy the source tree **two ways**: by git-sync from a real GitHub repo, and by a bundle zip upload. Both paths register the same three DAGs.
6. Trigger each DAG, watch the combined run-log view, and confirm Trino can read every table the DAGs wrote.
7. (Optional) Enable kiok's S3 job-log flush so each task's full stdout/stderr is archived to ShannonStore after the run.

> A deeper, kiok-flavoured walkthrough of step 4–7 lives in [kiok-docs · Spark + Iceberg via SSH-to-Master](https://cloudcheflabs.github.io/kiok-docs/tutorials/spark-iceberg-via-ssh/). This page covers the chango angle — provisioning the kiok cluster through chango admin, plus the foundation-aware steps that come before.

## Topology

```mermaid
flowchart LR
  subgraph chango-n1
    cm[chango master]
    kw1[kiok Worker]
  end
  subgraph chango-n2
    sm[Spark master + worker]
    bin[/opt/components/spark-main-master-1/bin/spark-submit]
    ssapi[ShannonStore API]
    pol[Polaris]
    kz1[kiok ZK]
    kkm[kiok Master]
  end
  subgraph chango-n3
    ssd[ShannonStore data]
    pg[PostgreSQL]
    kz2[kiok ZK]
  end
  kw1 -- passwordless ssh --> chango-n2
  bin --> sm
  sm -. read .-> ssapi
  sm -. catalog .-> pol
  pol -. data files .-> ssapi
  kkm -- gitsync pull --> github[(GitHub<br/>chango-dags repo)]
  kkm -- assigns runs --> kw1
```

The same three NMs from Phase 0 host kiok — its ZK ensemble on 2 NMs, one Master, one Worker — sharing hosts with the existing Foundation + Spark components.

## Variables carried over

```bash
BASE=http://<master-host>:8080
TOK=<chango admin token>
N1=nm-chango-n1-19998
N2=nm-chango-n2-19998
N3=nm-chango-n3-19998

# From Phase 0
SS_AK=<ShannonStore access key>          # for kiok S3 Connection
SS_SK=<ShannonStore secret key>
POLARIS_CRED='polaris-root:<polaris secret>'   # from Phase 1's catalog register step
```

You stopped Phase 2's Spark and Trino clusters at the end of that phase; for Phase 3 you only need **Foundation + Spark**. Trino stays stopped — we will not query through Trino in this phase. Bring Spark back up if you stopped it:

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/spark/spark-main/start
```

## 1. Install the kiok cluster

### Via the chango admin UI

1. Open `http://<master-host>:8080/admin/` and sign in.
2. In the left sidebar's **Workflow Orchestration** group click **kiok**.
3. Click **Install new kiok cluster**. A modal opens with these fields:
    - **Cluster ID** — type `kiok-main`.
    - **Master key** — click **Generate** to mint a random 32+ byte URL-safe string. (Copy it into your secret manager *before* you close the modal; chango stores it KMS-encrypted but never shows it again.)
    - **ZooKeeper nodes** — pick `chango-n2` and `chango-n3`. (Odd count rule — 1, 3, or 5.)
    - **Master nodes** — pick `chango-n2`.
    - **Worker nodes** — pick `chango-n1`.
4. Click **Install**. The modal closes and the cluster card flips to `INSTALLING`, then to `STOPPED` once every NM finishes the package push.
5. Click the **Start** button on the cluster card. Each ZK / Master / Worker instance row turns `RUNNING` over the next 20–40 seconds. The card surfaces the **Admin endpoint** (`http://chango-n2:18400`) as soon as the Master is up.

### Via REST

The equivalent calls:

```bash
KIOK_MASTER_KEY=$(openssl rand -base64 32)
curl -sS -X POST $BASE/admin/api/kiok \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "{
    \"clusterId\":   \"kiok-main\",
    \"masterKey\":   \"$KIOK_MASTER_KEY\",
    \"zkNodes\":     [\"$N2\",\"$N3\"],
    \"masterNodes\": [\"$N2\"],
    \"workerNodes\": [\"$N1\"]
  }"
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/kiok/kiok-main/start
```

`KIOK_MASTER_KEY` is the cluster's KMS master key; chango stores it KMS-encrypted at rest the same way as Ontul / ShannonStore master keys. Keep it in a real secret manager — losing it locks you out of the kiok metadata store.

Wait until every kiok instance is `RUNNING`:

```bash
curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/kiok/kiok-main \
  | jq '{status, nodes: [.nodes[] | {instanceId, role, status}]}'
```

Pull the kiok admin endpoint and rotate the default `admin/admin` password (same first-login flow as chango / Ontul / ShannonStore admin).

### Via the kiok admin UI

1. From the chango admin UI's **kiok** page, click the **Open admin UI** button on the `kiok-main` card. A new tab opens at `http://chango-n2:18400/`.
2. The login screen accepts `admin` / `admin`. Submit it.
3. The UI redirects to a **Change password** form (the only allowed endpoint until you rotate). Enter `admin` as the current password, then a strong new password twice. Submit.
4. Log back in with the new password. You're now on the kiok dashboard with a full JWT — every subsequent kiok action is available.

### Via REST

```bash
KIOK=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/kiok/kiok-main \
  | jq -r '.settings.adminEndpoint')
echo "$KIOK"  # → http://chango-n2:18400

# 1) Default login (kiok auth body uses `user`, not `username`)
ATOK=$(curl -sS -X POST $KIOK/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"user":"admin","password":"admin"}' | jq -r .accessToken)

# 2) Force-rotate (only the auth endpoints work until rotation is done)
curl -sS -X POST $KIOK/api/v1/auth/change-password \
  -H "Authorization: Bearer $ATOK" -H 'Content-Type: application/json' \
  -d '{"oldPassword":"admin","newPassword":"<your-strong-kiok-pw>"}'

# 3) Re-login + save the token for the rest of Phase 3
KTOK=$(curl -sS -X POST $KIOK/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"user":"admin","password":"<your-strong-kiok-pw>"}' | jq -r .accessToken)
```

## 2. Passwordless SSH: kiok Worker → Spark master

The kiok Worker runs as the Unix user `kiok` on `chango-n1`; the Spark master / Spark worker / `spark-submit` binary live as `spark` on `chango-n2`. Generate an ed25519 key for `kiok` and trust it on `spark`:

```bash
# On chango-n1 (kiok Worker host)
sudo -u kiok ssh-keygen -t ed25519 -N "" -f /home/kiok/.ssh/id_ed25519 -C "kiok@worker"
PUB=$(sudo cat /home/kiok/.ssh/id_ed25519.pub)

# On chango-n2 (Spark master host)
sudo mkdir -p /home/spark/.ssh && sudo chmod 700 /home/spark/.ssh
echo "$PUB" | sudo tee -a /home/spark/.ssh/authorized_keys
sudo chmod 600 /home/spark/.ssh/authorized_keys
sudo chown -R spark:spark /home/spark/.ssh

# Smoke test (from chango-n1)
sudo -u kiok ssh -o StrictHostKeyChecking=no spark@chango-n2 \
  'ls /opt/components/spark-main-master-1/bin/spark-submit'
# → /opt/components/spark-main-master-1/bin/spark-submit
```

This is the **only** host-side bridge between kiok and Spark — every DAG task from here on is a shell task that opens one SSH connection, runs one `spark-submit` on the remote side, and streams the output back.

## 3. Stash ShannonStore + Polaris credentials in kiok Connections

### Via the kiok admin UI

1. In the kiok admin UI (from step 1) click **Connections** in the left sidebar.
2. Click **New connection**. Fill in for the S3 connection:
    - **Connection ID** — `s3-shannon`
    - **Type** — `S3`
    - **Description** — `ShannonStore warehouse + uberjar`
    - **Properties** — add these key/value rows:

        | Key | Value |
        |---|---|
        | `endpoint` | `http://chango-n2.chango.private:8080` |
        | `region` | `us-east-1` |
        | `accessKey` | `$SS_AK` (your Phase 0 access key) |
        | `secretKey` | `$SS_SK` (your Phase 0 secret key) |
        | `pathStyleAccess` | `true` |

    Click **Save**. The row appears in the Connections list with the secret values redacted.
3. Click **New connection** again and create the Polaris connection:
    - **Connection ID** — `polaris-rest`
    - **Type** — `GENERIC`
    - **Description** — `Polaris REST catalog (Iceberg)`
    - **Properties** —

        | Key | Value |
        |---|---|
        | `uri` | `http://chango-n2.chango.private:8180/api/catalog` |
        | `warehouse` | `lakehouse` |
        | `oauthCredential` | `polaris-root:<polaris secret>` (your Phase 1 cred) |
        | `scope` | `PRINCIPAL_ROLE:ALL` |

    Click **Save**.
4. The Connections list now shows both `s3-shannon` and `polaris-rest`. Each row's "Open" affordance reveals only the property *keys* — the values are KMS-decrypted only at task-exec time on a Worker.

### Via REST

```bash
# S3 (ShannonStore — Phase 0 already gave you SS_AK / SS_SK)
curl -sS -X POST $KIOK/api/v1/connections \
  -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' \
  -d "{
    \"connectionId\":\"s3-shannon\",
    \"type\":\"S3\",
    \"description\":\"ShannonStore warehouse + uberjar\",
    \"properties\":{
      \"endpoint\":\"http://chango-n2.chango.private:8080\",
      \"region\":\"us-east-1\",
      \"accessKey\":\"$SS_AK\",
      \"secretKey\":\"$SS_SK\",
      \"pathStyleAccess\":\"true\"
    }
  }"

# Polaris (Phase 1 already gave you POLARIS_CRED)
curl -sS -X POST $KIOK/api/v1/connections \
  -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' \
  -d "{
    \"connectionId\":\"polaris-rest\",
    \"type\":\"GENERIC\",
    \"description\":\"Polaris REST catalog (Iceberg)\",
    \"properties\":{
      \"uri\":\"http://chango-n2.chango.private:8180/api/catalog\",
      \"warehouse\":\"lakehouse\",
      \"oauthCredential\":\"$POLARIS_CRED\",
      \"scope\":\"PRINCIPAL_ROLE:ALL\"
    }
  }"
```

Both records are KMS-encrypted at rest by kiok (`kiok.kms.master.key`). Inside a DAG you reference them as:

| Form | Reference |
|---|---|
| YAML | `${conn.s3-shannon.accessKey}` |
| Python SDK | `conn('s3-shannon', 'accessKey')` |
| Java SDK | `Conn.ref("s3-shannon", "accessKey")` |

All three produce the literal `${conn.s3-shannon.accessKey}` reference string; the Worker's `ConnectionResolver` swaps in the decrypted value immediately before the shell task is exec'd.

## 4. Build the DAG repo (source only)

Lay out the source tree under the recommended convention:

```
chango-dags/
└── src
    └── main
        ├── script
        │   └── spark_iceberg_dag.yaml
        ├── python
        │   └── spark_iceberg_dag.py
        └── java
            └── com/cloudcheflabs/dags
                └── SparkIcebergJavaDag.java
```

> **Why source-only?** Because kiok's leader runs `javax.tools.JavaCompiler` in-process at sync/upload time. A `.java` file in the repo needs no `pom.xml`, no `gradle`, no jar — kiok-sdk is already on the leader's classpath, so `Conn.ref(...)`, `Dag`, `KiokDag` resolve automatically. The original `.java` text is what the admin UI's **Source** tab shows operators, with the compiled `DagSpec` rendered just below it.

The three DAGs are identical in shape: **two tasks** in series — `pyspark_client_mode_write` first (PySpark in client deploy mode), then `java_spark_cluster_mode_write` (Java uberjar in cluster deploy mode). Each task is a single shell that opens one SSH session into the Spark master and runs one `spark-submit` there; all credentials come from kiok Connections via reference strings the Worker resolves immediately before exec.

### 4a — PySpark body uploaded to S3

Both deploy modes want `spark-submit` to fetch the workload from S3 the same way it fetches the uberjar. Stage one PySpark body per DAG (they differ only in target table name so we can tell which DAG wrote what). On any host with a Spark distribution available:

```python
# /tmp/yaml_pyspark.py — used by the YAML DAG.
# Make 2 more copies (py_pyspark.py and java_pyspark.py) changing only the
# table name in T (and the appName + label strings so you can identify the
# writer from the output).
from pyspark.sql import SparkSession
import os

C, N, T = "iceberg", "test", "yaml_dag_smoke"
spark = (SparkSession.builder.appName("kiok-yaml-pyspark")
    .config(f"spark.sql.catalog.{C}",              "org.apache.iceberg.spark.SparkCatalog")
    .config(f"spark.sql.catalog.{C}.catalog-impl", "org.apache.iceberg.rest.RESTCatalog")
    .config(f"spark.sql.catalog.{C}.uri",          os.environ["POLARIS_URI"])
    .config(f"spark.sql.catalog.{C}.warehouse",    "lakehouse")
    .config(f"spark.sql.catalog.{C}.credential",   os.environ["POLARIS_CRED"])
    .config(f"spark.sql.catalog.{C}.scope",        "PRINCIPAL_ROLE:ALL")
    .config(f"spark.sql.catalog.{C}.io-impl",      "org.apache.iceberg.aws.s3.S3FileIO")
    .config(f"spark.sql.catalog.{C}.s3.endpoint",         os.environ["S3_ENDPOINT"])
    .config(f"spark.sql.catalog.{C}.s3.access-key-id",    os.environ["S3_AK"])
    .config(f"spark.sql.catalog.{C}.s3.secret-access-key",os.environ["S3_SK"])
    .config(f"spark.sql.catalog.{C}.s3.path-style-access","true")
    .config(f"spark.sql.catalog.{C}.s3.region",           "us-east-1")
    .config("spark.sql.defaultCatalog", C).getOrCreate())

spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {C}.{N}")
spark.sql(f"DROP TABLE IF EXISTS {C}.{N}.{T}")
spark.sql(f"CREATE TABLE {C}.{N}.{T} (id INT, label STRING) USING iceberg")
spark.sql(f"INSERT INTO {C}.{N}.{T} VALUES (1, 'yaml-1'), (2, 'yaml-2'), (3, 'yaml-3')")
n = spark.sql(f"SELECT COUNT(*) AS n FROM {C}.{N}.{T}").collect()[0]["n"]
print(f"=== yaml-dag-pyspark wrote {n} rows ===")
spark.stop()
```

Make `py_pyspark.py` and `java_pyspark.py` by copying this file and changing:

- `T` from `yaml_dag_smoke` → `py_dag_smoke` / `java_dag_smoke`
- `appName` from `kiok-yaml-pyspark` → `kiok-py-pyspark` / `kiok-java-pyspark`
- label strings `yaml-1/2/3` → `py-1/2/3` / `java-1/2/3`
- the final `print` line accordingly

Then upload all three to `s3://pyspark-scripts/` with this one-shot Spark uploader:

```python
# /tmp/s3_upload.py — local-mode pyspark using the master's S3 config.
# spark-defaults.conf on the Spark master already carries fs.s3a.endpoint +
# AK/SK (Phase 0 wired them for the spark eventLog dir), so the uploader
# needs no inline credential config.
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("s3-uploader").getOrCreate()
hconf = spark.sparkContext._jsc.hadoopConfiguration()
jvm   = spark._jvm
URI, Path, FS = jvm.java.net.URI, jvm.org.apache.hadoop.fs.Path, jvm.org.apache.hadoop.fs.FileSystem
fs = FS.get(URI("s3a://pyspark-scripts/"), hconf)
fs.mkdirs(Path("s3a://pyspark-scripts/"))
for name in ("yaml_pyspark.py", "py_pyspark.py", "java_pyspark.py"):
    src = Path("file:///tmp/" + name)
    dst = Path("s3a://pyspark-scripts/" + name)
    if fs.exists(dst): fs.delete(dst, False)
    fs.copyFromLocalFile(False, True, src, dst)
    print("uploaded s3a://pyspark-scripts/" + name)
print("=== listing s3a://pyspark-scripts/ ===")
for st in fs.listStatus(Path("s3a://pyspark-scripts/")):
    print(st.getPath().toString(), st.getLen())
spark.stop()
```

```bash
# Run on the Spark master host (chango-n2):
scp /tmp/{yaml,py,java}_pyspark.py /tmp/s3_upload.py spark@chango-n2:/tmp/
sudo -u spark /opt/components/spark-main-master-1/bin/spark-submit \
  --master 'local[2]' --conf spark.eventLog.enabled=false \
  --driver-java-options '--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \
  /tmp/s3_upload.py
# → uploaded s3a://pyspark-scripts/yaml_pyspark.py
# → uploaded s3a://pyspark-scripts/py_pyspark.py
# → uploaded s3a://pyspark-scripts/java_pyspark.py
# → s3a://pyspark-scripts/yaml_pyspark.py 1689
# → ...
```

### 4b — The YAML DAG

`chango-dags/src/main/script/spark_iceberg_dag.yaml`:

```yaml
# Kiok DAG (YAML) — submit a PySpark client-mode write and a Java uberjar
# cluster-mode write to the spark cluster. The kiok worker doesn't need a
# local SPARK_HOME — each task SSHes (passwordless, kiok@chango-n1 → spark@chango-n2)
# into the spark master and runs spark-submit there. Credentials only via
# ${conn.<id>.<key>} refs the worker's ConnectionResolver substitutes before
# bash runs — this YAML never carries a plaintext secret.
dag:
  id: spark-iceberg-yaml
  name: spark-iceberg-yaml
  catchup: false
  defaultTimeoutMs: 600000

tasks:
  - id: pyspark_client_mode_write
    type: shell
    script: |
      #!/bin/bash
      set -euo pipefail
      SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR spark@chango-n2"
      $SSH "
        export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64
        export POLARIS_URI='http://chango-n2.chango.private:8180/api/catalog'
        export POLARIS_CRED='${conn.polaris-rest.oauthCredential}'
        export S3_ENDPOINT='${conn.s3-shannon.endpoint}'
        export S3_AK='${conn.s3-shannon.accessKey}'
        export S3_SK='${conn.s3-shannon.secretKey}'
        /opt/components/spark-main-master-1/bin/spark-submit \
          --master spark://chango-n2:7077 \
          --deploy-mode client --conf spark.eventLog.enabled=false \
          --driver-java-options '--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \
          --conf spark.executor.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \
          --conf spark.hadoop.fs.s3a.endpoint='${conn.s3-shannon.endpoint}' \
          --conf spark.hadoop.fs.s3a.access.key='${conn.s3-shannon.accessKey}' \
          --conf spark.hadoop.fs.s3a.secret.key='${conn.s3-shannon.secretKey}' \
          --conf spark.hadoop.fs.s3a.path.style.access=true \
          s3a://pyspark-scripts/yaml_pyspark.py
      "

  - id: java_spark_cluster_mode_write
    type: shell
    requires: [pyspark_client_mode_write]
    script: |
      #!/bin/bash
      set -euo pipefail
      SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR spark@chango-n2"
      $SSH "
        export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64
        /opt/components/spark-main-master-1/bin/spark-submit \
          --master spark://chango-n2:7077 \
          --deploy-mode cluster --conf spark.eventLog.enabled=false \
          --class com.cloudcheflabs.spark.IcebergSmoke \
          --conf spark.driver.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \
          --conf spark.executor.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \
          --conf spark.hadoop.fs.s3a.endpoint='${conn.s3-shannon.endpoint}' \
          --conf spark.hadoop.fs.s3a.access.key='${conn.s3-shannon.accessKey}' \
          --conf spark.hadoop.fs.s3a.secret.key='${conn.s3-shannon.secretKey}' \
          --conf spark.hadoop.fs.s3a.path.style.access=true \
          s3a://uberjar-upload/iceberg-smoke-java.jar
      "
```

Things to notice:

- Two `shell` tasks. `requires: [pyspark_client_mode_write]` says the cluster-mode task can only start after the client-mode task succeeds.
- The kiok Worker runs `$SSH "<remote command>"`. The remote-side `export X=...` lines + `spark-submit` all execute on `chango-n2`, where the real Spark distribution lives.
- `${conn.s3-shannon.accessKey}` is substituted by `ConnectionResolver` **before** bash parses the line, so the decrypted value only exists inside the (encrypted) SSH stream and the remote env vars; this YAML file is plaintext-safe.

### 4c — The Python SDK DAG

`chango-dags/src/main/python/spark_iceberg_dag.py`:

```python
"""Kiok DAG (Python SDK) — same workload as the YAML twin.
One ssh-then-spark-submit per task; pyspark script + java uberjar both live
in S3. Credentials only via conn(...).
"""
from kiok import Dag, conn

SSH = ('ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
       '-o LogLevel=ERROR spark@chango-n2')

# Pre-build the credential refs so the f-string inside the script body stays
# regex-friendly (the inner conn() call uses its own single quotes).
POLARIS_CRED = conn('polaris-rest', 'oauthCredential')
S3_ENDPOINT  = conn('s3-shannon',   'endpoint')
S3_AK        = conn('s3-shannon',   'accessKey')
S3_SK        = conn('s3-shannon',   'secretKey')

CLIENT_SCRIPT = f"""#!/bin/bash
set -euo pipefail
SSH="{SSH}"
$SSH "
  export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64
  export POLARIS_URI='http://chango-n2.chango.private:8180/api/catalog'
  export POLARIS_CRED='{POLARIS_CRED}'
  export S3_ENDPOINT='{S3_ENDPOINT}'
  export S3_AK='{S3_AK}'
  export S3_SK='{S3_SK}'
  /opt/components/spark-main-master-1/bin/spark-submit \\
    --master spark://chango-n2:7077 \\
    --deploy-mode client --conf spark.eventLog.enabled=false \\
    --driver-java-options '--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
    --conf spark.executor.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
    --conf spark.hadoop.fs.s3a.endpoint='{S3_ENDPOINT}' \\
    --conf spark.hadoop.fs.s3a.access.key='{S3_AK}' \\
    --conf spark.hadoop.fs.s3a.secret.key='{S3_SK}' \\
    --conf spark.hadoop.fs.s3a.path.style.access=true \\
    s3a://pyspark-scripts/py_pyspark.py
"
"""

CLUSTER_SCRIPT = f"""#!/bin/bash
set -euo pipefail
SSH="{SSH}"
$SSH "
  export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64
  /opt/components/spark-main-master-1/bin/spark-submit \\
    --master spark://chango-n2:7077 \\
    --deploy-mode cluster --conf spark.eventLog.enabled=false \\
    --class com.cloudcheflabs.spark.IcebergSmoke \\
    --conf spark.driver.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
    --conf spark.executor.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
    --conf spark.hadoop.fs.s3a.endpoint='{S3_ENDPOINT}' \\
    --conf spark.hadoop.fs.s3a.access.key='{S3_AK}' \\
    --conf spark.hadoop.fs.s3a.secret.key='{S3_SK}' \\
    --conf spark.hadoop.fs.s3a.path.style.access=true \\
    s3a://uberjar-upload/iceberg-smoke-java.jar
"
"""

dag = Dag("spark-iceberg-python", catchup=False, default_timeout="10m")
dag.task("pyspark_client_mode_write",     script=CLIENT_SCRIPT)
dag.task("java_spark_cluster_mode_write", script=CLUSTER_SCRIPT,
         requires=["pyspark_client_mode_write"])
```

Things to notice:

- Any module-level `Dag` instance is automatically picked up by `kiok.compile` at sync time. To define multiple DAGs in one file, just assign more module-level `Dag(...)` instances.
- `conn('s3-shannon', 'accessKey')` returns the literal string `${conn.s3-shannon.accessKey}` — the f-string just splices the reference into the script body. The actual credential is resolved at task-exec time on the Worker, not at compile time on the master.

### 4d — The Java SDK DAG

`chango-dags/src/main/java/com/cloudcheflabs/dags/SparkIcebergJavaDag.java`:

```java
package com.cloudcheflabs.dags;

import com.cloudcheflabs.kiok.sdk.Conn;
import com.cloudcheflabs.kiok.sdk.Dag;
import com.cloudcheflabs.kiok.sdk.KiokDag;

/**
 * Kiok DAG (Java SDK) — same workload as the YAML / Python twins. One ssh
 * then one spark-submit per task; pyspark script (java_pyspark.py) + java
 * uberjar both live in S3. Credentials only via Conn.ref(...).
 */
public class SparkIcebergJavaDag implements KiokDag {

    private static final String SSH =
            "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
          + "-o LogLevel=ERROR spark@chango-n2";

    private static final String POLARIS_CRED = Conn.ref("polaris-rest", "oauthCredential");
    private static final String S3_ENDPOINT  = Conn.ref("s3-shannon",   "endpoint");
    private static final String S3_AK        = Conn.ref("s3-shannon",   "accessKey");
    private static final String S3_SK        = Conn.ref("s3-shannon",   "secretKey");

    private static final String CLIENT_SCRIPT = """
            #!/bin/bash
            set -euo pipefail
            SSH="%s"
            $SSH "
              export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64
              export POLARIS_URI='http://chango-n2.chango.private:8180/api/catalog'
              export POLARIS_CRED='%s'
              export S3_ENDPOINT='%s'
              export S3_AK='%s'
              export S3_SK='%s'
              /opt/components/spark-main-master-1/bin/spark-submit \\
                --master spark://chango-n2:7077 \\
                --deploy-mode client --conf spark.eventLog.enabled=false \\
                --driver-java-options '--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
                --conf spark.executor.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
                --conf spark.hadoop.fs.s3a.endpoint='%s' \\
                --conf spark.hadoop.fs.s3a.access.key='%s' \\
                --conf spark.hadoop.fs.s3a.secret.key='%s' \\
                --conf spark.hadoop.fs.s3a.path.style.access=true \\
                s3a://pyspark-scripts/java_pyspark.py
            "
            """.formatted(SSH,
                    POLARIS_CRED, S3_ENDPOINT, S3_AK, S3_SK,
                    S3_ENDPOINT, S3_AK, S3_SK);

    private static final String CLUSTER_SCRIPT = """
            #!/bin/bash
            set -euo pipefail
            SSH="%s"
            $SSH "
              export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64
              /opt/components/spark-main-master-1/bin/spark-submit \\
                --master spark://chango-n2:7077 \\
                --deploy-mode cluster --conf spark.eventLog.enabled=false \\
                --class com.cloudcheflabs.spark.IcebergSmoke \\
                --conf spark.driver.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
                --conf spark.executor.extraJavaOptions='--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED' \\
                --conf spark.hadoop.fs.s3a.endpoint='%s' \\
                --conf spark.hadoop.fs.s3a.access.key='%s' \\
                --conf spark.hadoop.fs.s3a.secret.key='%s' \\
                --conf spark.hadoop.fs.s3a.path.style.access=true \\
                s3a://uberjar-upload/iceberg-smoke-java.jar
            "
            """.formatted(SSH, S3_ENDPOINT, S3_AK, S3_SK);

    @Override
    public Dag define() {
        Dag dag = new Dag("spark-iceberg-java")
                .catchup(false)
                .defaultTimeoutMs(600_000);
        dag.task("pyspark_client_mode_write").shell(CLIENT_SCRIPT);
        dag.task("java_spark_cluster_mode_write")
           .requires("pyspark_client_mode_write")
           .shell(CLUSTER_SCRIPT);
        return dag;
    }
}
```

There is **no `pom.xml`, no `build.gradle`, no `mvn package`**. The file goes into the repo as a plain `.java` source. The kiok leader runs `javax.tools.JavaCompiler` in-process at sync time with kiok-sdk on the master's classpath, so the `Conn`, `Dag`, and `KiokDag` imports resolve automatically. The original `.java` source text is what the admin UI's **Source** tab shows for this DAG.

## 5. Deploy

### Path A — git-sync (recommended)

Push the source tree to any git repo the kiok master can reach (we use `https://github.com/<your-org>/chango-dags.git`):

```bash
cd chango-dags
git init -b main && git add -A && git commit -m "spark-iceberg DAGs"
git remote add origin https://github.com/<your-org>/chango-dags.git
git push -u origin main
```

#### Via the kiok admin UI

1. In the kiok admin UI's left sidebar click **Settings → Git Sync**.
2. Click **Add repository**. Fill in:
    - **Name** — `chango-dags`
    - **URL** — `https://github.com/<your-org>/chango-dags.git`
    - **Ref** — `main`
    - **Tag** — leave unchecked (we are tracking a branch)
    - **Subpath** — leave empty (scan from the repo root)
    - **Credential connection** — leave empty for a public repo. For a private repo, first create a `GIT` connection on the Connections page with either `username` + `password` (a PAT works as the password) or a `privateKey` for SSH, then pick its id here.
3. Click **Save**. The repo appears in the list with the next-sync countdown.
4. Click **Sync now** on the repo row to skip the countdown. The leader pulls, batch-compiles every source, and registers the DAGs immediately.
5. Click **DAGs** in the sidebar — you should see three new rows, one per source format. Each row's **Source** tab shows the original `.yaml` / `.py` / `.java` text plus the compiled `DagSpec` JSON.

#### Via REST

```bash
curl -sS -X POST $KIOK/api/v1/admin/gitsync/repos \
  -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' \
  -d '{
    "name":"chango-dags",
    "url": "https://github.com/<your-org>/chango-dags.git",
    "ref": "main", "tag": false, "subpath": ""
  }'
curl -sS -X POST -H "Authorization: Bearer $KTOK" \
  $KIOK/api/v1/admin/gitsync/sync
```

Verify all three DAGs are registered (one per source format):

```bash
curl -sS -H "Authorization: Bearer $KTOK" $KIOK/api/v1/dags \
  | jq '[.[] | select(.origin == "git") | {id, name, sourcePath}]'
```

### Path B — bundle zip upload (alternative, for air-gapped sites)

#### Via the kiok admin UI

1. Zip the source tree on the operator machine: `cd chango-dags && zip -r /tmp/spark-iceberg-bundle.zip src`
2. In the kiok admin UI's sidebar click **Settings → DAG Bundles**.
3. Click **Upload bundle**. Fill in:
    - **Name** — `spark-iceberg-bundle` (this becomes the bundle's id; re-uploading under the same name overwrites the previous DAGs in-place but keeps their run history)
    - **File** — pick `spark-iceberg-bundle.zip` from your local filesystem.
4. Click **Upload**. The bundle row appears with a DAG count of 3. Any compile failures appear as expandable error chips against the bundle.
5. Click **DAGs** in the sidebar — you should see three more rows tagged `origin: bundle`.

#### Via REST

```bash
cd chango-dags && zip -r /tmp/spark-iceberg-bundle.zip src
curl -sS -X POST "$KIOK/api/v1/admin/bundles/spark-iceberg-bundle" \
  -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/zip' \
  --data-binary @/tmp/spark-iceberg-bundle.zip
```

The compile flow is identical to git-sync; the only difference is delivery.

## 6. Trigger + verify

### Via the kiok admin UI

1. Click **DAGs** in the sidebar. Filter by `spark-iceberg-yaml` (or pick the row directly).
2. Click the DAG name to open the **DAG detail** page. Click **Trigger run** in the top-right.
3. A modal asks for optional args — leave empty and click **Run**. The page redirects to the new run's **Execution** view.
4. The **Graph** tab shows the two-task graph with state badges (`PENDING` → `RUNNING` → `SUCCESS`). The **Job List** tab is a tabular row-per-task view with start/finish/elapsed columns; click **Log** on any row for the per-task modal.
5. The **Run Log** tab is the most useful view for this DAG: it shows **one combined stream** with the driver-orchestration events at the top followed by each task's full stdout/stderr in stacked sections, each with its own byte offset. Section headers stay stuck to the top while you scroll. For an active task the section is `LIVE` and polls every 2 seconds; once a task hits a terminal state the section stops polling but stays visible. This is where the `spark-submit`'s long `INFO` / `WARN` / `ERROR` stack of Iceberg metrics and S3A I/O lines lives.
6. When the run shows `SUCCESS` on both tasks, repeat the trigger from the `spark-iceberg-python` and `spark-iceberg-java` DAG pages to confirm all three formats behave identically.

### Via REST

```bash
DAG=chango-dags_src_main_script_spark_iceberg_dag  # the YAML one
RID=$(curl -sS -X POST "$KIOK/api/v1/dags/$DAG/runs" \
  -H "Authorization: Bearer $KTOK" -H 'Content-Type: application/json' -d '{}' \
  | jq -r .runId)

for i in $(seq 1 40); do
  R=$(curl -sS -H "Authorization: Bearer $KTOK" $KIOK/api/v1/runs/$RID)
  S=$(echo "$R" | jq -r .state)
  T=$(echo "$R" | jq -c '.tasks | with_entries(.value |= .state)')
  echo "[$i] $S $T"
  [ "$S" = "SUCCESS" ] || [ "$S" = "FAILED" ] && break
  sleep 10
done
```

A successful run progresses:

```
[1] PENDING {}
[2] RUNNING {"pyspark_client_mode_write":"RUNNING","java_spark_cluster_mode_write":"PENDING"}
[3] RUNNING {"pyspark_client_mode_write":"SUCCESS","java_spark_cluster_mode_write":"RUNNING"}
[4] SUCCESS {"pyspark_client_mode_write":"SUCCESS","java_spark_cluster_mode_write":"SUCCESS"}
```

Repeat the trigger + poll for the Python (`…python_spark_iceberg_dag.py_spark-iceberg-python`) and Java (`…java_spark-iceberg-java`) DAG ids to confirm all three behave identically.

### Read back the writes with `spark-sql` (or restart Trino briefly)

The DAGs created three Iceberg tables, one per source format:

| DAG | table |
|---|---|
| `spark-iceberg-yaml`   | `iceberg.test.yaml_dag_smoke` |
| `spark-iceberg-python` | `iceberg.test.py_dag_smoke` |
| `spark-iceberg-java`   | `iceberg.test.java_dag_smoke` |

Quick verification from any Spark host:

```bash
sudo -u spark /opt/components/spark-main-master-1/bin/spark-sql \
  --conf spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.iceberg.catalog-impl=org.apache.iceberg.rest.RESTCatalog \
  --conf spark.sql.catalog.iceberg.uri=http://chango-n2.chango.private:8180/api/catalog \
  --conf spark.sql.catalog.iceberg.warehouse=lakehouse \
  --conf spark.sql.catalog.iceberg.credential=$POLARIS_CRED \
  --conf spark.sql.catalog.iceberg.io-impl=org.apache.iceberg.aws.s3.S3FileIO \
  --conf spark.sql.catalog.iceberg.s3.endpoint=http://chango-n2.chango.private:8080 \
  --conf spark.sql.catalog.iceberg.s3.access-key-id=$SS_AK \
  --conf spark.sql.catalog.iceberg.s3.secret-access-key=$SS_SK \
  --conf spark.sql.catalog.iceberg.s3.path-style-access=true \
  -e "SELECT * FROM iceberg.test.yaml_dag_smoke ORDER BY id;
      SELECT * FROM iceberg.test.py_dag_smoke ORDER BY id;
      SELECT * FROM iceberg.test.java_dag_smoke ORDER BY id;"
```

Each table holds three rows — same shape, different `label` values that identify which DAG wrote them (`yaml-1`/`yaml-2`/`yaml-3` etc).

## 7. (Optional) Flush task logs to ShannonStore

By default kiok keeps each task's stdout/stderr in the leader's KMS-encrypted RocksDB indefinitely. For long-term retention or off-leader durability, point kiok's [Job Log](https://cloudcheflabs.github.io/kiok-docs/features/job-logs/) flush at ShannonStore — re-use the same S3 endpoint + AK/SK Phase 0 set up:

```bash
# Create the bucket once (use the same uploader from kiok-docs Step 3 with a
# different Path — fs.mkdirs(Path("s3a://kiok-joblogs/")))
# Then apply the seven kiok properties through chango's admin REST:
curl -sS -X POST $BASE/admin/api/kiok/kiok-main/config \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d "{
    \"properties\":{
      \"kiok.joblog.s3.endpoint\":  \"http://chango-n2.chango.private:8080\",
      \"kiok.joblog.s3.region\":    \"us-east-1\",
      \"kiok.joblog.s3.bucket\":    \"kiok-joblogs\",
      \"kiok.joblog.s3.path.style\":\"true\",
      \"kiok.joblog.s3.access.key\":\"$SS_AK\",
      \"kiok.joblog.s3.secret.key\":\"$SS_SK\",
      \"kiok.joblog.s3.prefix\":    \"joblogs\"
    }
  }"
```

chango rewrites every Master + Worker's `kiok.properties`, then restarts the cluster. After restart kiok's `JobLogService` starts a periodic flush thread:

- every `kiok.joblog.flush.interval.ms` (default 10s) it archives any task buffer that grew since the last flush;
- on task completion it does a final flush, then drops the leader's RocksDB buffer — so completed tasks read their log from `s3://kiok-joblogs/joblogs/<runId>/<taskId>.log` (KMS-encrypted by kiok) on next access.

Re-trigger any DAG and confirm the run still SUCCEEDs with no UI behaviour change — the read path falls back transparently when the in-leader buffer is empty.

## Phase 3 exit checklist

- [ ] `curl /admin/api/kiok/kiok-main | jq .status` returns `RUNNING` and every NM lists `RUNNING` nodes for ZK / Master / Worker.
- [ ] `sudo -u kiok ssh spark@chango-n2 hostname` from `chango-n1` works with no password and no key argument.
- [ ] `GET /api/v1/connections` lists `s3-shannon` and `polaris-rest`.
- [ ] `GET /api/v1/dags` lists the three DAGs (`spark-iceberg-yaml`, `spark-iceberg-python`, `spark-iceberg-java`) under `origin: git` — and three more under `origin: bundle` if you also did Path B.
- [ ] Triggering each DAG ends in `SUCCESS`; the corresponding `iceberg.test.<dag>_dag_smoke` table holds three rows.
- [ ] The admin UI's Run Log tab shows the driver events **and** every task's full `spark-submit` stdout in one continuous view.

## Stop kiok if you want before moving on

Phase 4 doesn't need kiok or Spark. To free their memory before continuing:

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/kiok/kiok-main/stop
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/spark/spark-main/stop
```

## Troubleshooting

- **Task fails with `Permission denied (publickey)` on the SSH step.** The `kiok` user's `~/.ssh/id_ed25519.pub` is not in `spark@chango-n2:/home/spark/.ssh/authorized_keys`, or that file's permissions are too open. Re-run step 2.
- **`spark-submit` succeeds locally but the kiok DAG run fails inside the script with `org.apache.iceberg.exceptions.BadRequestException: unauthorized_client`.** The `POLARIS_CRED` env-var that landed on the remote side is malformed — usually a `Conn.ref(...)` argument that doesn't match a stored Connection. Reissue `GET /api/v1/connections` and double-check the connection id + property names.
- **Task fails with `SecurityException: user 'spark' is not allowed to data:Insert`.** Ontul authz is gating the Spark catalog (Phase 1 wired up `chango-spark-authz`). Create the `spark` user in Ontul and put it in a group whose attached policy allows `data:Select`, `data:Insert`, `data:CreateSchema`, `data:Create`, `data:Drop` on `data:table:iceberg.test.*` + `data:schema:iceberg.test`.
- **The admin UI **Run Log** tab is empty though the run finished.** The page polls `tailTaskLog(runId, '__run__')` (driver events) plus each task. Make sure the kiok master is reachable from your browser and the JWT in local storage hasn't expired.
