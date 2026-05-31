# Cluster Operations

Day-2 operations for the chango cluster itself — the chango master, the bundled ZooKeeper, the node managers. After the initial ansible install, the operator drives every lifecycle action directly with the shell scripts under `/opt/chango/bin/`. Chango does not install systemd units and does not read any persistent key file at runtime.

## The two things the operator always supplies

Every chango startup needs two things, both supplied by the operator:

1. **The cluster master key**, as an environment variable on the shell that launches the JVM. Same value across all hosts and across all restarts; keep it in your secret manager.
2. **The shell script for the role you are starting**, run as the `chango` user.

Without `CHANGO_MASTER_KEY` in the environment, `bin/start-master.sh` and `bin/start-node-manager.sh` will start the JVM but the KMS init will fail and the process will exit. With the wrong key, the same failure happens but a step later — the RocksDB stores cannot be decrypted.

## Start / stop / restart — chango master + ZK

On the master host:

```bash
# As root or via a sudoers account
export CHANGO_MASTER_KEY=<from your secret store>

# Start ZooKeeper first
sudo -u chango -E /opt/chango/bin/start-zk.sh \
    -Dchango.zk.serverList=<zk-quorum>

# Then the chango master
sudo -u chango -E /opt/chango/bin/start-master.sh \
    -Dchango.zk.serverList=<zk-quorum>
```

The scripts daemonize the JVM with `nohup &` and write the pid to:

- `/opt/chango/bin/zookeeper.pid`
- `/opt/chango/bin/master.pid`

Stop is the inverse (no master key needed for stop):

```bash
sudo -u chango /opt/chango/bin/stop-master.sh
sudo -u chango /opt/chango/bin/stop-zk.sh
```

Restart is stop + start in the same shell with the master key exported.

## Start / stop — chango node manager

On every node manager host:

```bash
export CHANGO_MASTER_KEY=<from your secret store>
sudo -u chango -E /opt/chango/bin/start-node-manager.sh \
    -Dchango.zk.serverList=<zk-quorum>
```

The pid file is `/opt/chango/bin/node-manager.pid`. Stop:

```bash
sudo -u chango /opt/chango/bin/stop-node-manager.sh
```

A node manager restart costs no component downtime — managed component processes (Trino, Spark, …) keep running, and the NM re-attaches to them by reading their pid files when it starts again.

## Rolling restart

For an HA cluster (more than one master), restart followers first, then the leader.

```bash
export CHANGO_MASTER_KEY=<from your secret store>

# 1. On each follower host, in turn:
sudo -u chango /opt/chango/bin/stop-master.sh
sudo -u chango -E /opt/chango/bin/start-master.sh -Dchango.zk.serverList=<zk-quorum>
# wait until the master is back to `ready = true` in the admin UI before moving on

# 2. Finally, the leader:
sudo -u chango /opt/chango/bin/stop-master.sh
sudo -u chango -E /opt/chango/bin/start-master.sh -Dchango.zk.serverList=<zk-quorum>
```

Leadership hands off to one of the followers on stop; when the old leader comes back up the **sticky-leader** mechanism re-elects it without a leadership toggle. The leader writes a `master-leader-preferred:<expiresAt>` hint to ZK during its graceful stop; any follower that receives `takeLeadership` while the hint is fresh yields back during the `deferenceWindowMs` window so the original leader can reclaim leadership on restart. See [Sticky Leader Election](../features/sticky-leader.md) for the two mechanisms (cold-start deference + hot-restart sticky-back) and the ZK znodes.

Node managers can be restarted in any order — the order does not affect cluster availability.

## Add another node manager

The bundle ships `ansible/add-nodemanager.yml` for this. It does the same `node-prep` + Java 17/25 + chango distribution + first-boot start as the initial install, but **never stages the master key on disk** — the playbook prompts you for it interactively and passes it through to first-boot start in memory only. The new host joins the cluster and registers in ZooKeeper; the admin UI sees it within seconds.

### Recommended — `ansible add-nodemanager.yml`

1. Add the new host to your existing inventory under `chango_nodemanagers:`.

