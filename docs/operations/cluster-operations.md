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

Leadership hands off to one of the followers on stop; when the old leader comes back up it joins as a follower, and the sticky-leader window may then re-elect it.

Node managers can be restarted in any order — the order does not affect cluster availability.

## Add another node manager

To add a node manager to an existing cluster:

1. **Prepare the host** per [Node Preparation](../installation/node-preparation.md) — SELinux, ulimit, `/opt` mount.
2. **Copy the chango distribution** onto the new host (the same lean tarball you used for the initial install, or rsync `/opt/chango` from an existing host).
3. **Create the `chango` user** and base directories:

   ```bash
   sudo groupadd -r chango || true
   sudo useradd -r -g chango -s /bin/bash -d /opt/chango -M chango || true
   sudo install -d -o chango -g chango /opt/chango /var/lib/chango /var/log/chango
   ```

4. **Extract chango** under `/opt/chango` and chown to chango.
5. **Grant passwordless sudo** for the chango user (component install, hosts sync):

   ```bash
   echo 'chango ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/chango
   sudo chmod 0440 /etc/sudoers.d/chango
   ```

6. **Start the node manager**:

   ```bash
   export CHANGO_MASTER_KEY=<from your secret store>
   sudo -u chango -E /opt/chango/bin/start-node-manager.sh \
       -Dchango.zk.serverList=<zk-quorum>
   ```

The new NM registers itself in ZooKeeper. The leader picks it up automatically; the admin UI shows it as a target for new component instances within seconds.

## Add another chango master

Multi-master mode is for control-plane HA. Two ways to add a master:

### A second master on a *new* host

Same steps as adding a node manager up through "Grant passwordless sudo", then:

```bash
export CHANGO_MASTER_KEY=<from your secret store>

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

- The leader is elected, or this master has pulled a fresh KMS + IAM + metadata snapshot from the leader.
- ZooKeeper quorum is reachable.

Until then, requests return `503` with a JSON body identifying which precondition is unmet. The admin UI shows a "cluster starting" splash.

The readiness gate timeout is `chango.cluster.readiness.timeout.ms` (default 120 000). On master startup, the master logs `Cluster ready` once the gate opens; if it stays closed past the timeout the master exits with a non-zero status. You will see it in `/var/log/chango/master.log` and the pid file goes stale — re-run `bin/start-master.sh` after fixing the underlying issue.
