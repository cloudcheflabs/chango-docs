# Automated Install (Ansible)

This page brings up a chango cluster with the ansible playbooks shipped in the bundle. Use it for any multi-host install you intend to keep running. Scaling the cluster out later (adding a master or a node manager) also uses ansible — `add-master.yml` and `add-nodemanager.yml`.

The end state is identical to the [manual install](manual.md): a chango master + bundled ZooKeeper on the master host, a node manager on every host, no systemd units, the cluster master key held only in operator-controlled secret storage.

## What ansible does — and what it does not

Chango uses ansible **only for these three actions**:

| Playbook | Purpose |
|---|---|
| `install.yml` | First-time cluster bootstrap — node prep + Java 17/25 + chango distribution + first-boot start on every host. |
| `add-master.yml` | Add a chango master to an existing cluster. |
| `add-nodemanager.yml` | Add a node manager to an existing cluster. |

Stop / restart / upgrade are **not** ansible's job. After any of the three playbooks above finishes, ansible is out of the picture and the operator runs `/opt/chango/bin/*.sh` directly on each host. See [Cluster Operations](../operations/cluster-operations.md).

The bundle deliberately ships no systemd units and no `/etc/sysconfig/chango` file. The cluster master key never lands on disk under chango's control — at first install ansible stages a one-time copy at `/opt/chango/.master-key-bootstrap` on the master host, prints its path in the play recap, and expects the operator to move that value into a secret manager and delete the file.

## Topology

The smallest cluster is three hosts:

| Host | Roles |
|---|---|
| host1 | chango master + node manager |
| host2 | node manager |
| host3 | node manager |

Chango masters are multi-per-host; node managers are singleton-per-host. A master and a node manager can co-locate on the same host. High-availability deployments run 3 masters on 3 different hosts (the bundled ZooKeeper quorum is then a 3-node ensemble).

## 1. Download the chango bundle on the controller

The ansible controller is typically the future master host. Download the lean tarball:

```bash
curl -L -O https://github.com/cloudcheflabs/chango-pack/releases/download/chango-archive/chango-3.0.0.tar.gz
tar -xzf chango-3.0.0.tar.gz
cd chango-3.0.0
```

Then build the **with-comps** bundle (component tarballs + JDKs + ansible RPMs):

```bash
bash build-with-comps/build-with-comps.sh
```

This produces `chango-with-comps-3.0.0.tar.gz` (≈ 4.4 GB). The build step downloads every component package and the two JDKs (Java 17 + Java 25) into the ansible role's `files/` directories so the playbook can ship them to every host. If your controller is air-gapped, run the same script on a connected machine and transfer the resulting bundle.

## 2. Install ansible-core on the controller

The bundle ships ansible RPMs for offline install:

```bash
mkdir -p /tmp/ansible-bundle
tar -xzf components/ansible/ansible-core-rocky9-x86_64.tar.gz -C /tmp/ansible-bundle
cd /tmp/ansible-bundle
sudo dnf install -y --disablerepo='*' ./*.rpm
ansible --version
```

If the controller has internet access, `sudo dnf install -y ansible-core` is equivalent.

## 3. Prepare the inventory

Copy the example and edit it:

```bash
cd ansible
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
          ansible_host: 10.0.0.11
          chango_master_zk_id: 1
    chango_nodemanagers:
      hosts:
        chango-host1:                     # same as the master — co-located
          ansible_host: 10.0.0.11
        chango-host2:
          ansible_host: 10.0.0.12
        chango-host3:
          ansible_host: 10.0.0.13
```

Notes:

- `ansible_host` is the **private IP** of each node. Chango uses private IPs for all internal connectivity.
- `chango_master_zk_id` is the ZooKeeper `myid` for that master's bundled ZK quorum — distinct integers per master.
- A node manager whose `ansible_host` matches a master's is the co-location case.

## 4. Generate the cluster master key

Once, on the controller:

