# Cluster Readiness

When a chango master starts (cold, restart, or after a self-patch), it does not serve admin REST traffic until it has proven that it holds a fresh, leader-validated copy of the cluster state. Until then every request to `/admin/api/<anything except auth/*>` returns `503 Service Unavailable`. This is the readiness gate.

The gate exists for one reason: **a follower master that has not yet synced from the leader could serve stale (or, on a freshly-wiped node, empty) IAM and silently accept the wrong credentials**. The same applies to KMS keys (envelope-wrapped DEKs would fail to decrypt) and to component metadata (the inventory page would show an empty list).

## The full flow

```
            ┌──────── leader path ────────┐    ┌──────── non-leader path ─────────┐
            │                             │    │                                  │
  start  ─→ │ election: takeLeadership    │    │ election: takeLeadership          │
            │ KMS / IAM / metadata init   │    │   (returns immediately as follower)│
            │ registry.setLeaderReady(true)│    │ wait for /chango/leader-ready    │
            │ writes /chango/leader-ready │    │ mandatory pull-from-leader        │
            │                             │    │   (KMS + IAM + metadata + patches)│
            │ registry.setMasterReady(self,true)│ enableWireEncryptionIfNeeded() │
            │ waitForPeersReady()         │    │ registry.setMasterReady(self,true)│
            │ registry.setClusterReady(true)│  │                                  │
            │ writes /chango/cluster-ready│    │                                  │
            └──────────────┬──────────────┘    └────────────────┬─────────────────┘
                           │                                    │
                           └─────────────  both paths  ─────────┘
                                          │
                                  wait for /chango/cluster-ready
                                          │
                                readinessGate.markReady()
                                          │
                                admin HTTP starts serving 2xx
```

The ZK znodes that gate everything:

| ZK path | Written by | Meaning |
|---|---|---|
| `/chango/leader-ready` | The current leader, after KMS / IAM / metadata init. | "There is a leader; it has decrypted its stores and is willing to accept pull requests from followers." |
| `/chango/cluster-ready` | The current leader, after `waitForPeersReady()`. | "All masters and at least the minimum required NMs report `ready = true`." |
| `/chango/nodes/masters/<nodeId>` | Each master writes its own `ready = true` after the pull (non-leader) or after `setLeaderReady` (leader). | Per-master ready flag used by the leader's `waitForPeersReady()`. |

`readinessGate.markReady()` is a process-local flag — once flipped, the admin HTTP server (`AdminHttpServer`) starts responding with real status codes; before it is flipped, every request to a non-auth path is shortcircuited to `503`.

## Step-by-step

1. **Master bootstrap**. `MasterBootstrap.start()` opens RocksDB stores, starts ZooKeeper client, starts internal-protocol NIO server, starts election.
2. **Election**. `MasterLeaderElection` may sleep up to `deferenceWindowMs` (see [Sticky Leader Election](sticky-leader.md)) before calling `takeLeadership`. Whichever master wins runs `onLeadershipChange(true)` and writes `/chango/leader-ready = true`.
3. **Admin HTTP starts, but gated**. The admin HTTP server is up; the `ClusterReadinessGate` is held `false`, so every non-auth request returns `503` with a body identifying which precondition is unmet ("waiting for /chango/leader-ready", "waiting for mandatory pull", "waiting for /chango/cluster-ready").
4. **Wait for `/chango/leader-ready`**. Both paths block until this znode exists. Cap at `chango.cluster.readiness.timeout.ms` (default `120_000`); on timeout the master logs the failure and exits.
5. **Non-leader: mandatory pull**. The follower runs `PeriodicLeaderPull.pullOnce()` against the leader's NIO endpoint, fetching KMS state + IAM state + metadata state + the patch library (PR 5). It retries up to 60×1s. If the pull never succeeds, the master throws `IllegalStateException("Mandatory startup pull failed; aborting")`.
6. **Wire encryption**. After a successful pull, the follower flips its internal-NIO encryption flag on the same cluster-wide setting the leader uses — without this, the next message it sends would be plain-text against a leader expecting AES-GCM.
7. **Mark self ready**. `registry.setMasterReady(nodeId, true)` writes the per-master flag. The periodic pull loop also starts here so the follower keeps syncing changes after readiness flips.
8. **Leader: wait for peers**. The leader runs `waitForPeersReady()` — every master in `/chango/nodes/masters/*` must report `ready = true`, and at least the minimum NMs must be registered. There is a configurable timeout; on timeout the leader logs `"Timed out waiting for peers; writing cluster-ready anyway"` and proceeds (a fresh cluster with no NMs is still useful to serve admin UI for installing the first NM).
9. **Leader writes `/chango/cluster-ready`**. Persistent znode `= "true"`. This is the cluster-wide all-ready signal.
10. **All masters wait for `/chango/cluster-ready`, then flip readiness gate**. `readinessGate.markReady()` unblocks the admin HTTP path; admin UI splash flips from "cluster starting" to the normal layout.

## What clients see before readiness

`/admin/api/auth/*` is open at the HTTP layer the moment Netty is up — so the admin UI can attempt `login` and surface the readiness-pending state from the JSON error body rather than from a generic connection refused. Every other path returns:

```http
HTTP/1.1 503 Service Unavailable
Content-Type: application/json

{"error":"cluster starting: waiting for /chango/leader-ready"}
```

The admin UI shows a centred "Cluster starting" splash with the current precondition. It polls a lightweight readiness endpoint (which returns the same JSON when not yet ready) until it gets a 2xx, then loads the normal UI.

## Patch-system implication

`PeriodicLeaderPull` is also where the patch library catches up — every periodic pull fetches the patch index from the leader and downloads any patches the follower does not have. This means a brand-new follower that just finished the readiness flow already has every patch the leader has. See [Patch System](patch-system.md#non-leader-catch-up-pr-5).

## Config

| Property | Default | What it controls |
|---|---|---|
| `chango.cluster.readiness.timeout.ms` | `120_000` | Overall cap on the readiness flow. On timeout the master exits non-zero. |
| `chango.cluster.readiness.poll.interval.ms` | `1_000` | How often the leader-ready wait polls ZooKeeper. |
| `chango.master.leader.deference.window.ms` | `3_000` | Sticky-leader sleep before joining the election (also used by the hot-restart yield). |

If the master exits with a readiness-timeout failure, `/var/log/chango/master.log` will end with the unmet precondition. The pid file goes stale; re-run `bin/start-master.sh` once the upstream problem is fixed (most commonly: ZK quorum down, or the leader's host unreachable from the follower).

## Why "503 on follower" before any forward?

The follower's own readiness gate runs **before** the leader-forward path. A follower that has not pulled yet would forward a request to a leader the operator may also be trying to start — replaying client traffic in that situation makes the admin UI confusing (the operator sees a partial success against a half-started cluster). Holding the gate until `/chango/cluster-ready` arrives keeps the cluster's "ready" semantics binary.
