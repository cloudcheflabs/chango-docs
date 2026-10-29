# Trust Store

When object storage or a query surface is served over HTTPS with a certificate
issued by a private (corporate) CA, everything that talks to it has to trust
that CA. Something that does not fails with `PKIX path building failed` — a
message that reads like a wrong address or a wrong credential, not like a
missing certificate.

chango distributes trusted certificates from one place, at two levels:

| Level | Who calls the HTTPS endpoint | Where to register |
|---|---|---|
| **Control plane** | chango itself — the PostgreSQL backup upload, its own backup and the backup pre-flight check, the Spark event-log prefix it creates at install | **Settings → Trust Store**, `/admin/api/truststore` |
| **Component** | an engine — Polaris, Trino, Trino Gateway, Spark, Flink, Ontul, kiok | the component's **Trust Store** tab, `/admin/api/<comp>/<clusterId>/truststore` |

The two are separate on purpose. Registering a CA for a component used to be
the only option, and the control plane trusted it only by accident — when that
component happened to run on the same JDK as the master, the certificate landed
in that JDK's `cacerts` and the master inherited it. On a host where every
component runs on a different JDK, the master's own calls failed with PKIX, and
the failure surfaced as a warning in one place (the event-log prefix) and as a
backup error with somebody else's name on it in another.

!!! tip "Register the CA, not the server certificate"
    A server (leaf) certificate works today and breaks the day it is renewed.
    Both screens flag a non-CA certificate as `CA 아님` (*not a CA*). Chain-verifying
    clients — Python, `curl`, `mc` — reject a leaf-only file outright, with
    `CERTIFICATE_VERIFY_FAILED` and nothing that points at the cause.

## Control plane — Settings → Trust Store

Sidebar → **Settings → Trust Store**. The page lists the registered certificates
and, for admins, a registration form.

| Column | What it shows |
|---|---|
| 파일 (*file*) | The file name, with a `CA 아님` badge when the certificate is not a CA |
| 주체 (*subject*) | The certificate's subject DN |
| 만료 (*expiry*) | `notAfter` as a local date and time, plus days left. Within 30 days it is shown in red |
| 이 마스터 (*this master*) | `적용 중` (*active*) when the file is present in this master's trust directory, `파일 없음` (*file missing*) when the record has it and this host does not |
| 등록 (*registered*) | When it was registered |

The **이 마스터** column is the one to read. It compares the cluster record
with the files this master actually composed into its TLS trust. When they
disagree, *this* master does not trust the certificate even though the record
says it is registered — so its backups to that endpoint fail while the other
master's succeed.

To register, paste the PEM into **인증서 (PEM)**, optionally give a
**파일 이름** (*file name*; blank means `chango-trust.pem`), and click
**Register**. The button reads *Paste a certificate first* until there is
something to register. Registering under an existing name overwrites it — that
is how you renew a certificate.

Delete is the trash icon on the row (admins only) and goes through a
confirmation: from that moment, the control plane's calls to a server whose
certificate this CA issued fail with `PKIX path building failed`, and the backup
is where that shows first. Run a backup after deleting to confirm.

Non-admins see the list and nothing else — no form, no delete.

### No restart

The master's S3 client does not read a JVM trust store. It builds its TLS
context from the JDK's default CAs **plus** every `.pem` / `.crt` file in the
trust directory (`/etc/chango/certs` by default, overridable with the
`chango.trust.dir` system property), and it re-reads that directory whenever a
file in it changes. So:

- a registration is in effect on the **next call**, with no master restart;
- the public CAs are never lost — the registered certificate is *added* to the
  JDK defaults, not substituted for them;
- a file may hold a chain; every certificate block in it is trusted.

Importing into the JDK's `cacerts` instead would need every master restarted,
and restarting masters is a hazard of its own.

### REST

```bash
# list
curl -s $BASE/admin/api/truststore -H "Authorization: Bearer $TOK"
```

```json
{
  "certificates": [
    {
      "fileName": "corp-root-ca.pem",
      "installedAt": 1761735600000,
      "subject": "CN=Corp Root CA,O=Example",
      "issuer": "CN=Corp Root CA,O=Example",
      "notAfter": 2108556302000,
      "daysLeft": 4012,
      "isCa": true,
      "sha256": "…"
    }
  ],
  "activeOnThisMaster": ["corp-root-ca.pem"],
  "directory": "/etc/chango/certs",
  "appliesWithoutRestart": true
}
```

