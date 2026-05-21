# UI Proxy

Component web UIs — Spark Master, Trino, Trino Gateway, Flink JobManager, Polaris — are not exposed directly. The chango **UI Proxy** is the single edge entry point, and it delegates login to Ontul before forwarding requests upstream.

## Why a separate proxy

Component web UIs ship with thin or no authentication. Trino's `/ui/` shows queries and cluster state to anyone who reaches the port; Spark Master's web UI shows job graphs and worker hosts; Flink's REST surface lets you submit jobs. Putting them behind raw nginx is fine for an internal network but does not give you tenant- or role-based access.

The UI Proxy fills that gap. It is a small Netty reverse proxy that:

- Terminates the user-facing TLS / HTTP connection.
- Drives a login flow against Ontul IAM (Ontul issues a session for the end user).
- Maps each request to one of N configured upstreams (Spark Master, Trino coordinator, …) by host header.
- Forwards the request only when Ontul has authorized the user for that upstream.

Component admin UIs that already have their own auth (chango itself, Ontul, NeoRunBase admin) are typically exposed directly, not through the UI Proxy.

## Topology

The UI Proxy is a chango component like any other — install it from the admin UI, scale it across hosts, watch its CPU / memory in the same dashboard.

- Role: `proxy`, multi-instance.
- Front-end port: configurable per instance (typically `9190` or `8443`).
- Stateless — each instance hits the same Ontul for session validation.

## Upstreams

A UI Proxy upstream is one `host=url` mapping: the hostname the end user types in their browser, and the internal URL the proxy forwards to. For example:

| User-facing hostname | Internal upstream |
|---|---|
| `spark-prod-ui.chango.local` | `http://chango-m1:18180/` |
| `trino-prod-ui.chango.local` | `http://chango-m2:8480/ui/` |
| `flink-jobs-ui.chango.local` | `http://chango-n3:8081/` |

These mappings live in the chango metadata RocksDB and are pushed to every UI Proxy instance on update.

## Auto-discovery

The Create UI Proxy panel in the admin UI does not ask you to type the URLs. Chango already knows every running Spark master web UI, Trino coordinator, Trino Gateway, Flink JobManager, and Polaris HTTP endpoint — it sees their cluster + role + port through the standard component registry. The Create panel lists them as checkable rows; you pick the ones you want to expose and chango fills the upstream string itself.

A free-text "Add extra upstreams (advanced)" box is still available for endpoints chango does not manage (a customer-supplied legacy web UI, a Polaris CDN, …).

## Ontul integration

When a request arrives:

1. The UI Proxy checks for an Ontul session cookie. No cookie → redirect to Ontul's login page; on success Ontul redirects back with a session.
2. With a valid session, the proxy asks Ontul `POST /v1/api/authz/check-batch` whether the user is allowed to access the upstream — typically `(action: WEB_UI, resource: <component>.<clusterId>)`.
3. On `ALLOW`, the request is forwarded upstream with the original method / headers / body. On `DENY` or `ABSTAIN`, the proxy returns `403`.

The Ontul endpoint and the long-lived service token the proxy uses are wired at install time (the same `ontulAuthzEndpoint` + OTOK token that Trino / Spark / Flink use).

## What it is not

- **Not a load balancer**. UI Proxy maps a hostname to a single upstream URL. For load balancing across multiple Trino coordinators, run Trino Gateway in front and point the UI Proxy at the gateway.
- **Not a TLS terminator only**. The point is the auth layer. If you only want TLS, run a customer nginx instead.
- **Not for component-to-component traffic**. Chango's internal NIO and Ontul authz API are separate paths — the UI Proxy is strictly the human-facing entry.

## Day-2 ops

- **Add an upstream** — open the Configure panel, edit upstreams, save. The change rewrites the proxy config on every instance and the routing applies on the next request (no restart needed).
- **Rotate the Ontul service token** — Configure → "Ontul Authz" tab → update endpoint / token. Chango re-renders the proxy config on every instance and restarts them.
- **Scale** — install another proxy instance on a different host through the Scale panel. Hostnames in front of the proxies are resolved by your DNS or by chango's [Hosts Sync](hosts-sync.md) — load-balancing across multiple proxies is your DNS / LB layer's job.
