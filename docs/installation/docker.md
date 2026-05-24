# Local Docker Cluster

For functional verification on a developer laptop, chango ships a one-command Docker bring-up: `tests/cluster/run.sh` in the chango source tree boots three Rocky 9 systemd containers, installs ansible offline on the master container, and runs the production `install.yml` against the three of them. The result is a real chango cluster — same KMS, same Ontul authz, same internal NIO protocol — just running inside Docker.

This is the recommended way to walk through the [tutorials](../tutorials/index.md). It is **not** a production deployment model.

## What you get

- 3 Rocky 9 containers: `chango-e2e-m1` (master + NM), `chango-e2e-n1`, `chango-e2e-n2` (NM)
- The actual chango distribution extracted under `/opt/chango` on each container
- Java 17 + Java 25 installed under `/opt/openlogic-openjdk-*`
- A real master, bundled ZooKeeper, and node managers — started by the same first-boot logic the production ansible install uses
- The admin UI exposed at `http://localhost:18100/admin/` on the host

The cluster's persistent state (chango master's KMS / IAM / metadata RocksDB, ZooKeeper data) lives on per-container named volumes so a `docker compose restart` does not wipe it.

## Prerequisites

| Tool | Why |
|---|---|
| Docker Desktop (or a Docker daemon) | runs the three Rocky 9 containers |
| ≥ 8 GiB of RAM allocated to Docker | chango master + ZK + 3 NMs + later components (Trino, Spark, …) |
| The chango source tree | the script lives at `tests/cluster/run.sh` |
| `~/.ssh/chango-pem` is **not** needed | the script ships its own e2e SSH key under `tests/cluster/.ssh/id_e2e` |

> Apple Silicon (M-series) Macs run the containers in `linux/amd64` emulation — Component packages in the bundle are amd64-only. Expect noticeably slower component startup than on a native amd64 host.

## One-time setup — build the lean tarball

The Docker e2e flow expects the chango lean tarball (`build/chango-<version>.tar.gz`) to already exist. From the chango repo root:

```bash
bash package.sh
# -> build/chango-3.0.0-SNAPSHOT.tar.gz
```

You only need to re-run `package.sh` after you change chango master / NM source.

## Bring the cluster up

```bash
bash tests/cluster/run.sh
```

This single command:

1. Assembles a `chango-with-comps` bundle by running `package/build-with-comps/build-with-comps.sh` against the lean tarball (downloading every component tarball + the JDKs into `ansible/roles/*/files/`).
2. Starts the three containers via `docker compose`.
3. Installs ansible-core on `chango-e2e-m1` from the bundled RPMs (offline).
4. Stages the ansible tree + a generated `CHANGO_MASTER_KEY` on `chango-e2e-m1` and runs `install.yml -i inventory-docker.yml`.
5. Polls the master's admin REST until `cluster/info` returns `ready: true` with all NMs registered.

Total runtime: 5 – 15 minutes depending on the host (slower on amd64-emulated Apple Silicon).

When it finishes you will see:

```
==> chango cluster is up.
    Admin UI:  http://localhost:18100/admin/   (login: admin / admin)
    Teardown:  bash tests/cluster/run.sh down
```

## Log in to the admin UI

Browse to `http://localhost:18100/admin/`, log in as `admin / admin`, change the password on first login. From here you can:

- watch the master + 3 NMs in **Cluster → Nodes**
- install components (Ontul, PostgreSQL, ShannonStore, Polaris, Trino, …) via the admin UI
- follow the [tutorials](../tutorials/index.md) which drive the same flow via REST

## Tear it down

```bash
bash tests/cluster/run.sh down
```

This runs `docker compose down -v` against the e2e compose project — containers + named volumes are removed, you start from a clean slate on the next `run.sh`.

## Adding a node manager — verifying `add-nodemanager.yml`

The Docker e2e includes a fourth container `chango-e2e-n3` defined behind a `profiles: ["add"]` so it does not come up with the initial cluster. Use it to exercise `ansible/add-nodemanager.yml`:

```bash
# Start n3
docker compose -p chango-e2e-cluster \
  -f tests/cluster/docker-compose.yml \
  --profile add up -d chango-n3

# Run add-nodemanager from inside m1 (the ansible controller)
KEY=$(docker exec chango-e2e-m1 cat /opt/chango/.master-key-bootstrap)
docker cp tests/cluster/inventory-docker-add-n3.yml \
  chango-e2e-m1:/root/ansible/inventory-docker-add-n3.yml
docker exec chango-e2e-m1 bash -lc "
  cd /root/ansible
  CHANGO_MASTER_KEY='$KEY' ansible-playbook \
    -i inventory-docker-add-n3.yml add-nodemanager.yml
"
```

After it finishes, `cluster/info` reports a third NM `nm-chango-n3-19998` as ready.

## Limitations

| Aspect | Notes |
|---|---|
| Performance | Apple Silicon hosts run amd64 emulation — Trino / Spark / Flink workloads will be markedly slower than on a native host. |
| Networking | Containers share the host's Docker network; component-to-component connections use container hostnames. The admin UI's only host-facing port is `18100`. |
| Persistence | Volumes survive `compose restart` but are wiped by `run.sh down`. Treat the cluster as ephemeral. |
| Sizing | The cluster has 3 NMs total (4 with `chango-n3`). Components in the [tutorials](../tutorials/index.md) are sized to fit; don't expect production-scale workloads to run. |

## Next

Once the Docker cluster reports ready, jump to [Tutorials](../tutorials/index.md). All commands in the tutorials run as-is against the Docker cluster — replace `<master-host>` with `localhost` and `8080` with `18100`.
