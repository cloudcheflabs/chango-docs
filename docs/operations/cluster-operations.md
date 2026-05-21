# Cluster Operations

Day-2 operations for the chango cluster itself — masters, node managers, the bundled ZooKeeper. Component-level operations are on the next page.

## Service control

Three systemd units per chango host:

| Unit | Host | Purpose |
|---|---|---|
| `chango-zk.service` | master hosts | Bundled ZooKeeper |
| `chango-master.service` | master hosts | Chango master JVM |
| `chango-nodemanager.service` | every host | Chango node manager JVM |

```bash
# Status
systemctl is-active chango-master
systemctl is-active chango-nodemanager
journalctl -xeu chango-master --no-pager | tail -200

# Lifecycle
sudo systemctl restart chango-master
sudo systemctl restart chango-nodemanager
```

The bundled `chango-zk` should normally not be touched by hand; restarting `chango-master` keeps ZK running, and ZK only needs a manual restart if the quorum changes.

## Rolling restart

A rolling restart of the chango cluster is safe — managed component processes (Trino, Spark, …) keep running across a node manager restart because the NM tracks them by pid and re-attaches.

For an HA cluster (multiple masters):

```bash
# 1. Restart followers, one at a time
for h in chango-m2 chango-m3; do
  ssh $h sudo systemctl restart chango-master
  sleep 10
done

# 2. Restart the leader last — leadership hands off to a follower on shutdown
ssh chango-m1 sudo systemctl restart chango-master
```

For node managers:

```bash
for h in chango-n1 chango-n2 chango-n3 ...; do
  ssh $h sudo systemctl restart chango-nodemanager
  sleep 5
done
```

A NM restart costs no component downtime — the leader's metrics charts show a sub-10s blip while the NM reattaches.

## Leader status

The current leader and full master list:

```bash
curl -sH "Authorization: Bearer $TOK" $BASE/admin/api/nodes/masters | jq .
```

Look for `isLeader: true`. The leader's `nodeId` is also written to the persistent znode `/chango/master-leader-id` — useful for shell debugging:

```bash
# On a master host
docker exec chango-m1 \
  /opt/chango/zookeeper/bin/zkCli.sh -server localhost:2181 \
  get /chango/master-leader-id
```

## Sticky leader

If you restart only the leader, the moment it comes back up it will (within a configurable deference window) try to reclaim leadership. This is intentional — leader changes invalidate the leader-only RocksDB write path and force every NM's cached state to re-pull. Sticky leader avoids the churn during a routine restart.

The deference window is `chango.master.leader.deference.window.ms` (default 3000). If you want to *forcibly* hand leadership off (e.g., to drain a master before scheduled maintenance), restart it twice in quick succession — the second restart starts after the deference window has expired on the new leader.

## Adding a master

For HA, run more than one master:

1. Prep the new host per [Node Preparation](../installation/node-preparation.md).
2. Append it to the `chango_masters` group in `inventory.yml` with a unique `chango_master_zk_id`.
3. Re-run the ansible playbook with `--limit <new-host>`.

The new master joins the existing ZooKeeper quorum, becomes a follower, and starts serving read-only admin-API routes.

## Removing a master

Stop the master process and remove it from the ZK quorum. ZK quorum reconfiguration is manual today — edit `conf/zk/zoo.cfg` on every remaining master, restart `chango-zk.service` on each (rolling).

## Adding / removing a node manager

NMs are stateless from chango's point of view (the master holds the inventory) — adding or removing one is mechanical.

- **Add** — prepare the host, add to `chango_nodemanagers`, re-run the playbook with `--limit <new-host>`. The new NM registers in ZK; the admin UI starts offering it as an install target.
- **Remove** — stop `chango-nodemanager.service`. Its ephemeral znode disappears. Component instances still listed against that nodeId become "unreachable" — move them to a different NM first (delete + reinstall on a new NM) before reusing the same nodeId.

## Resetting a cluster

If you need to wipe a chango cluster back to first-boot state (test environments, demo resets):

```bash
# On every chango host
sudo systemctl stop chango-master chango-zk chango-nodemanager
sudo rm -rf /var/lib/chango/{kms,iam,metadata,zookeeper}/*
sudo systemctl start chango-zk chango-master chango-nodemanager
```

The first start re-creates the default `admin/admin` user. Component install dirs under `/opt/components/` are not removed by this — wipe them separately if you want a clean component slate too.

This is destructive; for HA, do it on every master at once or you'll lose KMS/IAM data to a follower that still has stale state.

## Cluster readiness

The admin REST API refuses non-auth routes until the cluster is "ready":

- The leader is elected, or this master has pulled a fresh KMS + IAM + metadata snapshot from the leader.
- ZooKeeper quorum is reachable.

Until then, requests return `503` with a JSON body identifying which precondition is unmet. The admin UI shows a "cluster starting" splash.

The readiness gate timeout is `chango.cluster.readiness.timeout.ms` (default 120 000). On master startup, the master logs `Cluster ready` once the gate opens; if it stays closed past the timeout the master exits with a non-zero status and systemd restarts it.