`notAfter` and `installedAt` are epoch milliseconds. A record whose PEM cannot
be parsed carries `parseError` instead of the certificate fields.

```bash
# register (admin, leader)
curl -s -X POST $BASE/admin/api/truststore \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg pem "$(cat corp-root-ca.pem)" \
        '{certificate:$pem, fileName:"corp-root-ca.pem"}')"
#   → {"fileName":"corp-root-ca.pem","path":"/etc/chango/certs/corp-root-ca.pem",
#      "nodes":["nm-host1-…","nm-host2-…","nm-host3-…"],
#      "configKeys":{…}, "appliesWithoutRestart":true}

# or take the certificate a Trino Gateway TLS surface serves
curl -s -X POST $BASE/admin/api/truststore \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"gatewayClusterId":"tg-1"}'          # fileName defaults to tg-1.pem

# delete (admin, leader)
curl -s -X DELETE "$BASE/admin/api/truststore?fileName=corp-root-ca.pem" \
  -H "Authorization: Bearer $TOK"
#   → {"fileName":"corp-root-ca.pem","nodes":[…],"appliesWithoutRestart":true}
```

| Field | Notes |
|---|---|
| `certificate` | A PEM block. Anything without `-----BEGIN CERTIFICATE-----` is refused with `400` — an empty or malformed trust file would cost the public CAs too, and the only symptom would be PKIX |
| `fileName` | A plain file name, no `/` or `..`. `.pem` is appended when it ends in neither `.pem` nor `.crt` |
| `gatewayClusterId` | Instead of `certificate`: read the certificate a Trino Gateway nginx surface serves. Refused with `gateway '<id>' has no TLS certificate — apply its nginx surface first` when the surface does not exist yet. This pins the leaf — see the tip above |

The target is **every registered node manager**, not a list you pass — a master
host also runs a node manager, so the masters are covered. The certificates are
recorded on the control plane's own record so the list survives a master
restart and a leader change.

`GET` is open to any signed-in user; `POST` and `DELETE` are admin-only and
leader-only (a follower forwards them). All three run on the admin worker pool,
not the HTTP event loop, because a registration waits on every node manager.

!!! note "A node manager added later"
    The control-plane registration is pushed to the node managers registered at
    the time of the call. A host that joins afterwards does not receive it —
    unlike component certificates, which a scale-out replays. Register the same
    file name again after adding a node manager; it overwrites in place.

## Component Trust Store tab

Polaris, Trino, Trino Gateway, Spark, Flink and Ontul share a **Trust Store** tab in the
Configure drawer; kiok has its own. Two ways to supply the certificate:

- **인증서 붙여넣기** (*paste a certificate*) — paste your CA's PEM.
- **쿼리 창구에서 읽어오기** (*read it from the query surface*) — pick a Trino
  Gateway; chango reads the certificate that gateway's TLS surface is serving.
  The tab says what this does: it pins the certificate served today. When that
  certificate is renewed, run it again — or paste your **CA** certificate
  instead, which survives renewals and is what chain-verifying clients need.

```bash
curl -s -X POST $BASE/admin/api/<comp>/<clusterId>/truststore \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"certificate":"-----BEGIN CERTIFICATE-----…","fileName":"corp-ca.pem"}'
curl -s    "$BASE/admin/api/<comp>/<clusterId>/truststore" -H "Authorization: Bearer $TOK"
curl -s -X DELETE "$BASE/admin/api/<comp>/<clusterId>/truststore?fileName=corp-ca.pem" \
  -H "Authorization: Bearer $TOK"
```

`<comp>` is `polaris`, `trino`, `trino-gateway`, `spark`, `flink` or `ontul`. kiok has
its own route, `POST /admin/api/kiok/<clusterId>/truststore`, with the same
body (`certificate` + `fileName`, or `gatewayClusterId`); it has no `GET` or
`DELETE`, and its answer carries `taskConfigKeys` — the lines a DAG task needs.

!!! note "Register the catalog server too"
    Polaris writes table metadata to object storage itself — creating a table
    through its REST API, or committing on an engine's behalf, is Polaris
    opening the `https://` connection, on its own JDK (25). Registering the CA
    only on the query engine can look sufficient when that engine happens to
    share Polaris's JDK; it is not. Register it on the Polaris cluster as well,
    and check by creating a table through Polaris's REST API before any engine
    is involved.