2. Run the playbook limited to the new host (from the ansible controller, with the chango tarballs staged the same way as initial install):

   ```bash
   ansible-playbook -i inventory.yml add-nodemanager.yml --limit <new-host>
   ```

3. The playbook prompts for `CHANGO MASTER KEY` — type the same value you used at first install (you should be holding it in your secret manager). The key is `private` (not echoed) and never persisted on disk on the new host.

That is it. The new NM is registered + ready when the playbook returns. Verify with the REST snippet at the bottom of this page.

### Manual fallback

If you cannot use ansible (air-gapped maintenance host with no controller, recovering one offline node, etc.):

1. **Prepare the host** per [Node Preparation](../installation/node-preparation.md).
2. **Install Java 17** (Trino's Java 25 is only required on masters that will run Trino's coordinator; NMs don't need it).
3. **Copy the chango distribution** onto the new host (the same lean tarball used at install).
4. **Create the `chango` user** and base directories:

   ```bash
   sudo groupadd -r chango || true
   sudo useradd -r -g chango -s /bin/bash -d /opt/chango -M chango || true
   sudo install -d -o chango -g chango /opt/chango /var/lib/chango /var/log/chango
   ```

5. **Extract chango** under `/opt/chango` and chown to chango.
6. **Grant passwordless sudo** for the chango user:

   ```bash
   echo 'chango ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/chango
   sudo chmod 0440 /etc/sudoers.d/chango
   ```

7. **Start the node manager** with the cluster master key in the environment:

   ```bash
   export CHANGO_MASTER_KEY=<from your secret store>
   sudo -u chango -E /opt/chango/bin/start-node-manager.sh \
       -Dchango.zk.serverList=<zk-quorum>
   ```

## Add another chango master

Multi-master mode is for control-plane HA. The bundle ships `ansible/add-master.yml` to do this end-to-end — it runs `node-prep` + Java 17/25 + chango install + first-boot start on the new host, prompts for the master key interactively (never writing it to disk on the new host), and is the recommended path. There is a manual fallback for environments where ansible is not an option.

### Recommended — `ansible add-master.yml`

**Prerequisite — extend the bundled ZooKeeper quorum first** (see "ZK quorum" below for the exact edits). The quorum must already contain the new server line before you start the new master.

1. Add the new host to your inventory under `chango_masters:` with a distinct `chango_master_zk_id`.
2. Run the playbook limited to the new host:

   ```bash
   ansible-playbook -i inventory.yml add-master.yml --limit <new-master-host>
   ```

3. Type the same `CHANGO MASTER KEY` you used at first install when prompted (or set `CHANGO_MASTER_KEY` in the controller's environment for non-interactive runs — the prompt uses that as its default).

The new master joins the live ZK quorum and shows up in the admin UI's **Cluster → Nodes** within seconds.

### Manual — a second master on a *new* host

If you cannot use ansible:

Same steps as the manual NM install above up through "Grant passwordless sudo" plus Java 25 installation, then:

```bash
export CHANGO_MASTER_KEY=<from your secret store>
export JAVA_HOME=/opt/openlogic-openjdk-17.0.7+7-linux-x64

# Start bundled ZooKeeper on the new host (extend the quorum — see "ZK quorum" below)
sudo -u chango -E /opt/chango/bin/start-zk.sh \
    -Dchango.zk.serverList=<extended-quorum>

# Start chango master
sudo -u chango -E /opt/chango/bin/start-master.sh \
    -Dchango.zk.serverList=<extended-quorum>
```

### A second master on the *same* host

Chango masters are multi-per-host. To run two on the same host, pick distinct admin / internal ports for the second one:

```bash
export CHANGO_MASTER_KEY=<from your secret store>

sudo -u chango -E /opt/chango/bin/start-master.sh \
    -Dchango.master.admin.port=8090 \
    -Dchango.master.internal.port=20000 \
    -Dchango.zk.serverList=<zk-quorum>
```

`bin/chango-common.sh` automatically suffixes the pid file with the admin port (`master-8090.pid`), so the two instances coexist without colliding on the pid.

### ZK quorum

Adding a master means extending the bundled ZooKeeper quorum (an odd-count ensemble — 1, 3, 5). This is a manual step today:

1. Edit `/opt/chango/conf/zk/zoo.cfg` on **every** existing master host to add the new server (`server.<id>=<host>:<peerPort>:<leaderPort>`).
2. Write `<id>` into `/var/lib/chango/zookeeper/myid` on the new master host.
3. Restart `chango-zk` on every master host, rolling.
4. Then start the new master.

For a single-master cluster you do not need to touch ZK quorum config — the ZK ensemble is already a one-node quorum.

## Verifying

After any start, sanity-check from the admin UI's Cluster → Nodes page (or REST):

```bash
TOK=$(curl -s http://<master>:8080/admin/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<pw>"}' | jq -r .accessToken)

curl -sH "Authorization: Bearer $TOK" http://<master>:8080/admin/api/nodes/masters
curl -sH "Authorization: Bearer $TOK" http://<master>:8080/admin/api/nodes/node-managers
```

Every entry should show `ready = true`. Exactly one master should show `isLeader = true`.

## Resetting a cluster

To wipe a chango cluster back to first-boot state (test / demo / disaster):

```bash
# On every chango host — stop everything
sudo -u chango /opt/chango/bin/stop-node-manager.sh
sudo -u chango /opt/chango/bin/stop-master.sh         # master hosts only
sudo -u chango /opt/chango/bin/stop-zk.sh             # master hosts only

# Wipe RocksDB stores and ZK data on the master hosts
sudo rm -rf /var/lib/chango/{kms,iam,metadata,zookeeper}/*

# Start fresh — first start re-creates the default admin/admin user
export CHANGO_MASTER_KEY=<from your secret store>
sudo -u chango -E /opt/chango/bin/start-zk.sh -Dchango.zk.serverList=<zk-quorum>     # master
sudo -u chango -E /opt/chango/bin/start-master.sh -Dchango.zk.serverList=<zk-quorum> # master
sudo -u chango -E /opt/chango/bin/start-node-manager.sh -Dchango.zk.serverList=<zk-quorum>  # every host
```

Component install dirs under `/opt/components/` are not removed by this — wipe them separately if you want a clean component slate too.

This is destructive; for HA, do the wipe on every master at the same time, otherwise a still-running follower will push stale state back when the wiped master rejoins.

## Cluster readiness

The admin REST API refuses non-auth routes until the cluster is "ready":

- The leader is elected, has decrypted its KMS / IAM / metadata stores, and has written `/chango/leader-ready`.
- Every non-leader master has done a mandatory pull from the leader (KMS + IAM + metadata + patch library), marked itself ready under `/chango/nodes/masters/<id>`, and `/chango/cluster-ready = true` has been written by the leader.
- ZooKeeper quorum is reachable.

Until then, requests return `503` with a JSON body identifying which precondition is unmet. The admin UI shows a "cluster starting" splash.

The readiness gate timeout is `chango.cluster.readiness.timeout.ms` (default 120 000). On master startup, the master logs `Cluster ready` once the gate opens; if it stays closed past the timeout the master exits with a non-zero status. You will see it in `/var/log/chango/master.log` and the pid file goes stale — re-run `bin/start-master.sh` after fixing the underlying issue.

See [Cluster Readiness](../features/cluster-readiness.md) for the full flow (leader / non-leader paths, every ZK znode, per-master ready flag) and [Leader Forwarding](../features/leader-forward.md) for how follower masters relay mutating admin traffic to the leader once readiness opens.

## Config endpoint requires RUNNING

`POST /admin/api/<comp>/<id>/config` (and any file-write endpoint on a component instance) **requires the instance to be RUNNING**. A request against a STOPPED instance returns `400 Bad Request` with `"instance 'X' is STOPPED — config changes require RUNNING; start the instance first."`.

This keeps "admin API state" and "on-disk state" lockstep — components whose `start-*.sh` re-derives content from chango master settings would otherwise overwrite the just-edited file. Start the instance, apply the config, restart for the change to take effect. See [Config Runtime-Only Policy](../features/config-runtime-only.md).

For values you need from the very first start (heap size, custom properties), use the install-time `properties` map + per-role JVM config — not the config endpoint.
