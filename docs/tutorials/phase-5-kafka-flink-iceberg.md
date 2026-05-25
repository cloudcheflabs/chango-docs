# Phase 5 — Kafka → Flink → Iceberg streaming (with Ontul RBAC)

The last four phases were batch — Trino ran SQL on Iceberg tables, Spark wrote them in batches, and Phase 4 maintained them on a schedule. Phase 5 closes the loop with **continuous ingestion**: a Flink streaming job reads JSON events from a Kafka topic, projects + flattens them, and writes the result into an Iceberg table — committing a new snapshot every checkpoint. Ontul RBAC gates the write the same way it gates Trino SELECT in Phase 1 and Spark INSERT in Phase 2, but with one caveat that matters for streaming engines: **Flink authz is table-level only** (Allow / Deny on `data:Select` / `data:Insert`), not row- or column-level. The reason is in the [authz scope memo](../features/iam.md#engine-coverage).

By the end of Phase 5 you will have:

1. A 1-broker Apache **Kafka** cluster (with **ZooKeeper** mode) installed by chango.
2. A Confluent **Schema Registry** running alongside that broker (optional; this tutorial uses plain JSON to keep the surface small).
3. A 1+1 Apache **Flink** standalone session cluster with the `chango-flink-authz` plugin wired in.
4. A **streaming job** (Flink Java uberjar) that consumes from `orders.raw`, parses each JSON record, and `INSERT`s into `iceberg.streaming.orders` via the same Polaris REST catalog the earlier phases used.
5. Ontul **RBAC**: a `flink-streamer` user in a `flink-writers` group with one policy allowing `data:Insert` on the streaming namespace. Submitting the same job as a different user fails fast with `Access Denied`.

## Topology

| Component | Count | Host |
|---|---|---|
| Kafka ZooKeeper | 1 | n1 |
| Kafka Broker | 1 | n2 |
| (optional) Schema Registry | 1 | n2 |
| Flink JobManager | 1 | n1 |
| Flink TaskManager | 1 | n2 |

> Production layouts run a 3-node ZK ensemble, ≥3 brokers, ≥2 JobManagers (HA), and many TaskManagers. The single-broker / single-TM layout below is the verification-grade minimum that still exercises every authz + Iceberg-sink code path.

## Pre-stop the heavies (single-host lab)

Free what Phase 2/3/4 left running before adding two more JVM-heavy clusters:

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/kiok/kiok-main/stop  || true
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/spark/spark-main/stop || true
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/trino/trino-main/stop || true
```

Keep ShannonStore, Polaris, PostgreSQL, Ontul, and the Trino Gateway up — Phase 5 read-back uses Trino, but the cluster only needs to be flipped on briefly at the end.

## Variables carried over

```bash
BASE=http://<master-host>:8080
TOK=<chango admin token>
N1=nm-chango-n1-19998
N2=nm-chango-n2-19998

# Ontul (Phase 0)
ONTUL_HOST=<chango-n1>
ONTUL_PORT=<ontul-master adminPort>
ADMIN_OTOK=<admin user OTOK from Ontul>

# ShannonStore (Phase 0)
SS_AK=<access key>
SS_SK=<secret key>
SS_ENDPOINT=http://chango-n2.chango.private:8080

# Polaris (Phase 1)
POLARIS_REST=http://chango-n2.chango.private:8180/api/catalog
CLIENT_SECRET=<polaris-root client secret>
POLARIS_CRED="polaris-root:$CLIENT_SECRET"
```

## 1. Install Kafka (ZooKeeper mode)

### Via the chango admin UI

1. In the sidebar's **Streaming** group click **Kafka**.
2. Click **Install new Kafka cluster**:
    - **Cluster ID** — `kafka-main`
    - **ZooKeeper nodes** — `chango-n1`
    - **Broker nodes** — `chango-n2`
    - **Schema Registry nodes** — `chango-n2` (leave empty if you don't want SR for this tutorial)
3. Click **Install** then **Start**. The card flips to `RUNNING` within ~30 seconds — broker + ZK + (optional) SR all come up together.

### Via REST

```bash
curl -sS -X POST $BASE/admin/api/kafka \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "{
    \"clusterId\":           \"kafka-main\",
    \"zkNodes\":             [\"$N1\"],
    \"brokerNodes\":         [\"$N2\"],
    \"schemaRegistryNodes\": [\"$N2\"]
  }"
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/kafka/kafka-main/start
```

Pin the broker bootstrap endpoint — every Kafka client (the Flink job, the test producer, the console consumer) uses it:

```bash
BROKER_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/kafka | \
              jq -r '.[] | select(.clusterId=="kafka-main") | .instances[]
                     | select(.role=="broker") | .host')
