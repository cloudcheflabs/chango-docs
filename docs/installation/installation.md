# Download & Install

This page walks through bringing a Chango cluster up on prepared Rocky 9 hosts. Before you start, every host must have been prepared per [Node Preparation](node-preparation.md) — SELinux disabled, ulimit and sysctl raised, `/opt` mounted, passwordless SSH from the master host.

## What ansible does — and what it does not

Chango uses ansible **only for the first install**. The playbook:

- creates the `chango` system user and base directories on every host,
- extracts the chango distribution under `/opt/chango`,
- starts the chango master, the bundled ZooKeeper, and every node manager **exactly once** (the first boot).

After the playbook finishes, ansible is out of the picture. Stopping, restarting, adding another master, and adding another node manager are all done by the operator running shell scripts on the host directly — no systemctl, no chango systemd units. See [Cluster Operations](../operations/cluster-operations.md) for those flows.

## Topology

The smallest cluster is three hosts. A typical small layout:

| Host | Roles |
|---|---|
| host1 | chango master + node manager |
| host2 | node manager |
| host3 | node manager |

Chango masters are multi-per-host; node managers are singleton-per-host. A master and a node manager can co-locate on the same host.

## Download the chango bundle

Chango ships as a single tarball on GitHub Releases. Download it on the host that will act as ansible controller (typically the chango master host):

```bash
curl -L -O https://github.com/cloudcheflabs/chango-pack/releases/download/chango-archive/chango-3.0.0.tar.gz
```

This is the **lean** distribution — chango binaries, admin UI, ansible scripts. Component packages (Spark, Trino, ShannonStore, Ontul, NeoRunBase, ItdaStream, kiok, Mium, …) are added by a second step:

```bash
tar -xzf chango-3.0.0.tar.gz
cd chango-3.0.0
bash build-with-comps/build-with-comps.sh
```

This produces `chango-with-comps-3.0.0.tar.gz` (≈ 4.4 GB) — the bundle ansible installs from. It contains every component package, the JDKs chango needs (Java 17 + 25), and the ansible RPMs to install ansible itself on the controller (so the install works on an air-gapped cluster).

## Prepare the inventory

Copy the example inventory and edit hosts:

```bash
cd chango-3.0.0/ansible
cp inventory.yml.example inventory.yml
```

A minimal `inventory.yml`:

```yaml
all:
  vars:
    ansible_user: rocky
    ansible_ssh_private_key_file: ~/.ssh/your-key.pem
    ansible_python_interpreter: /usr/bin/python3
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no'
  children:
    chango_masters:
      hosts:
        chango-host1:
          ansible_host: 10.0.0.11        # private IP
          chango_master_zk_id: 1
    chango_nodemanagers:
      hosts:
        chango-host1:                     # same host as the master — co-located
          ansible_host: 10.0.0.11
        chango-host2:
          ansible_host: 10.0.0.12
        chango-host3:
          ansible_host: 10.0.0.13
```

Notes:

- `ansible_host` is the **private IP** of each node. Chango uses private IPs for all internal connectivity.
- `chango_master_zk_id` is the ZooKeeper `myid` for that master's bundled ZK quorum — distinct integers per master.
- A node manager entry whose `ansible_host` matches a master entry's is the co-location case.

## Install ansible-core

The bundle ships ansible RPMs for offline install. On the controller:

```bash
mkdir -p /tmp/ansible-bundle
tar -xzf chango-3.0.0/components/ansible/ansible-core-rocky9-x86_64.tar.gz -C /tmp/ansible-bundle
cd /tmp/ansible-bundle
sudo dnf install -y --disablerepo='*' ./*.rpm
ansible --version
```

If your hosts have internet access, `sudo dnf install -y ansible-core` is equivalent.

## Generate the master key

Chango envelope-encrypts every cluster-wide secret with a master key. Generate one **before** running the playbook and pass it via environment variable:

```bash
export CHANGO_MASTER_KEY=$(openssl rand -base64 48 | head -c 48)
```

Treat this value the same way you would treat a root credential — it is the root of trust for every secret chango stores. Keep it in a real secret manager (Vault, AWS Secrets Manager, a hardware-backed password manager). You will re-supply this exact value on every chango restart from now on.

## Run the playbook

```bash
cd chango-3.0.0/ansible
ansible-playbook -i inventory.yml install.yml
```

Expected runtime: 5 – 10 minutes for a 3-host cluster (component extraction dominates).

The playbook finishes with an operator-note debug block telling you where on the master host it parked a one-time copy of the master key. **Read that note carefully** — it is the one moment ansible holds the key in a file. Move that value into your secret manager, then remove the staged file. The exact file path is in the play-recap output.

The chango master, the bundled ZooKeeper, and every node manager are now running. The admin UI is reachable on the master's admin port (default `8080`).

## Verify

```bash
# Replace <master> with the master host's reachable address
curl -s http://<master>:8080/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}'
```

A response containing `accessToken` means chango is up. The default login is `admin` / `admin`; the first login requires a password change.

Web UI: `http://<master>:8080/admin/`

Next: [Getting Started](getting-started.md) for the first component install.

## After install — what stays running, what ansible does not touch

After the playbook finishes:

- The chango master JVM is running on the master host (started by ansible exactly once).
- The bundled ZooKeeper JVM is running on the master host.
- A node manager JVM is running on every host listed in `chango_nodemanagers`.

None of these are systemd units. They are background processes started by `bin/start-master.sh`, `bin/start-zk.sh`, and `bin/start-node-manager.sh`, with their pid files under `/opt/chango/bin/`.

From this point on, any lifecycle action you need — restart, stop, add another master, add another node manager — is done by the operator manually. See [Cluster Operations](../operations/cluster-operations.md).
