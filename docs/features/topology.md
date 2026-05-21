# Cluster Topology

Chango's cluster topology has two simple rules — one for masters, one for node managers — and the rest follows.

## The two rules

**Master**

- More than one master may run on the same host (admin ports must differ).
- A master may co-locate with a node manager on the same host.
- HA is achieved by running multiple masters; one is elected leader via ZooKeeper.

**Node manager**

- Exactly one node manager per host.
- A node manager may co-locate with one or more masters on the same host.

These rules are enforced at registration time — a second node manager attempting to register against the same host (with a different `nodeId`) is rejected with `IllegalStateException`.

## Why these rules

- **Master = N per host** — masters are stateless (cluster state lives in the leader's RocksDB and ZooKeeper). Running more than one on a single host gives admin-UI / API capacity headroom and a hot standby that can take over in <1 leader-election window.
- **NM = 1 per host** — the node manager is the host agent. It owns the host's `/opt/components/*` install dirs, the host's `ps` view of every managed process, and the SELinux / sudo / file-ownership surface. Two NMs on one host would fight over those.
- **Co-location is fine** — a small cluster (three hosts, one master + three NMs) is the standard layout. On large clusters you split masters off onto dedicated control hosts; on dev / lab clusters everything stacks on one host.

## Typical layouts

### Small layout (one master)

```
host1   master + NM   (chango admin, ZK, component instances)
host2            NM   (component instances)
host3            NM   (component instances)
```

This is the layout used by the standard install playbook (`inventory.yml.example`). One master is enough to run a cluster — a master restart costs ~10 s of admin-API unavailability; component processes keep running.

### Three masters + N node managers (HA)

```
host1   master + NM
host2   master + NM
host3   master + NM
host4         NM
...
hostN         NM
```

Three masters form a ZooKeeper quorum and elect a leader. Losing one master (network blip, restart) causes a sub-second leader re-election with the other two; component processes are unaffected.

### Dedicated control hosts

```
host-c1  master           (no NM, no component processes)
host-c2  master
host-c3  master
host1            NM       (every component instance)
host2            NM
...
hostN            NM
```

Used when control-plane and workload need physical isolation (compliance, blast radius).

## Node identifiers

Default identifiers are derived from the host and the role:

- Master: `master-<sanitized-hostname>-<adminPort>` — the admin port is what makes a second master on the same host distinct (currently a deploy-layer limitation — single master per host is what the bundled systemd unit supports today).
- Node manager: `nm-<sanitized-hostname>-<internalPort>` — the internal port is in the id for stable backwards compatibility with component records; since only one NM per host is allowed at runtime, the port is effectively constant.

Both are overridable via `chango.master.nodeId` / `chango.nodemanager.nodeId` in `chango.properties` for environments that need explicit naming.

## Hostname model

Chango registers each node by its OS canonical hostname. There are two cases:

| OS hostname looks like | Chango behaviour |
|---|---|
| Real FQDN (`host1.example.com`, `ip-10-0-0-11.region.compute.internal`, …) | Use it as-is. `/etc/hosts` is not modified — your DNS already resolves it. |
| Short (`host1`, `ip-10-0-0-11`, …) | Synthesize `<short>.<chango.cluster.domain>` (default `chango.private`) and keep `/etc/hosts` in sync across all hosts with a managed `# BEGIN chango … # END chango` block. |

See [Hosts Sync](hosts-sync.md) for the sync details.

## Adding / removing hosts

- **Adding** a node manager — prepare the host, add it to the inventory, re-run the install playbook with `--limit <new-host>`. The new NM registers in ZooKeeper, the leader picks it up, and component install panels in the admin UI start offering it as a target.
- **Removing** a node manager — stop `chango-nodemanager.service` on that host. Its ephemeral znode disappears; the leader removes it from the live registry. Component instances still listed against that nodeId stay in metadata; before reusing the same nodeId on a different host, delete or move those instances first.
- **Adding** a master — start a new master process with a fresh `nodeId` against the same ZooKeeper. It joins the leader election. The existing leader keeps leadership (sticky leader).
- **Removing** a master — stop `chango-master.service`. If it was the leader, the other masters elect a new leader within a second.
