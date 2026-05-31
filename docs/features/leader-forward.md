# Leader Forwarding

The chango admin REST API is served from every master process, but only the **leader** writes to the cluster's RocksDB stores and only the leader drives component install / start / stop. A request that lands on a follower needs to reach the leader. Chango does that **transparently** — the follower forwards the request, waits for the leader's response, and relays it back to the original client. The client never sees the follower / leader distinction.

This is the same pattern Ontul uses. It replaces the older "follower returns HTTP `421 Misdirected Request` + leader address; client retries" flow that earlier chango versions used.

## How it works

Every authenticated request to `/admin/api/<anything other than auth/*>` on a follower master is captured at the top of `AdminApiHandler.handle()`:

```java
// non-auth route on a follower → forward to leader verbatim
if (!rest.startsWith("auth/") && !isLeader.getAsBoolean()) {
    leaderForwardPool.execute(() -> forwardToLeader(ctx, req));
    return;
}
```

`forwardToLeader` runs off the Netty event loop on a dedicated worker pool (thread name `chango-admin-leader-forward`) so a slow leader response never blocks other admin traffic on the same follower. It opens a plain `HttpURLConnection` to the leader's admin port, mirrors method + headers + body verbatim, and writes the leader's status / content-type / body straight back to the original client.

| Step | Detail |
|---|---|
| Resolve leader | `leaderAdminAddress()` looks up the current leader's `nodeId` in ZK and finds its admin host:port in the live `NodeRegistry`. |
| Connect timeout | `10 s` |
| Read timeout | `600 s` — backup / restore and patch apply can take minutes on a busy cluster |
| Headers | All headers except `Host` and `Content-Length` are passed through verbatim (so the `Authorization` bearer reaches the leader unchanged). |
| Body | POST / PUT / PATCH / DELETE bodies are streamed through. |
| No leader | `503 Service Unavailable` with `{"error":"no leader available for forwarding"}`. |
| Connect / read failure | `502 Bad Gateway` with the underlying message. |
| Anything else | Leader's status + body relayed verbatim. |

The client always gets the leader's response. There is no `421` redirect, no retry loop, no leader address leakage.

## What is local vs forwarded

| Path prefix | Behaviour on a follower |
|---|---|
| `/admin/api/auth/*` (`login`, `refresh`, `session`, `logout`, `change-password`) | **Local.** Token verification works on every master (KMS keys are cluster-wide synced), and `change-password` itself runs `requireLeader()` to forward when needed. |
| `/admin/api/kms/*` | Forwarded |
| `/admin/api/iam/*` | Forwarded |
| `/admin/api/sts/*` | Forwarded |
| `/admin/api/clusters/*` | Forwarded |
| `/admin/api/<component>/*` (postgres, ontul, kiok, mium, neorunbase, kafka, schema-registry, itdastream, polaris, trino, trino-gateway, ui-proxy, spark, flink, shannonstore) | Forwarded |
| `/admin/api/backup/*` | Forwarded |
| `/admin/api/patch/*` | Forwarded |
| `/admin/api/nodes/*`, `/admin/api/monitoring/*` | Forwarded (so the read path always reflects the leader's authoritative cluster view rather than a follower's lagged cache) |

Auth stays local because the follower must be able to verify a token and emit a fresh password-change response on its own — the operator might be hitting a follower during a leader outage just to rotate their own password and try again.

## Why not the old `421` pattern?

Earlier versions had each mutating route on a follower return `421 Misdirected Request` with the leader's address in the body. The admin UI followed the redirect, but every other client (curl scripts, kiok DAGs that call back into chango, ansible playbooks) had to know to look at the body and retry — they did not. The Ontul-style verbatim forward is opaque to the client and idiomatic with how every other cloudcheflabs component handles the same situation, so we converged on it across the platform.

`requireLeader()` is still called per-endpoint as a safety net inside the handler, but it never fires on a follower in practice — the top-of-handler forward catches everything first.

## Operational implications

- A follower's admin HTTP latency for mutations is **leader-RTT + leader-processing-time**, not zero. On the same host the extra cost is sub-millisecond; cross-host it is whatever the inter-host RTT is.
- A follower under heavy admin load forwards every request through the same `chango-admin-leader-forward` pool. The pool is generous (24-thread fixed pool); a single noisy admin client cannot starve other follower traffic, but a saturated leader is shared across all followers — the bottleneck is the leader, not the forward.
- The `Authorization: Bearer …` header is forwarded as-is. The leader re-validates it. No token re-signing, no admin token replay surface.
- Forwarding does not change [Cluster Readiness](cluster-readiness.md) semantics. Until the follower's own readiness gate opens, it returns `503` directly — it does not try to forward a request from a not-yet-ready process.

## When forwarding fails

- Leader address resolves but the leader is down → `502 Bad Gateway`. The admin UI surfaces the gateway error and re-tries on the next user action. ZooKeeper will be re-electing a leader within `deferenceWindowMs` + Curator's own election time; once the new leader writes `/chango/leader-ready`, follower-forward starts succeeding again.
- No leader at all (election in progress) → `503` with `{"error":"no leader available for forwarding"}`. Same UI behaviour.
- Forward times out at the 600 s read timeout → `502`. This is rare and indicates the leader is wedged on a long-running operation; check the leader's `master.log` directly.
