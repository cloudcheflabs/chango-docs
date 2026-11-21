# Command Line — `changoctl`

`changoctl` is a remote client for the [admin API](../api/index.md): everything the admin console
does — installing and configuring components, catalogs, patches, trust stores, users, backups —
from a terminal, a script or a site file. Every admin API route is a command.

It is **not** the same tool as `bin/chango-cli.sh` on a master:

| | `changoctl` | `chango-cli` (on a master) |
|---|---|---|
| Where it runs | any host that reaches the admin API (operator PC, VDI, a build host) | on a master, as the account the master runs as (or root) |
| How it connects | the admin API over HTTP(S) | the master's local Unix socket — no network |
| Authentication | console login (user/password → token), the same permissions as the console | the operating-system account only, no login |
| What it does | every admin-console action | recovery: reset the admin password (`iam:reset-password`), the master key (`master-key`), control-plane backup restore (`backup`), `ping` |
| Master down | needs a running master | partly works (backup restore, master key) |

Keep `chango-cli` on the masters: it resets passwords without a login.

## Install

The bundle carries two files in `bin/`: `changoctl` (launcher) and `changoctl.jar`. Copy both to the
host you work from; they need a Java 17 runtime (`JAVA_HOME` or `java` on `PATH`). Do not put
`changoctl.jar` into the platform's `lib/`.

```bash
cp bin/changoctl bin/changoctl.jar ~/bin/
changoctl --help
```

## Log in

List every master — requests go to the first that answers; `502`/`503`/no connection moves on to
the next ([which master to call](../api/index.md#which-master-to-call)). The addresses and the session
are kept in `~/.changoctl/` (mode `0600`; `CHANGOCTL_HOME` moves it).

```bash
changoctl login -s https://node-1.example.com:8080 -s https://node-2.example.com:8080 -u admin
changoctl whoami
```

- The password comes from `--password-file FILE`, `CHANGOCTL_PASSWORD`, or a prompt.
- The access token is renewed automatically; the rotating refresh token is saved after every renewal.
- A user that must change the initial password is told to run `changoctl passwd`.
- A read-only console user can run every read command; changes come back `403` from the server.
- Private CA: `--cacert corp-root-ca.pem` (or `--insecure` for a test).

## Install one component at a time

Every field of the install request is a flag — the field name in kebab-case (`serverNodes` →
`--server-nodes`, `serverJvm.heapMax` → `--server-jvm-heap-max`); `--heap` sets every role's heap.
Node lists take host names. `--start` starts the cluster and waits for `RUNNING`. Values starting with
`@` are read from a file (`--password @pg.pw`). `changoctl <component> install --help` lists every flag
with its type, default and description.

```bash
changoctl postgres install pg-1 --node node-2 --port 5432 --password @pg.pw --start
changoctl ontul install ontul-1 --master-key @mk.txt --zks node-1,node-2,node-3 \
    --masters node-1,node-2 --workers node-1,node-2,node-3 --heap 1g --start
changoctl polaris install polaris-1 --servers node-1,node-2 --pg pg-1 \
    --s3-endpoint https://s3.example.com --s3-access-key @ak --s3-secret-key @sk --heap 2g --start
changoctl polaris catalog create polaris-1 lakehouse --bucket lakehouse
changoctl trino install trino-1 --coordinators node-1 --workers node-2,node-3 --start
changoctl trino catalog add trino-1 iceberg --polaris polaris-1 --catalog lakehouse \
    --s3-access-key @ak --s3-secret-key @sk
```

`--pg pg-1` fills the metastore host, port and password from that PostgreSQL instance;
`--polaris P --catalog C` writes the whole Iceberg REST catalog definition (front address, the
catalog's own principal, S3). The same works for `trino-gateway`, `spark`, `flink`, `kafka`,
`schema-registry`, `kiok` and `ui-proxy`.

A field the server would not read is refused before anything is sent:

```text
$ changoctl spark install spark-1 --masters node-1 --workers node-1,node-2,node-3 --heap 768m
changoctl: the server does not read these fields of SparkClusterRequest:
  s3PathStyle (did you mean 's3PathStyleAccess'?)
```

## Install a whole site from one file

`changoctl install -f site.yaml` runs the same per-component commands in dependency order —
PostgreSQL → IAM engine (Ontul) → Polaris (+ catalogs) → Trino (+ catalogs) → Trino Gateway → Spark →
Flink → Kafka → Schema Registry → workflow (Kiok) → UI Proxy — starting each and waiting for
`RUNNING` before the next. What already exists is left alone, so an interrupted run is finished by
running the same command again. `--dry-run` builds and checks every request and sends nothing;
`--only postgres,polaris` limits the run.

```yaml
credentialsDir: ./site-credentials      # admin passwords, service token, catalog principals (mode 600)

truststore:
  - cert: ./corp-root-ca.pem

postgres:
  - instanceId: pg-1
    node: node-2.example.com
    port: 5432
    password: ${env:PG_PASSWORD}

polaris:
  - clusterId: polaris-1
    serverNodes: [node-1, node-2]
    pg: pg-1
    s3Endpoint: https://s3.example.com
    s3AccessKey: ${env:S3_ACCESS_KEY}
    s3SecretKey: ${env:S3_SECRET_KEY}
    serverJvm: {heapMin: 256m, heapMax: 768m}
    catalogs:
      - name: lakehouse
        bucket: lakehouse
```

Keys are the request fields (camelCase) or the flag names; secrets come from `${env:NAME}` or
`${file:path}`. Add a block per component in the same way (`trino`, `trino-gateway`, `spark`, `flink`,
`kafka`, `schema-registry`, `kiok`, `ui-proxy` — each entry is the flags of that component's `install`).

## Check, watch, read logs, restart

```bash
changoctl status                      # masters, node managers, every cluster, fronts, patch level
changoctl status --problems           # only what is not healthy
changoctl status --watch 30           # redraw every 30 s, changes highlighted
changoctl logs polaris polaris-1 -n 200
changoctl logs polaris-1-server-1 --follow
changoctl restart all --yes           # stop in dependency order, start in reverse, RUNNING at each step
changoctl stop spark flink --yes
```

`status` exits `0` when everything is healthy and `1` otherwise, so it can drive a monitoring
check:

```text
$ changoctl status --problems ; echo $?
2026-11-21 00:57:09  8 problem(s)
  schema-registry sr-1 is STOPPED
  ...
1
```

Stop order: UI Proxy → workflow → Flink → Kafka → Spark → Trino Gateway → Trino → IAM engine → Polaris
(PostgreSQL only with `--include-storage`); start is the reverse.

## Patches

```bash
changoctl patch upload chango-patch.tgz
changoctl patch apply chango-3.0.0-<sha12>                    # the platform's own patch
changoctl patch apply polaris-1.4.1-<sha12> --cluster polaris-1
changoctl patch history --component polaris --cluster polaris-1
```

An apply that loses its connection (the master serving it restarts during a platform patch) is
not sent again — `changoctl` follows the recorded patch level until every host reports done.

## Any route

```bash
changoctl routes                      # the full route ↔ command table
changoctl api GET polaris/polaris-1/config
changoctl api POST polaris/polaris-1/config -d '{"ontulAuthzOp":"enable"}'
```

Global options: `-o table|json`, `--timeout SECONDS` (default 900), `--retries N`, `-v` (each request
and fail-over), `-y` (skip confirmations). Exit codes: `0` ok, `1` error or problems, `2` usage,
`3` login/forbidden, `4` not found, `5` no answer or not confirmed.