BROKER_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/kafka | \
              jq -r '.[] | select(.clusterId=="kafka-main") | .instances[]
                     | select(.role=="broker") | .config.clientPort // "9092"')
BOOTSTRAP="$BROKER_HOST:$BROKER_PORT"
echo "Kafka bootstrap: $BOOTSTRAP"
```

> **Plaintext listener.** Vanilla Apache Kafka in chango's bundle runs `PLAINTEXT` (no TLS, no SASL) — that is enough for an in-VPC verification setup. For production, install the Kafka cluster on the same node as the chango master only after pinning a SASL config; the chango installer accepts SASL JAAS as part of `KafkaConfigRequest`.

### 1.1 Create the source topic

```bash
sudo -u kafka /opt/components/kafka-main-broker-1/bin/kafka-topics.sh \
  --bootstrap-server $BOOTSTRAP \
  --create --topic orders.raw \
  --partitions 3 --replication-factor 1
# Created topic orders.raw.

sudo -u kafka /opt/components/kafka-main-broker-1/bin/kafka-topics.sh \
  --bootstrap-server $BOOTSTRAP --list
# __consumer_offsets
# orders.raw
```

### 1.2 Produce a handful of JSON events

A 3-line producer is enough to verify the Flink job picks up records right away. Use the kafka CLI on the broker host:

```bash
ssh chango-n2 'sudo -u kafka bash -lc "
cat <<EOF | /opt/components/kafka-main-broker-1/bin/kafka-console-producer.sh \
    --bootstrap-server '$BOOTSTRAP' --topic orders.raw
{\"order_id\":1001,\"customer_id\":42,\"country\":\"KR\",\"total\":12.50,\"ts\":\"2026-05-25T09:00:00Z\"}
{\"order_id\":1002,\"customer_id\":17,\"country\":\"JP\",\"total\":33.00,\"ts\":\"2026-05-25T09:01:30Z\"}
{\"order_id\":1003,\"customer_id\":42,\"country\":\"KR\",\"total\":58.20,\"ts\":\"2026-05-25T09:03:10Z\"}
EOF
"'
```

The records sit on `orders.raw` until a consumer drains them. The Flink job in §3 will be that consumer.

## 2. Install Flink with Ontul authz

### 2.1 Mint a long-lived Ontul service token for chango-flink-authz

The `chango-flink-authz` plugin calls Ontul's `/admin/iam/check` on every table the job touches. It needs a long-lived bearer token issued by Ontul:

```bash
FLINK_OTOK=$(curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/iam/keys \
  -H "Authorization: Bearer $ADMIN_OTOK" -H 'Content-Type: application/json' \
  -d '{"userId":"flink-system","comment":"chango-flink-authz service token"}' \
  | jq -r .token)
echo "$FLINK_OTOK" > ~/chango-secrets/ontul-otok-flink
```

This is the **service principal** for the plugin, not the user submitting the job. The plugin sends it as `Authorization: Token <FLINK_OTOK>` and Ontul resolves the *job-submitting user* from the request payload — exactly the same pattern Trino + Spark use.

### 2.2 Install the Flink cluster

#### Via the chango admin UI

1. In the sidebar's **Lakehouse Engines** group click **Flink**.
2. Click **Install new Flink cluster**:
    - **Cluster ID** — `flink-main`
    - **JobManager nodes** — `chango-n1`
    - **TaskManager nodes** — `chango-n2`
    - **Ontul authz endpoint** — `http://chango-n1.chango.private:18080` (the Ontul master adminPort).
    - **Ontul authz token** — paste `$FLINK_OTOK`.
3. Click **Install** then **Start**. The cluster card flips to `RUNNING` within ~30 seconds.

#### Via REST

```bash
curl -sS -X POST $BASE/admin/api/flink \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "{
    \"clusterId\":            \"flink-main\",
    \"jobmanagerNodes\":      [\"$N1\"],
    \"taskmanagerNodes\":     [\"$N2\"],
    \"ontulAuthzEndpoint\":   \"http://chango-n1.chango.private:18080\",
    \"ontulAuthzToken\":      \"$FLINK_OTOK\"
  }"
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/flink/flink-main/start
```

The chango installer auto-wires:

- The `chango-flink-authz` jar into `lib/` on every JobManager + TaskManager (table-level Allow/Deny against Ontul IAM).
- Flink 1.19 JVM `--add-opens` defaults for Java 17.
- A `conf/config.yaml` that binds rest + RPC on `0.0.0.0` and advertises the FQHN — UI Proxy auto-discovers the JobManager UI via the cluster registry.

Pin the JobManager REST endpoint — the Flink CLI uses it to submit jobs:

```bash
JM_HOST=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/flink | \
          jq -r '.[] | select(.clusterId=="flink-main") | .instances[]
                 | select(.role=="jobmanager") | .host')
JM_PORT=$(curl -sS -H "Authorization: Bearer $TOK" $BASE/admin/api/flink | \
          jq -r '.[] | select(.clusterId=="flink-main") | .instances[]
                 | select(.role=="jobmanager") | .config.restPort')
JM_REST=http://$JM_HOST:$JM_PORT
echo "JobManager REST: $JM_REST"
```

### 2.3 Reach the JobManager UI through the UI Proxy

Phase 3 hooked the UI Proxy auto-registration into the Flink service, so the JobManager web UI now appears at `http://<ui-proxy-host>:<ui-proxy-port>/` once you log in once with an Ontul user. See [UI Proxy](../features/ui-proxy.md) for the full SSO flow.

## 3. Build the Flink Kafka → Iceberg job

A small Java uberjar — Kafka source, JSON parsing, Iceberg sink writing to `iceberg.streaming.orders` via Polaris REST + S3A. Iceberg / Flink / Kafka connector / S3A jars are **provided** because chango Flink already bundles them in `lib/`.

`pom.xml`
```xml
<dependencies>
  <dependency>
    <groupId>org.apache.flink</groupId>
    <artifactId>flink-streaming-java</artifactId>
    <version>1.19.3</version>
    <scope>provided</scope>
  </dependency>
  <dependency>
    <groupId>org.apache.flink</groupId>
    <artifactId>flink-connector-kafka</artifactId>
    <version>3.2.0-1.19</version>
    <scope>provided</scope>
  </dependency>
  <dependency>
    <groupId>org.apache.iceberg</groupId>
    <artifactId>iceberg-flink-runtime-1.19</artifactId>
    <version>1.6.1</version>
    <scope>provided</scope>
  </dependency>
  <dependency>
    <groupId>org.apache.iceberg</groupId>
    <artifactId>iceberg-aws-bundle</artifactId>
    <version>1.6.1</version>
    <scope>provided</scope>
  </dependency>
  <dependency>
    <groupId>com.fasterxml.jackson.core</groupId>
    <artifactId>jackson-databind</artifactId>
    <version>2.17.2</version>
  </dependency>
</dependencies>
```

`OrdersStream.java`
```java
package com.chango.test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.table.api.bridge.java.StreamTableEnvironment;
import org.apache.flink.table.data.GenericRowData;
import org.apache.flink.table.data.RowData;
import org.apache.flink.table.data.StringData;
import org.apache.flink.types.RowKind;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

public class OrdersStream {

    public static void main(String[] args) throws Exception {
        String bootstrap     = req(args, "--bootstrap");
        String topic         = req(args, "--topic");
        String restUri       = req(args, "--polaris-rest");
        String credential    = req(args, "--polaris-cred");
        String warehouse     = req(args, "--warehouse");
        String s3Endpoint    = req(args, "--s3-endpoint");
        String s3Ak          = req(args, "--s3-ak");
        String s3Sk          = req(args, "--s3-sk");
        String submittingUser= req(args, "--user");        // for chango-flink-authz

        StreamExecutionEnvironment env =
                StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(10_000);  // commit a new Iceberg snapshot every 10s.
        env.getConfig().setGlobalJobParameters(
                org.apache.flink.api.java.utils.ParameterTool.fromArgs(args));

        // The chango-flink-authz plugin reads the submitting user from this key.
        env.getConfig().setGlobalJobParameters(
                org.apache.flink.api.java.utils.ParameterTool.fromMap(
                        java.util.Map.of("chango.authz.user", submittingUser)));

        KafkaSource<String> source = KafkaSource.<String>builder()
                .setBootstrapServers(bootstrap)
                .setTopics(topic)
                .setGroupId("orders-stream-" + submittingUser)
                .setStartingOffsets(OffsetsInitializer.earliest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        DataStream<String> raw = env.fromSource(
                source, WatermarkStrategy.noWatermarks(), "kafka-orders.raw");

        DataStream<RowData> rows = raw.map(new com.chango.test.JsonToRow());

        StreamTableEnvironment tEnv = StreamTableEnvironment.create(env);

        // Register the Polaris-backed Iceberg catalog identically to the
        // Phase 2 Spark setup; `chango-flink-authz` intercepts every read +
        // write the catalog issues.
        tEnv.executeSql(
            "CREATE CATALOG iceberg WITH (" +
            "  'type'='iceberg'," +
            "  'catalog-type'='rest'," +
            "  'uri'='" + restUri + "'," +
            "  'warehouse'='" + warehouse + "'," +
            "  'credential'='" + credential + "'," +
            "  'scope'='PRINCIPAL_ROLE:ALL'," +
            "  'header.X-Iceberg-Access-Delegation'=''," +
            "  'rest.access-delegation'='none'," +
            "  'io-impl'='org.apache.iceberg.aws.s3.S3FileIO'," +
            "  's3.endpoint'='" + s3Endpoint + "'," +
            "  's3.access-key-id'='" + s3Ak + "'," +
            "  's3.secret-access-key'='" + s3Sk + "'," +
            "  's3.path-style-access'='true'," +
            "  's3.region'='us-east-1'" +
            ")"
        );
        tEnv.executeSql("USE CATALOG iceberg");
        tEnv.executeSql("CREATE DATABASE IF NOT EXISTS streaming");
        tEnv.executeSql(
            "CREATE TABLE IF NOT EXISTS iceberg.streaming.orders (" +
            "  order_id    BIGINT," +
            "  customer_id BIGINT," +
            "  country     STRING," +
            "  total       DECIMAL(12,2)," +
            "  ts          TIMESTAMP_LTZ(6)" +
            ") PARTITIONED BY (country)"
        );

        tEnv.createTemporaryView("rows", rows,
                org.apache.flink.table.api.Schema.newBuilder()
                        .column("order_id",    "BIGINT")
                        .column("customer_id", "BIGINT")
                        .column("country",     "STRING")
                        .column("total",       "DECIMAL(12,2)")
                        .column("ts",          "TIMESTAMP_LTZ(6)")
                        .build());

        tEnv.executeSql(
            "INSERT INTO iceberg.streaming.orders " +
            "SELECT order_id, customer_id, country, total, ts FROM rows");

        env.execute("orders-stream-" + submittingUser);
    }

    private static String req(String[] args, String key) {
        for (int i = 0; i < args.length - 1; i++)
            if (args[i].equals(key)) return args[i + 1];
        throw new IllegalArgumentException("missing " + key);
    }
}
```

`JsonToRow.java`
```java
package com.chango.test;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.table.data.DecimalData;
import org.apache.flink.table.data.GenericRowData;
import org.apache.flink.table.data.RowData;
import org.apache.flink.table.data.StringData;
import org.apache.flink.table.data.TimestampData;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

public class JsonToRow implements MapFunction<String, RowData> {
    private static final ObjectMapper M = new ObjectMapper();

    @Override
    public RowData map(String json) throws Exception {
        JsonNode n = M.readTree(json);
        GenericRowData r = new GenericRowData(5);
        r.setField(0, n.get("order_id").asLong());
        r.setField(1, n.get("customer_id").asLong());
        r.setField(2, StringData.fromString(n.get("country").asText()));
        r.setField(3, DecimalData.fromBigDecimal(new BigDecimal(n.get("total").asText()), 12, 2));
        r.setField(4, TimestampData.fromInstant(OffsetDateTime.parse(n.get("ts").asText()).toInstant()));
        return r;
    }
}
```

Build the uberjar (Maven shade) the same way Phase 2 does — `mvn package` yields `target/orders-stream-1.0.0.jar`.

## 4. Wire Ontul RBAC for the streaming write

### 4.1 Create the user + group

```bash
# Create the operator who will submit the job.
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/iam/users \
  -H "Authorization: Bearer $ADMIN_OTOK" -H 'Content-Type: application/json' \
  -d '{"userId":"flink-streamer","password":"Stream2026Pw!","email":"flink-streamer@example"}'

# Create the group that will hold the policy.
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/iam/groups \
  -H "Authorization: Bearer $ADMIN_OTOK" -H 'Content-Type: application/json' \
  -d '{"groupName":"flink-writers","description":"Streaming writers"}'

curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/iam/users/flink-streamer/groups \
  -H "Authorization: Bearer $ADMIN_OTOK" -H 'Content-Type: application/json' \
  -d '{"groupName":"flink-writers"}'
```

### 4.2 Attach a policy that allows INSERT on the streaming namespace

`chango-flink-authz` checks every read with `data:Select` and every write with `data:Insert`, scoped to `data:table:<catalog>.<schema>.<table>`. The Flink job in §3 reads from Kafka (not gated by Ontul) and writes to `iceberg.streaming.orders` (gated). The minimum policy is:

```bash
cat > /tmp/iceberg-streaming-write.json <<'EOF'
{
  "name": "iceberg-streaming-write",
  "document": {
    "Version": "2024-01-01",
    "Statement": [
      {
        "Sid":      "StreamingInsert",
        "Effect":   "Allow",
        "Action":   ["data:Insert", "data:Select", "data:Create"],
        "Resource": "data:table:iceberg.streaming.*"
      },
      {
        "Sid":      "StreamingSchemaDdl",
        "Effect":   "Allow",
        "Action":   ["data:CreateSchema"],
        "Resource": "data:schema:iceberg.streaming"
      }
    ]
  }
}
EOF

curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/iam/policies \
  -H "Authorization: Bearer $ADMIN_OTOK" -H 'Content-Type: application/json' \
  --data @/tmp/iceberg-streaming-write.json

curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/iam/groups/flink-writers/policies \
  -H "Authorization: Bearer $ADMIN_OTOK" -H 'Content-Type: application/json' \
  -d '{"policyName":"iceberg-streaming-write"}'
```

> **No row-filter / column-mask for Flink.** The same `Condition` / `Columns` fields Phase 1 used for Trino are ignored by `chango-flink-authz` — the engine's table API does not expose a plan rewrite hook the plugin can use without re-implementing Calcite. The deliberate scope decision is recorded in [the engine-coverage memo](../features/iam.md#engine-coverage); for fine-grained policy on streaming reads you must filter at the source side (e.g. a topic-per-tenant + ACL).

## 5. Submit the streaming job

Run from any host that has the Flink CLI binary — chango Flink's JobManager install dir ships one:

```bash
ssh chango-n1 'sudo -u flink bash -lc "
/opt/components/flink-main-jobmanager-1/bin/flink run \
  --jobmanager '$JM_HOST:$JM_PORT' \
  --detached \
  /tmp/orders-stream-1.0.0.jar \
    --bootstrap     '$BOOTSTRAP' \
    --topic         orders.raw \
    --polaris-rest  '$POLARIS_REST' \
    --polaris-cred  '$POLARIS_CRED' \
    --warehouse     lakehouse \
    --s3-endpoint   '$SS_ENDPOINT' \
    --s3-ak         '$SS_AK' \
    --s3-sk         '$SS_SK' \
    --user          flink-streamer
"'
# Job has been submitted with JobID 86fa5e3b…
```

The job parses the three test records from §1.2, transforms them, and writes them into `iceberg.streaming.orders`. Because checkpointing is set to 10 s, the **first Iceberg commit lands ~10 s after job start**. Subsequent records from the same Kafka topic land in the next commit.

### 5.1 Monitor

JobManager UI (through UI Proxy):
- **Running Jobs** — the job's bar shows `RUNNING` with non-zero `Records Received`.
- **Checkpoints** — successive completed checkpoints with byte counts.
- **TaskManagers** — slot usage on the worker.

Logs from CLI:
```bash
ssh chango-n2 'sudo journalctl -u flink-main-taskmanager-1 --since "5 min ago"' | grep -E 'Committed|orders.raw|ontul'
```

Look for two key lines:

- `iceberg.streaming.orders ← committed snapshot <id>` (Iceberg sink commit).
- `chango-flink-authz: ALLOW user=flink-streamer action=data:Insert resource=data:table:iceberg.streaming.orders` (plugin authz log).

## 6. Verify the write through Trino

Flip Trino back on briefly and read the same Iceberg table:

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/trino/trino-main/start
# (wait until READY)

trino --server $COORD_HOST:$COORD_PORT --user admin --catalog iceberg \
  --execute 'SELECT order_id, country, total FROM streaming.orders ORDER BY order_id'
#  order_id | country | total
# ----------+---------+--------
#      1001 | KR      |  12.50
#      1002 | JP      |  33.00
#      1003 | KR      |  58.20
```

Three rows — one per Kafka message, partitioned by country, ready for ad-hoc SQL.

Run the producer from §1.2 again with `order_id` values `1004 / 1005`, wait one checkpoint, and re-query — the new rows appear. The job stays up.

## 7. Verify the DENY path

Submit the same job as a user that lacks the `iceberg-streaming-write` policy:

```bash
curl -sS -X POST http://$ONTUL_HOST:$ONTUL_PORT/admin/iam/users \
  -H "Authorization: Bearer $ADMIN_OTOK" -H 'Content-Type: application/json' \
  -d '{"userId":"flink-nobody","password":"Pw2026!","email":"flink-nobody@example"}'

ssh chango-n1 'sudo -u flink bash -lc "
/opt/components/flink-main-jobmanager-1/bin/flink run --jobmanager '$JM_HOST:$JM_PORT' \
  /tmp/orders-stream-1.0.0.jar \
    --bootstrap     '$BOOTSTRAP' \
    --topic         orders.raw \
    --polaris-rest  '$POLARIS_REST' \
    --polaris-cred  '$POLARIS_CRED' \
    --warehouse     lakehouse \
    --s3-endpoint   '$SS_ENDPOINT' \
    --s3-ak         '$SS_AK' \
    --s3-sk         '$SS_SK' \
    --user          flink-nobody
"'
```

The job is accepted by the JobManager (chango-flink-authz runs at table-load time, not submit time), but the first checkpoint logs:

```
chango-flink-authz: DENY user=flink-nobody action=data:Insert
                    resource=data:table:iceberg.streaming.orders reason=ABSTAIN
org.apache.flink.runtime.JobException: Recovery is suppressed by NoRestartBackoffTimeStrategy
Caused by: com.cloudcheflabs.chango.flink.authz.AuthzException:
  Access Denied: user flink-nobody not authorized for data:Insert on
  data:table:iceberg.streaming.orders (ontul decision: ABSTAIN — fail-closed)
```

The job transitions to `FAILED`, with no data appended to the Iceberg table. **Fail-closed** is the only mode `chango-flink-authz` supports — `fail-open: false` is hard-coded in the chango installer's rendered `config.yaml` so a misconfigured Ontul never silently allows writes.

## Phase 5 exit checklist

- [ ] `curl /admin/api/kafka/kafka-main | jq .status` returns `RUNNING`; `kafka-topics.sh --list` shows `orders.raw`.
- [ ] `curl /admin/api/flink/flink-main | jq .status` returns `RUNNING`; JobManager UI reachable through UI Proxy.
- [ ] `flink-streamer` job stays `RUNNING` after submission; TaskManager log shows `committed snapshot <id>`.
- [ ] Trino `SELECT … FROM iceberg.streaming.orders` returns the three test rows; producing a fourth record adds it within one checkpoint.
- [ ] `flink-nobody` submission fails with `chango-flink-authz: DENY … data:Insert` and no rows appear in the table.
- [ ] Ontul **Iceberg Maintenance** page (Phase 4) lists `iceberg.streaming.orders` as a candidate — the 6-hour cycle will now run `expire_snapshots` + `rewrite_data_files` against this streaming output too.

## Stop the streaming engines before the next phase

```bash
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/flink/flink-main/stop
curl -sS -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/kafka/kafka-main/stop
```

## Troubleshooting

- **JobManager UI shows `0 TaskManagers`** — TaskManager couldn't reach the JobManager's RPC port. Check `/admin/api/flink/flink-main | jq '.instances[].host'` resolves on the TaskManager host (`/etc/hosts` from the chango hosts-sync); the chango installer sets `jobmanager.rpc.address` to the JM's FQHN.
- **Iceberg sink throws `Failed to refresh token …`** — the `--polaris-cred` value (`client_id:client_secret`) is wrong. The credential comes from `GET /admin/api/polaris/polaris-main/credentials` and must be re-fetched after a Polaris re-install.
- **`chango-flink-authz: DENY` for a user you intended to allow** — the policy is missing `data:Create` or `data:CreateSchema` for the first job submission (the sink calls `CREATE TABLE IF NOT EXISTS`). Once the table exists, only `data:Insert` is needed; before then you also need `data:Create` + `data:CreateSchema`. The §4.2 policy includes all three.
- **First snapshot never lands** — either checkpointing didn't fire (TM log shows no `Triggering checkpoint`) or the Iceberg sink couldn't reach S3 (look for `S3 endpoint` errors). Verify `--s3-endpoint` reaches ShannonStore from the TM host; the chango admin's Network panel for `shannon-main` lists the live S3 endpoint.
- **DENY message says `reason=ABSTAIN` even though I attached a policy** — the policy didn't deserialize (PascalCase field-name pitfall from Phase 1 §5.2.1 applies to every Ontul policy). Re-read the policy via `GET /admin/iam/policies` and confirm `Statement` is populated.