**Registering the same `fileName` again** replaces the certificate on every
node, including the JDK `cacerts` entry of the same alias — use it to roll a
renewed CA. Deleting asks for confirmation in the tab, then removes the PEM
and the PKCS12 under `/etc/chango/certs/` on every node of the cluster.

!!! warning "Deleting does not withdraw the trust"
    The `cacerts` alias (`chango-<name>`) and the OS trust anchor stay — they
    are per JDK and per host, not per cluster, so another component on the same
    JDK may rely on the same entry. An engine therefore keeps trusting the CA
    after a delete and a restart. They are removed when the node manager is
    removed from that host (`remove-nodemanager.yml`). To withdraw a CA from a
    host that stays in service, remove the alias with `keytool -delete` from the
    engine's JDK `cacerts` and the anchor from `/etc/pki/ca-trust/source/anchors`
    followed by `update-ca-trust extract`, then restart the engines.

### What lands on each node

The certificate goes to **every node that runs an instance of the cluster**, at
the same path: `/etc/chango/certs/<fileName>`. The directory is world-readable
and deliberately not under `/opt/chango/conf`, which is `750` on master hosts
because it holds the master key — a product JVM could not read a certificate
there and would fall back to an empty trust store on some nodes only.

What else is built depends on how the engine reads TLS trust:

| Engine | What it reads | What chango does |
|---|---|---|
| kiok DAG tasks | The PEM, directly — the task's TLS settings accept PEM/JKS/PKCS12 and add the certificate to the default CAs | PEM |
| Every JVM engine — Polaris, Trino, Trino Gateway, Spark (and its drivers and executors), Flink (and its tasks), Ontul, kiok masters | **Its own JDK's `cacerts`**, which a JVM uses when no `javax.net.ssl.trustStore` is set | Imports the certificate into **that engine's JDK `cacerts`** and the OS trust anchors (`/etc/pki/ca-trust/source/anchors`, then `update-ca-trust extract`); also builds a PKCS12 (a copy of that `cacerts` plus your certificate) next to the PEM for anyone who wants an explicit `-Djavax.net.ssl.trustStore` |

**No JVM option is needed.** On the verification cluster not one running engine
JVM carries `-Djavax.net.ssl.trustStore`; every one trusts the private CA
through its JDK's `cacerts`. That is also why the example jobs submit to Spark
and Flink with no `-D` option and still read and write an `https://` endpoint:
executors, Spark drivers (client mode on a cluster node, or cluster mode on a
worker) and Flink tasks all run on the engine's JDK. A JVM on a developer's
machine is the one case that needs an explicit trust store.

The PKCS12 is a copy of `cacerts` because a store holding only your CA would make
the JVM lose every public CA, with the same PKIX message as before — pointing at
the certificate you just added rather than the ones that disappeared. The JDK
is the one the engine runs on (Trino 25, Spark 11, the others 17); a store built
from another JDK's `cacerts` is not what that engine reads, and other JDKs on
the host are left alone so one component's registration does not widen what
another trusts.

