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
- The list of cluster instances behind the proxy (checkboxes — usually you check all).
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

## Removing the proxy

Open the same Nginx panel and Apply with zero instances checked, or click *Remove Proxy*. Chango removes the `chango_<component>_<clusterId>.conf` file and reloads nginx. The chosen host's nginx daemon stays installed (it may be in use by another component's proxy on the same host).

## Multi-surface components

Some components front more than one surface from the same nginx. ShannonStore is the canonical example — one nginx listen port, three locations (`/` → S3 API, `/admin` → admin UI, `/metrics` → metrics scrape). The Current Proxy URL banner lists all three URLs.

NeoRunBase splits across `http {}` (admin REST) and `stream {}` (pgwire) — two listen ports. Both surfaces are part of the same Apply, and chango writes the stream-block snippet under `/etc/nginx/stream.d/`.

Ontul similarly uses two server blocks because its Arrow Flight SQL surface is gRPC (HTTP/2) which cannot share a server block with its HTTP/1.1 admin surface.

## Troubleshooting

- **nginx fails to start with `bind() to 0.0.0.0:19200 failed (13: Permission denied)`** — SELinux is enforcing and does not allow nginx to bind that port. See [Node Preparation](../installation/node-preparation.md) — SELinux should be disabled on chango hosts.
- **`semanage: command not found`** when chango tries to add an http_port_t label — install `policycoreutils-python-utils`, but the preferred answer is to disable SELinux entirely per node prep.
- **Stale upstream in nginx config** after deleting an instance — wait for the next reconciliation tick (≤30 s), or click Apply on the Nginx panel to force an immediate re-render.
- **`/etc/nginx/conf.d/chango_*.conf` was hand-edited** — chango will overwrite it on the next Apply. The chango-managed surface is the source of truth; if you need extra directives, layer them in a separately-named conf file under `conf.d/`.
