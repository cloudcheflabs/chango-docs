# Nginx Reverse Proxy

Several components ship a per-cluster nginx reverse proxy as an opt-in feature. Chango installs nginx on the chosen host, renders a config that fronts the cluster's API endpoints, and reconciles the upstreams as instances are added or removed.

This page is the operations side — what to click, what to expect. For the why-not-Spark / why-not-Trino question, see [UI Proxy](../features/ui-proxy.md).

## Which components support it

| Component | What the nginx fronts |
|---|---|
| ShannonStore | S3 API + admin UI + metrics under one listen port (multi-location) |
| Polaris | Iceberg REST catalog HTTP API |
| Ontul | Admin / REST (HTTP/1.1) and Arrow Flight SQL (HTTP/2 gRPC) — two listen ports |
| NeoRunBase | Coordinator admin REST (HTTP/1.1) and PostgreSQL wire (TCP stream) — two listen ports |
| Mium | Master admin UI |
| Kiok | Master web UI |
| Kafka | Schema Registry HTTP |
| Schema Registry | HTTP |
| ItdaStream | Broker admin / metrics |
| Trino Gateway | HTTP (the gateway is itself a load balancer in front of Trino) |
| UI Proxy | (auth-gated upstreams — see [UI Proxy](../features/ui-proxy.md)) |

Spark, Trino, and Flink are deliberately omitted — their web UIs are exposed through the UI Proxy, not a plain nginx, so they get Ontul-based authentication.

## What the operator does

For a supported component, open the cluster page in the admin UI and click **Nginx Proxy**. The panel shows:

- A dropdown of node managers — pick one to host the nginx instance. If the NM does not have nginx installed yet chango installs it via `dnf install nginx` the first time you Apply.
- The list of cluster instances behind the proxy (checkboxes). When no proxy is applied yet, every endpoint is **pre-selected** — putting all of them behind the proxy is the intended setup; uncheck the ones you want to leave out.
- The submit button says what it will do: **Apply Proxy (n)** with *n* endpoints selected; **Remove Proxy** when nothing is selected and a proxy is applied; **Pick at least one endpoint** (disabled) when nothing is selected and no proxy exists. A drawer opened to *create* a proxy never offers to remove one.
- A *Current Proxy URL* banner once the proxy is live, with the full `http://<host>:<port>` (per surface, for multi-surface components).

Apply writes the nginx config under `/etc/nginx/conf.d/chango_<component>_<clusterId>.conf` (and `/etc/nginx/stream.d/...` for stream-block surfaces like NeoRunBase pgwire), enables and reloads nginx, and remembers the chosen host + listen port in the cluster's settings.

## Listen ports

Chango's [Port Allocator](../features/port-allocator.md) picks the listen port from a component-specific band — `shannonstore-nginx` from 19200, `ontul-nginx` from 19220, `neorunbase-nginx` from 19260, and so on. The bands are spaced far enough apart that the operator can list the well-known port range per component in firewall / security-group rules.

The chosen port is shown in the Current Proxy URL banner and surfaces back through the REST API:

```bash
curl -sH "Authorization: Bearer $TOK" \
  $BASE/admin/api/clusters/ss-prod/nginx | jq .
# → { "nginxNode": "...", "nginxPort": "19200", ... }
```

## Reconciliation

When you scale the cluster (add or remove an instance), the leader's periodic nginx reconciler re-renders the nginx config to point at only the live instances, then reloads nginx. The reconciler runs every `chango.cluster.nginx.reconcile.interval.ms` (default 30 000) on the leader.

If you stop or delete an instance manually, the reconciler removes it from the upstream within the next tick.

Each component's proxy is reconciled as its own step. If the host of one component's proxy cannot be reached (node down, network partition), only that step fails — the leader log shows `nginx reconcile failed (<component> nginx): …` — and every other proxy, UI Proxy upstream and gateway route keeps being updated on the same tick. An instance whose node manager stops answering is kept in its upstream for a grace period (120 s) before it is dropped, so a node-manager restart does not empty a proxy.

## Trino Gateway — TLS and the public endpoint