The `cacerts` and OS-anchor import exists because of Trino. Its S3 client goes
through the AWS SDK's Netty transport, which runs on BoringSSL
(`netty-tcnative`, shipped inside the engine's plugins) and never consults
`javax.net.ssl.trustStore`. With the option set and the store verified by
`keytool`, every query still failed with
`SSLHandshakeException: General OpenSslEngine problem`. The OS anchors serve the
same purpose for OpenSSL clients on the host — `mc`, `curl`, Python. The alias
is removed before it is imported, so re-registering a name replaces it.

### The response tells you what to configure

```json
{
  "clusterId": "spark-1",
  "componentType": "spark",
  "fileName": "corp-ca.pem",
  "path": "/etc/chango/certs/corp-ca.pem",
  "nodes": ["nm-host1-…", "nm-host2-…"],
  "trustStorePath": "/etc/chango/certs/corp-ca.p12",
  "trustStorePassword": "changeit",
  "configKeys": {
    "Master · Worker · History · Livy JVM 의 추가 옵션": "-Djavax.net.ssl.trustStore=/etc/chango/certs/corp-ca.p12 -Djavax.net.ssl.trustStorePassword=changeit -Djavax.net.ssl.trustStoreType=PKCS12",
    "spark-defaults.conf (드라이버)": "spark.driver.extraJavaOptions -Djavax.net.ssl.trustStore=…",
    "spark-defaults.conf (익스큐터)": "spark.executor.extraJavaOptions -Djavax.net.ssl.trustStore=…"
  }
}
```

`configKeys` holds lines to paste, keyed by where they go, because a mistyped
key is ignored silently and comes back only as PKIX. For the JVM engines these
lines are **optional** — the `cacerts` import already covers them; use them only
to pin a JVM to an explicit store. Never put a developer-machine path into
`spark.executor.extraJavaOptions`: executors run on the workers, where that file
does not exist, and an executor pointed at a missing store trusts nothing. For **Trino** the first
entry is `필요한 조작` (*action needed*): none — the registration already put the
certificate in the JDK trust store and the OS anchors, and a cluster restart
picks it up. The JVM option is listed after it as optional, for JSSE paths such
as a catalog REST endpoint over TLS. For **kiok** the lines are the per-task
`trino.ssl.trustStore` / `ontul.ssl.trustStore` / `livy.ssl.trustStore` keys
and the common `ssl.trustStore`. `trustStoreError` appears when the PEM landed
but the PKCS12 could not be built.

!!! warning "Registered is not the same as trusted by a running JVM"
    A JVM reads `cacerts` once, at startup. After a component registration the
    engine needs **a restart** before it trusts the new CA — no JVM option is
    required. Until then the symptoms do not name the certificate: Flink jobs
    stay `RUNNING` with no exception while every checkpoint fails with `PKIX`
    (an Iceberg sink commits on checkpoints, so the table stays empty), and
    Trino queries fail with `General OpenSslEngine problem`. Confirm with a real
    read and write against the HTTPS endpoint from the engine — not by looking at
    the file. The control plane is the exception: it reads the directory per call.

!!! note "One JDK per registration"
    The import goes into the JDK **that component** runs on (Spark 11; Trino and
    Polaris 25; the others 17). Other JDKs on the host are left alone, so register
    the CA on every component that talks to the endpoint — registering it on
    Spark alone leaves Trino on the same host refusing it. Replacing a JDK (for
    example with a new bundle) drops the import; register again.

### Listing, scale-out and delete

`GET` returns an array of `{fileName, installedAt, subject, issuer, notAfter,
daysLeft, isCa, sha256}` — the fingerprint is what tells you whether a
re-registration under the same name actually replaced the certificate. The tab
shows it as **지문 (SHA-256)**.

Each registration through `/<comp>/<clusterId>/truststore` is recorded on the
cluster (`trustCertificates` in its settings; certificates are public, so not
encrypted). A **scale-out** of Trino, Trino Gateway, Spark, Flink or Ontul
reinstalls the recorded certificates on the new node. kiok's route does not
record what it distributes, so after scaling kiok out, register again. A replay failure does not fail the scale-out — the master log
names the node and the certificate that did not land. Without the replay, a new
node is RUNNING and only the work scheduled onto it fails with PKIX, which reads
as an intermittent network fault.

`DELETE` removes the PEM (and the PKCS12) from every node of the cluster and
forgets the record. The response lists `removed` nodes and `failed` ones; when
any node failed it carries a `warning` — work scheduled to that node keeps
trusting the certificate. It does not remove the alias from the JDK `cacerts` or
the OS anchors.

## Rotating a CA

If only the server certificate changes and the issuing CA stays, nothing needs to
happen — that is the reason to trust the CA. If the **issuing CA** changes, the
order matters:

1. Register the new CA (control plane and every component that reads the
   endpoint) under a **new** file name, keeping the old one.
2. Restart the engines so their JVMs pick it up. The control plane needs no
   restart.
3. Switch the endpoint to the certificate issued by the new CA.
4. Confirm with real reads and writes, then delete the old CA's file.

Reversing steps 1–2 and 3 makes every engine fail at once.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Backup or PostgreSQL backup fails with `PKIX path building failed` | The control plane does not trust the CA — register it on **Settings → Trust Store**. Registering on a component does not reach the control plane |
| Spark install refused with `could not create the event log prefix …` | The same — the control plane creates that prefix itself, before any job; the message lists the private-CA trust as one of the causes |
| **이 마스터** shows `파일 없음` on one master | That master lacks the file; register the same name again |
| Trino queries fail with `General OpenSslEngine problem` after a registration | The cluster was not restarted since the certificate was imported into its JDK `cacerts` |
| Python / `curl` fail with `CERTIFICATE_VERIFY_FAILED`, Java works | A leaf was registered (`CA 아님`). Java accepts a leaf as a trust anchor; chain-verifying clients do not |
