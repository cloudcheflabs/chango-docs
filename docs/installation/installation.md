# Download & Install

This page walks through bringing a Chango cluster up from scratch on prepared Rocky 9 hosts.

Before you start: every host must have been prepared per [Node Preparation](node-preparation.md) — SELinux disabled, ulimit and sysctl raised, `/opt` mounted, passwordless SSH from the master host.

## Topology

A typical small layout:

| Host | Roles |
|---|---|
| host1 | chango master + node manager |
| host2 | node manager |
| host3 | node manager |

Chango masters are multi-per-host; node managers are singleton-per-host. A master and a node manager can co-locate on the same host.

## Download the chango bundle

Chango ships as a single tarball on GitHub Releases. Download the lean tarball on the host that will act as ansible controller (typically the chango master host):

```bash
curl -L -O https://github.com/cloudcheflabs/chango-pack/releases/download/chango-archive/chango-3.0.0.tar.gz
```

This is the **lean** distribution — chango binaries, admin UI, ansible scripts. The component packages (Spark, Trino, ShannonStore, Ontul, NeoRunBase, ItdaStream, kiok, Mium, …) are downloaded by a second step that you run on the extracted tarball:

```bash
tar -xzf chango-3.0.0.tar.gz
cd chango-3.0.0
bash build-with-comps/build-with-comps.sh
```

This produces `chango-with-comps-3.0.0.tar.gz` (≈ 4.4 GB) — the bundle ansible installs from. It contains every component package, the JDKs chango needs (Java 17 + 25), and the ansible RPMs to install ansible itself on the master host (so the install works on an air-gapped cluster).

## Prepare ansible inventory

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
- `chango_master_zk_id` is the ZooKeeper `myid` for that master's bundled ZK quorum. Each chango master gets a distinct integer (1, 2, 3, …).
- A node manager entry whose `ansible_host` is the same as a master entry's is the co-location case — chango installs both roles on that host.

## Install ansible-core

The bundle ships ansible RPMs for offline install. On the ansible controller (your master host):

```bash
# already extracted: chango-3.0.0/components/ansible/ansible-core-rocky9-x86_64.tar.gz
mkdir -p /tmp/ansible-bundle
tar -xzf /path/to/chango-3.0.0/components/ansible/ansible-core-rocky9-x86_64.tar.gz -C /tmp/ansible-bundle
cd /tmp/ansible-bundle
sudo dnf install -y --disablerepo='*' ./*.rpm
ansible --version
```

If your hosts have internet access, `sudo dnf install -y ansible-core` is equivalent.

## Run the playbook

The playbook installs JDK 17 + 25, the chango master, and a chango node manager on each host listed in the inventory.

```bash
cd chango-3.0.0/ansible
ansible-playbook -i inventory.yml install.yml
```

Expected runtime: 5 – 10 minutes for a 3-host cluster (component extraction dominates).

## Verify

After the playbook finishes, the chango cluster is reachable on the master's admin port (default `8080`).

```bash
# Replace <master> with the master host's reachable address
curl -s http://<master>:8080/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}'
```

A response containing `accessToken` means chango is up. The default login is `admin` / `admin`; the first login requires a password change.

Web UI: `http://<master>:8080/admin/`

Next: [Getting Started](getting-started.md).

## Adding a host later

To add a new node manager host to an existing cluster, prepare the host per [Node Preparation](node-preparation.md), add it to the `chango_nodemanagers` group in `inventory.yml`, and re-run the playbook:

```bash
ansible-playbook -i inventory.yml install.yml --limit chango-host4
```

The new node manager registers itself in ZooKeeper, the leader picks it up automatically, and you can target component instances at it from the admin UI.