The Trino Gateway nginx is a special case: it is **always TLS**. Clients reach the gateway over `https://<nginxHost>:<nginxPort>`, and nginx terminates TLS in front of the gateway's plain-HTTP listener.

That creates a subtlety Trino clients care about. A Trino query response carries `nextUri` / `infoUri` pointers that the client follows for subsequent pages. When a request arrives through nginx those are rewritten from the `X-Forwarded-*` headers, so they resolve correctly. But the gateway also has a `gateway.public.endpoint` property used as the **fallback** — and by any client that talks to a gateway directly — and that fallback must not point at the insecure raw listener.

So on **Apply**, chango sets `gateway.public.endpoint = https://<nginxHost>:<nginxPort>` on every gateway instance behind the proxy and restarts it. On **Remove**, each previously-fronted gateway is reverted to its own raw `http://<host>:<listenPort>` address, since the TLS surface no longer exists.

Two consequences worth planning for:

- **Applying or removing the gateway nginx restarts the gateway instances.** The property is per-instance and only read at start. Expect a brief interruption; do it in a maintenance window if clients are live.
- **The reconciliation is best-effort per instance.** If one gateway cannot be updated, chango logs a warning and continues with the rest rather than aborting the whole Apply — the nginx front still comes up. Re-Apply after fixing the failing instance.

Verify the result on the host:

```bash
sudo grep public.endpoint /opt/components/<gatewayInstanceId>/conf/trino-gateway.properties
# → gateway.public.endpoint=https://10.0.0.13:19240
```

## Removing the proxy

Open the same Nginx panel, uncheck every instance and click *Remove Proxy*. An empty selection is only a removal when a proxy is applied; with no proxy in place the button is disabled, and the Trino Gateway API refuses the empty request (see [Trino Gateway Routing](../features/gateway-routing.md#the-client-surface-nginx-and-it-is-always-tls)). Chango removes the `chango_<component>_<clusterId>.conf` file and reloads nginx. The chosen host's nginx daemon stays installed (it may be in use by another component's proxy on the same host).

## Multi-surface components

Some components front more than one surface from the same nginx. ShannonStore is the canonical example — one nginx listen port, three locations (`/` → S3 API, `/admin` → admin UI, `/metrics` → metrics scrape). The Current Proxy URL banner lists all three URLs.

NeoRunBase splits across `http {}` (admin REST) and `stream {}` (pgwire) — two listen ports. Both surfaces are part of the same Apply, and chango writes the stream-block snippet under `/etc/nginx/stream.d/`.

Ontul similarly uses two server blocks because its Arrow Flight SQL surface is gRPC (HTTP/2) which cannot share a server block with its HTTP/1.1 admin surface.

Both Ontul upstreams are pinned per client address (`ip_hash`). Ontul issues login tokens and Flight SQL bearer tokens per master, so a client that logs in on one master must keep talking to it — a JDBC/ADBC session over the Flight SQL port sends several RPCs per statement. Earlier 3.0.0 builds pinned only the admin upstream, and Flight SQL clients through the proxy failed with `Bearer credentials were not valid` as soon as two masters were running.

## Troubleshooting

- **nginx fails to start with `bind() to 0.0.0.0:19200 failed (13: Permission denied)`** — SELinux is enforcing and does not allow nginx to bind that port. See [Node Preparation](../installation/node-preparation.md) — SELinux should be disabled on chango hosts.
- **`semanage: command not found`** when chango tries to add an http_port_t label — install `policycoreutils-python-utils`, but the preferred answer is to disable SELinux entirely per node prep.
- **Stale upstream in nginx config** after deleting an instance — wait for the next reconciliation tick (≤30 s), or click Apply on the Nginx panel to force an immediate re-render.
- **Flight SQL (JDBC/ADBC) through the Ontul proxy fails with `Bearer credentials were not valid`** while connecting to a master directly works — the Flight upstream is not pinned. Apply the current 3.0.0 patch; the leader re-renders the conf with `ip_hash` on its next reconcile.
- **`/etc/nginx/conf.d/chango_*.conf` was hand-edited** — chango will overwrite it on the next Apply. The chango-managed surface is the source of truth; if you need extra directives, layer them in a separately-named conf file under `conf.d/`.
