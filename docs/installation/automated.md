# Automated Install (Ansible)

This page brings up a chango cluster with the ansible playbooks shipped in the bundle. Use it for any multi-host install you intend to keep running. Scaling the cluster out later (adding a master or a node manager) also uses ansible — `add-master.yml` and `add-nodemanager.yml`.

The end state is identical to the [manual install](manual.md): masters running on the chosen master hosts, a bundled ZooKeeper quorum on the chosen ZK hosts (master and ZK groups may overlap but no longer have to), a node manager on every host that runs component workloads, no systemd units, the cluster master key held only in operator-controlled secret storage.

## What ansible does — and what it does not

Chango uses ansible **only for these three actions**:

| Playbook | Purpose |
|---|---|
| `install.yml` | First-time cluster bootstrap — node prep + Java 17/25 + chango distribution + first-boot start on every host. |
| `add-master.yml` | Add a chango master to an existing cluster. |
| `add-nodemanager.yml` | Add a node manager to an existing cluster. |

Stop / restart / upgrade are **not** ansible's job. After any of the three playbooks above finishes, ansible is out of the picture and the operator runs `/opt/chango/bin/*.sh` directly on each host. See [Cluster Operations](../operations/cluster-operations.md).

The bundle deliberately ships no systemd units and no `/etc/sysconfig/chango` file. The cluster master key never lands on disk under chango's control — at first install ansible stages a one-time copy at `/opt/chango/.master-key-bootstrap` on the master host, prints its path in the play recap, and expects the operator to move that value into a secret manager and delete the file.

## Topology (default — 2 masters + 3 ZK + 3 NMs)

The 3.0.0 default install layout is HA-from-day-one: **2 chango masters + 3-node ZooKeeper quorum + 3 node managers** on three hosts. Master and ZK groups are independent — master count is decoupled from ZK count so the quorum sizing is not driven by HA-master sizing.

| Host | chango_masters | chango_zookeepers | chango_nodemanagers |
|---|---|---|---|
| host1 | ✓ (zk_id=1) | ✓ (zk_id=1) | ✓ |
| host2 | ✓ (zk_id=2) | ✓ (zk_id=2) | ✓ |
| host3 | — | ✓ (zk_id=3) | ✓ |

Why this default:
- **2 masters** — leader-election + failover (a single-master cluster has no HA). One leader, one warm follower.
- **3 ZK nodes** — a write-quorum of 2 (majority of 3), so any single host loss keeps the cluster operational. A 2-node ZK quorum needs both nodes alive and is worse than a single node for availability.
- **3 NMs** — every host that should run component workloads (Trino workers, Ontul masters/workers, Shannon data nodes, etc.). NM is singleton-per-host.

Hosts can also be added later via `add-master.yml` / `add-nodemanager.yml` (see the bottom of this page). The chango-zookeeper role does not have a dedicated `add-` playbook — see the *Adding a ZK node later* section.

Each host's `chango_master_zk_id` and `chango_zk_id` is a distinct positive integer. When a host is in both groups (host1, host2 in the table above) the two ids may be the same value (the master role's id only matters to chango's own master election; the ZK id is the actual ZooKeeper quorum `myid`). Keep them aligned for sanity — it makes the inventory easier to read.

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

The shipped `inventory.yml.example` is already the 2-master + 3-ZK + 3-NM default. Edit `ansible_host` per host and you have a production inventory:

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
        chango-host2:
          ansible_host: 10.0.0.12
          chango_master_zk_id: 2
    chango_zookeepers:
      hosts:
        chango-host1:
          ansible_host: 10.0.0.11
          chango_zk_id: 1
        chango-host2:
          ansible_host: 10.0.0.12
          chango_zk_id: 2
        chango-host3:
          ansible_host: 10.0.0.13
          chango_zk_id: 3
    chango_nodemanagers:
      hosts:
        chango-host1:
          ansible_host: 10.0.0.11
        chango-host2:
          ansible_host: 10.0.0.12
        chango-host3:
          ansible_host: 10.0.0.13