```bash
export CHANGO_MASTER_KEY=$(openssl rand -base64 48 | head -c 48)
```

Treat this value as a root credential — it is the root of trust for every secret chango stores. Move it into a real secret manager (Vault, AWS Secrets Manager, a hardware-backed password manager) immediately after first install. You must re-supply this **exact** value on every master / NM restart and at every later scale-out.

## 5. Run the install playbook

```bash
ansible-playbook -i inventory.yml install.yml
```

The playbook runs five plays in order:

1. **`node-prep`** — SELinux disabled + ulimit + sysctl on every host.
2. **`java17`** — extracts Java 17 under `/opt` on every host.
3. **`java25`** — extracts Java 25 under `/opt` on every host (Trino's runtime).
4. **`chango-master`** — installs chango on the master hosts, stages the master key bootstrap file (master only, 0600 root), starts ZK + master once with `CHANGO_MASTER_KEY` from the controller's environment.
5. **`chango-nodemanager`** — installs chango on the NM hosts, starts the NM once. NM hosts **never** get the bootstrap file.

Expected runtime: 5 – 10 minutes for a 3-host cluster (component extraction dominates).

The last task of the master play is an operator-note debug block printing the bootstrap file path on the master host. Read it carefully — that is the one moment a chango-controlled file holds the master key. Move the value into your secret manager, then:

```bash
sudo shred -u /opt/chango/.master-key-bootstrap
```

After that, the chango runtime never reads any persistent key file again. Every later start requires the operator to supply `CHANGO_MASTER_KEY` from their secret manager.

## 6. Verify

```bash
curl -s http://<master>:8080/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}'
```

A response containing `accessToken` means chango is up. Default login is `admin` / `admin`; the first login forces a password change.

Web UI: `http://<master>:8080/admin/`

## Adding a master later — `add-master.yml`

Use this when you grow a single-master cluster into multi-master HA, or add a master in a new failure domain.

**Prerequisite — extend the bundled ZooKeeper quorum first** (a manual step today; ansible does not drive lifecycle anymore):

1. Edit `/opt/chango/conf/zk/zoo.cfg` on **every** existing master host to add the new server line (`server.<id>=<host>:2888:3888`).
2. Write `<id>` into `/var/lib/chango/zookeeper/myid` on the new master host (you will set this up below as part of the install).
3. Roll-restart `chango-zk` on each existing master one by one — see [Cluster Operations](../operations/cluster-operations.md).

Only then run the playbook:

```bash
# 1. Append the new master to inventory.yml under chango_masters: with a distinct
#    chango_master_zk_id (e.g. 2 if you already had 1).
# 2. Run, limited to the new host:
ansible-playbook -i inventory.yml add-master.yml --limit <new-master-host>
```

The playbook prompts for `CHANGO MASTER KEY` — type the same value you used at first install. The key is `private` (not echoed) and is passed through to first-boot start **in memory only**; the bootstrap file is not created on the new host.

CI / non-interactive use: set `CHANGO_MASTER_KEY` in the controller's environment; the prompt uses that as its default and the playbook runs without an interactive shell.

## Adding a node manager later — `add-nodemanager.yml`

Use this for any horizontal scale-out — more capacity for component instances, a new failure domain, a replacement after a hardware loss.

```bash
# 1. Append the new node to inventory.yml under chango_nodemanagers:.
# 2. Run, limited to the new host:
ansible-playbook -i inventory.yml add-nodemanager.yml --limit <new-nm-host>
```

Same prompt behavior as `add-master.yml`. The playbook installs `node-prep` + Java 17/25 + chango on the new host and runs first-boot start with the master key in env only. The NM registers itself in ZooKeeper and shows up in the admin UI within seconds.

## Next

- [Getting Started](getting-started.md) — first login + first managed component.
- [Cluster Operations](../operations/cluster-operations.md) — day-2 lifecycle (stop / restart / verifying).
