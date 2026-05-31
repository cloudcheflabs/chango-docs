# Sticky Leader Election

Chango masters elect a leader via Curator's `LeaderSelector` against ZooKeeper, but the bare election would re-elect a different master on every restart — even a graceful one. That triggers a leadership toggle, double KMS / IAM init on the new leader, and an avoidable window of follower-forward HTTP traffic during routine ops (rolling restart, self-patch, kernel patch reboot).

The chango master stacks **two** sticky mechanisms on top of `LeaderSelector` so that the master that was leader yesterday is the leader again today, even after a graceful restart.

## The two mechanisms

| Mechanism | When it fires | What it does | ZK node |
|---|---|---|---|
| Cold-start deference | Whole cluster cold-starts together (every master process was down). | Each master reads `master-leader-id`; if it does **not** match its own `nodeId`, it sleeps `chango.master.leader.deference.window.ms` (default `3000`) before joining the election. The "last leader" therefore wins the election race. | `/chango/master-leader-id` (persistent — written every time leadership lands) |
| Hot-restart sticky-back | One master is being restarted while the others stay up. | The restarting leader writes `master-leader-preferred = "<nodeId>:<expiresAtEpochMs>"` to ZK during graceful stop. When another master receives `takeLeadership()` and sees a **fresh** hint pointing at a different node, it sleeps `deferenceWindowMs` and returns from `takeLeadership` — yielding the election back. The preferred node reclaims it. | `/chango/master-leader-preferred` (persistent, timestamped) |

Both are in `MasterLeaderElection`. They are **independent**: cold-start deference handles cluster bring-up; hot-restart sticky handles a single-node restart during normal operation. Together they prevent leadership flap during a rolling restart, an ansible-driven upgrade, or a chango self-patch.

## Cold-start deference

```
Cluster cold-start:
    masterA stops → masterB stops → masterC stops    (yesterday)

    masterA starts:
        reads /chango/master-leader-id  → "masterA"   ← matches self
        joins election immediately      → elected leader
        writes /chango/master-leader-id → "masterA"   (no-op)
        clears /chango/master-leader-preferred

    masterB starts:
        reads /chango/master-leader-id  → "masterA"   ← differs from self
        sleeps deferenceWindowMs        (3 s default)
        joins election as follower
```

The persistent `master-leader-id` node is updated every time leadership lands somewhere; it is therefore always pointing at the most recent leader.

If `master-leader-id` is missing (truly fresh install — first start, never has had a leader), every master joins the election immediately and the natural Curator order decides. From the next leadership change onward, the sticky-back lock-in starts.

## Hot-restart sticky-back

```
Hot restart of the current leader, masterA, while masterB stays up:

    masterA  (leader)         masterB  (follower)
    ----------------          --------------------
    stop-master.sh
        |
        |  Just before close():
        |  /chango/master-leader-preferred = "masterA:<now + 60s>"
        |  /chango/master-leader-id        = "masterA"        (already)
        |  release leadership latch
        |                                          takeLeadership():
        |                                            reads preferred → "masterA:<exp>"
        |                                            now < exp        →  yield window
        |                                            now != masterA   →  not us
        |                                            sleep deferenceWindowMs (3s)
        |                                            return (give up election turn)
        |
    start-master.sh
        |
        |  takeLeadership():
        |    reads preferred → "masterA:<exp>"
        |    now < exp        → yield window
        |    now == masterA   → it IS us, claim
        |    promote, clear preferred hint, set master-leader-id=masterA
```

`PREFERRED_HINT_TTL_MS` is hard-coded to `60_000` ms today — long enough to cover a normal stop / start cycle (~10 s), short enough that a never-returning leader does not pin leadership forever. The hint is timestamped (`"<nodeId>:<expiresAt>"`) rather than tied to an ephemeral ZK node lifetime — the old leader's session may already be gone by the time the next master tries to take leadership, so a pure-ephemeral hint would falsely look stale.

If the preferred node never comes back (host died, not "graceful stop"), the hint expires after `PREFERRED_HINT_TTL_MS` and the next election attempt sees the expired hint, clears it, and proceeds normally — leadership lands on whoever wins the bare Curator race.

## Why two mechanisms?

A single deference window cannot do both jobs:

- **Cold-start** needs to consult the **persistent** "who was the last leader" record, since every master is starting cold and there is no live leader to compare against.
- **Hot-restart** needs a **timestamped** hint that the still-alive masters can check and yield to, because the cold-start record was already pointing at the leader who is about to come back — it would not look any different from a real swap.

The cold-start hint (`master-leader-id`) is updated whenever leadership lands; the hot-restart hint (`master-leader-preferred`) is **only** written by the leader during its own graceful close. Together they make the common case ("the master that was leader yesterday is still leader today") a strict invariant during planned restarts.

## Config

| Property | Default | What it controls |
|---|---|---|
| `chango.master.leader.deference.window.ms` | `3000` | How long a non-preferred master sleeps before joining the election (cold-start) or yields after seeing a fresh hint (hot-restart). |
| `PREFERRED_HINT_TTL_MS` (compile-time constant) | `60_000` | TTL on the `master-leader-preferred` hint. |

`deferenceWindowMs` is intentionally short — long enough to let the preferred node finish its restart on a normal host, short enough that a true outage does not pin leadership for too long.

## Observability

`master.log` shows the path taken every time:

```
... Startup deference: stored leader=masterA, sleeping 3000 ms before joining election
... Preferred hint points at us (masterA) — claiming leadership
... Yielding leadership to preferred incumbent masterA (hint valid for 47213 more ms)
... Preferred-leader hint for masterA expired 12 ms ago — clearing
```

In the admin UI's **Cluster → Nodes** view, the leader's `nodeId` should remain stable across a single-master restart of the leader. If it does not — for instance, the restart took longer than `PREFERRED_HINT_TTL_MS` and the hint expired before the old leader came back — the next leader is whoever Curator picked, and the sticky-back skips one cycle.

## Interactions

- **Self-patch (v2)** depends on this. The 3-phase fan-out restarts the leader **last**; the helper script preserves `CHANGO_MASTER_KEY` and the original `-Dchango.*` system props and lets sticky-back re-elect the same node. See [Patch System](patch-system.md#chango-self-patch-v2).
- **Rolling restart** of the masters relies on cold-start deference + hot-restart sticky to keep leadership on the original host across the whole roll — restart followers first, then the leader.
- **Reset** (`/var/lib/chango/{kms,iam,metadata,zookeeper}/*` wiped) clears the persistent `master-leader-id` node along with everything else. Sticky-back resumes on the next leadership lands.