```

Notes:

- `ansible_host` is the **private IP** of each node. Chango uses private IPs for all internal connectivity.
- `chango_master_zk_id` distinguishes masters in chango's own leader-election bookkeeping; `chango_zk_id` is the ZooKeeper quorum `myid`. Both are distinct positive integers within their respective groups. When a host appears in both groups (host1 / host2 above), aligning the two ids makes the inventory easier to read but is not required.
- `chango_zookeepers` is the group that drives `zoo.cfg` membership. Adding or removing a host from the ZK quorum is a property of *this group*, not the masters group.
- A host that appears in `chango_zookeepers` but not in `chango_masters` (host3 above) runs ZK + NM only — chango master is not started there. Useful when you want a 3-node ZK quorum without paying for a third master.

### Single-host (eval / dev)

If you really want a single-box install (eval, lab, vagrant), drop both masters / zk count to 1 — put the same host into all three groups. `inventory-vagrant.yml` is shipped pre-wired for that.

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

The playbook runs six plays in order:

1. **`node-prep`** — SELinux disabled + ulimit + sysctl on every host (masters + ZK + NMs).
2. **`java17`** — extracts Java 17 under `/opt` on every host.
3. **`java25`** — extracts Java 25 under `/opt` on every host (Trino's runtime).
4. **`chango-nodemanager`** — installs chango on the NM hosts, starts the NM once. NM hosts **never** get the master key bootstrap file. Distribution is extracted here, so later plays (`chango-zookeeper`, `chango-master`) only add their role-specific files on top.
5. **`chango-zookeeper`** — renders `zoo.cfg` from the `chango_zookeepers` group + writes `myid` + first-boot starts ZK on each ZK host. Has to run after NM (which extracts the distribution) and before master (which connects to ZK on startup).
6. **`chango-master`** — installs chango on the master hosts (idempotent over the NM extraction), stages the master key bootstrap file (master only, 0600 root), starts master once with `CHANGO_MASTER_KEY` from the controller's environment. The master immediately connects to the ZK quorum that play 5 brought up.

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

Use this when you grow the cluster beyond the 2-master default — e.g. a third master in a new failure domain — or to replace a master after a hardware loss.

If you do **not** also want to add a ZK node, the existing 3-node ZK quorum stays as-is; the new master just connects to that quorum. The `add-master.yml` playbook only touches the new master host's chango distribution + first-boot start.

```bash
# 1. Append the new master to inventory.yml under chango_masters: with a distinct
#    chango_master_zk_id (e.g. 3 if you already had 1 and 2).
# 2. Run, limited to the new host:
ansible-playbook -i inventory.yml add-master.yml --limit <new-master-host>
```

The playbook prompts for `CHANGO MASTER KEY` — type the same value you used at first install. The key is `private` (not echoed) and is passed through to first-boot start **in memory only**; the bootstrap file is not created on the new host.

CI / non-interactive use: set `CHANGO_MASTER_KEY` in the controller's environment; the prompt uses that as its default and the playbook runs without an interactive shell.

## Adding a ZK node later

There is no `add-zookeeper.yml` playbook today — ZK quorum changes are inherently a careful, manual roll. Default 3-node quorum handles a single host loss, so most operators never need to grow it. When you do (e.g. a 5-node quorum for a second AZ failure domain):

1. Append the new host to `inventory.yml` under `chango_zookeepers:` with a distinct `chango_zk_id`.
2. On **every existing ZK host**, append the new `server.<id>=<host>:2888:3888` line to `/opt/chango/conf/zk/zoo.cfg` (the playbook will render the same file on the new host).
3. Write `<id>` into `/var/lib/chango/zookeeper/myid` on the new host (an empty install does this automatically — but if you are re-introducing a known id, set it first).
4. Roll-restart `start-zk.sh` / `stop-zk.sh` on each existing ZK host one by one, waiting for the quorum to re-form before moving on. See [Cluster Operations](../operations/cluster-operations.md).
5. Run the install playbook scoped to the new host so its chango distribution, `zoo.cfg`, and `myid` land properly:
   ```bash
   ansible-playbook -i inventory.yml install.yml --limit <new-zk-host> --tags chango-zookeeper
   ```
   (The `chango-zookeeper` role only renders config + starts ZK; safe to re-run on existing hosts as well.)

Shrinking a quorum (3 → 1) is allowed only when you have isolated downtime — chango treats it like any other roll. Never go from 3 → 2; majority is now both nodes and you have worse availability than 1.

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
