# Manual Install

This page brings up a chango cluster by running shell commands directly on each host — no ansible, no automation. Use it when you want full visibility of every step, when you are evaluating chango on a single host, or when ansible is not available on the controller (truly air-gapped, restricted network policy, etc.).

The end state is identical to the [automated install](automated.md): masters running on the chosen master hosts, a bundled ZooKeeper quorum running on the chosen ZK hosts (master and ZK groups are independent — master count is decoupled from ZK count), a node manager on every host, no systemd units, the cluster master key held only in operator-controlled secret storage.

## What you will install on each host

| Step | Master host | Node-manager host |
|---|---|---|
| Rocky 9 prep (SELinux / ulimit / sysctl) | ✓ | ✓ |
| Java 17 | ✓ | ✓ |
| Java 25 (for Trino) | ✓ | ✓ |
| chango distribution under `/opt/chango` | ✓ | ✓ |
| chango master + bundled ZK first start | ✓ | — |
| chango node manager first start | — | ✓ |

The chango tarball is the same on master and node-manager hosts. Roles are decided by which shell script you run, not which package you install.

## 1. Rocky 9 host prep

On **every** host (master + node managers), follow [Node Preparation](node-preparation.md) — SELinux disabled, ulimit and sysctl drop-ins, dedicated `/opt` mount. Quick recap of the manual steps:

```bash
# SELinux
sudo setenforce 0
sudo sed -i 's/^SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config

# ulimit
sudo tee /etc/security/limits.d/chango.conf > /dev/null <<'EOF'
*  soft  nofile  131072
*  hard  nofile  131072
*  soft  nproc   128000
*  hard  nproc   128000
EOF

# sysctl
sudo tee /etc/sysctl.d/99-chango.conf > /dev/null <<'EOF'
vm.max_map_count = 262144
net.core.somaxconn = 4096
fs.file-max = 2000000
EOF
sudo sysctl --system
```

## 2. Install Java 17 and Java 25

Chango itself runs on **Java 17**. Trino — deployed later via the admin UI on the node managers — needs **Java 25**. Install both on every host so any host can run any component.

```bash
# Java 17 — chango master / NM / most components
curl -L -O https://github.com/cloudcheflabs/chango-libs/releases/download/chango-comps/openlogic-openjdk-17.0.7+7-linux-x64.tar.gz
sudo tar -xzf openlogic-openjdk-17.0.7+7-linux-x64.tar.gz -C /opt

# Java 25 — Trino
curl -L -O https://github.com/cloudcheflabs/chango-libs/releases/download/chango-comps/openlogic-openjdk-25.0.3+9-linux-x64.tar.gz
sudo tar -xzf openlogic-openjdk-25.0.3+9-linux-x64.tar.gz -C /opt

# Verify
/opt/openlogic-openjdk-17.0.7+7-linux-x64/bin/java -version
/opt/openlogic-openjdk-25.0.3+9-linux-x64/bin/java -version
```

Both JDKs land under `/opt/`. Chango does **not** want them on `PATH` or set as the system `JAVA_HOME` — the start scripts take `JAVA_HOME` from the environment of the shell that launches them.

## 3. Create the `chango` user and base directories

On every host:

```bash
sudo groupadd -r chango || true
sudo useradd -r -g chango -s /bin/bash -d /opt/chango -M chango || true
sudo install -d -o chango -g chango /opt/chango /var/lib/chango /var/log/chango
```

Grant passwordless sudo for the `chango` user — chango needs it to deploy components (port allocator, host file sync, component install):

```bash
echo 'chango ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/chango
sudo chmod 0440 /etc/sudoers.d/chango
```

## 4. Download and extract chango

On every host:

```bash
curl -L -O https://github.com/cloudcheflabs/chango-pack/releases/download/chango-archive/chango-3.0.0.tar.gz
sudo tar -xzf chango-3.0.0.tar.gz -C /opt/chango --strip-components=1
sudo chown -R chango:chango /opt/chango
```

This is the **lean** distribution — chango master + node-manager binaries, bundled ZooKeeper, admin UI. Component packages (Trino, Spark, Flink, ShannonStore, Ontul, NeoRunBase, ItdaStream, kiok, Mium, …) are pulled separately by the master at component-install time.

If you want to pre-stage component packages on the master host (faster first install, useful in air-gapped environments), run:

```bash
sudo -u chango bash /opt/chango/build-with-comps/download.sh
```

This downloads every component tarball into `/opt/chango/components/`. The master reads from there when an operator clicks **Install** in the admin UI.

## 5. Generate the cluster master key

Once, on the master host:

```bash
export CHANGO_MASTER_KEY=$(openssl rand -base64 48 | head -c 48)
```

Treat this value the same way you would treat a root credential — it is the root of trust for every secret chango stores. Keep it in a real secret manager (Vault, AWS Secrets Manager, a hardware-backed password manager). You must re-supply this **exact** value:

- on every chango master restart,
- on every node-manager restart,
- when adding any new host later.

## 6. Start the master host

On the master host, two shells (or two `tmux` windows / two `screen` windows / a `systemd-run --scope` per process):

### Start the bundled ZooKeeper

```bash
export CHANGO_MASTER_KEY=<from your secret manager>
export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64

sudo -u chango -E /opt/chango/bin/start-zk.sh
```

### Start the chango master

```bash
export CHANGO_MASTER_KEY=<from your secret manager>
export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64

sudo -u chango -E /opt/chango/bin/start-master.sh \
    -Dchango.zk.serverList=<master-host>:2181
```

The master binds:

- `:8080` — admin HTTP (web UI + REST)
- `:19999` — internal NIO (master ↔ NM, encrypted with the cluster master key)

The first time the master starts, the KMS RocksDB under `/var/lib/chango/kms` is created and seeded from `CHANGO_MASTER_KEY`. From that point on, every later start of the same master needs the **same** master key to decrypt it.

## 7. Start each node manager

On every node-manager host:

```bash
export CHANGO_MASTER_KEY=<from your secret manager>
export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64

sudo -u chango -E /opt/chango/bin/start-node-manager.sh \
    -Dchango.zk.serverList=<master-host>:2181
```

The NM binds `:19998` (internal NIO). It registers itself in ZooKeeper, the master picks it up, and the admin UI shows it as a target for new components.

## 8. Verify

From any host that can reach the master's `:8080`:

```bash
curl -s http://<master>:8080/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}'
```

A response containing `accessToken` means chango is up. The default login is `admin` / `admin`; the first login forces a password change.

Web UI: `http://<master>:8080/admin/`

## Logs and pid files

| What | Where |
|---|---|
| chango master log | `/var/log/chango/master.log` |
| chango master console | `/var/log/chango/master.out` |
| bundled ZK log | `/var/log/chango/zk.log` |
| node manager log | `/var/log/chango/nodemanager.log` |
| process pid files | `/opt/chango/bin/*.pid` |

Pid files are port-suffixed (`master-8080.pid`, `node-manager-19998.pid`) so multiple instances per host coexist.

## Adding hosts manually

Need to add a node manager later? Same recipe on the new host — host prep → install Java 17/25 → create `chango` user → extract chango tarball → `start-node-manager.sh` with the same `CHANGO_MASTER_KEY` and the existing cluster's ZK list. See [Add another node manager](../operations/cluster-operations.md#add-another-node-manager).

Adding a second master is the same recipe plus extending the bundled ZooKeeper quorum — see [Add another chango master](../operations/cluster-operations.md#add-another-chango-master).

## Next

- [Getting Started](getting-started.md) — first login + first managed component.
- [Cluster Operations](../operations/cluster-operations.md) — day-2 lifecycle.
