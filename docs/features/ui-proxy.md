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
| `spark-prod-master-1-ui.chango.local` | `http://chango-m1:8780` |
| `spark-prod-livy-1-ui.chango.local` | `http://chango-m1:8998/ui` |
| `trino-prod-coordinator-1-ui.chango.local` | `http://chango-m2:8480/ui` |
| `flink-jobs-jobmanager-1-ui.chango.local` | `http://chango-n3:8980` |

These mappings live in the chango metadata RocksDB and are pushed to every UI Proxy instance on update.

## Auto-discovery

The Create UI Proxy panel does not ask you to type URLs. Chango already knows every running component UI — cluster, role and port come from the component registry — and lists them as checkable rows. What it offers:

| Component | Roles offered | Path |
|---|---|---|
| Spark | master, worker, history-server, **Livy** | `/`, Livy at `/ui/` |
| Trino | coordinator | `/ui/` |
| Trino Gateway | all | `/` |
| Flink | jobmanager | `/` |
| Polaris | all | `/` |

A free-text **Add extra upstreams (advanced)** box remains for endpoints chango does not manage.

### Running clusters register themselves

Picking from the list is only the convenient path. The leader also pushes every running Spark, Trino and Flink UI into each proxy cluster's *managed upstream* slot on its reconcile tick, so installing a component after the proxy makes its UI appear without anyone editing the proxy — and scaling or deleting that component updates or empties the slot the same way.

The combined set (what you picked + what registered itself) is written to every instance's `ui-proxy.properties`, and the proxy instances are **restarted one at a time** when it changes. They read that file once, at startup; writing it and stopping there would leave the routing table correct on disk and the running proxy still answering 404 for the UI just installed.

!!! note "The left-hand side is a hostname, not a label"
    Auto-registered entries are named `<instanceId>-ui.chango.local`, matching what the Create panel suggests. The proxy routes by `Host` header, so this is a name the browser has to resolve to the proxy — point a wildcard record (`*.chango.local`) at it, or add the names to the clients' hosts file. Entries used to be the bare instance id, which resolves nowhere, so every auto-registered UI was unreachable while looking configured.

### Paths matter as much as ports

The proxy forwards to `upstream + request path`, so a UI that does not live at the root of its port needs that prefix in the upstream. Trino's UI is at `/ui`, and **Livy serves its REST API at `/` with the dashboard at `/ui`** — an upstream of just `host:port` for Livy lands the operator on JSON.

## Signing in

When a request arrives:

1. The proxy looks for its **own** session cookie (`chango_ui_session`). Without one, it serves its login page.
2. The credentials typed there are posted to Ontul's `POST /admin/auth/login`. Ontul answers yes or no; the proxy does not reuse Ontul's token.
3. On success the proxy mints its own AES-256-GCM session cookie, signed with the cluster-wide `uiproxy.session.secret`, and forwards the original request upstream.

The cookie is the whole session — there is no server-side store. Every instance of a proxy cluster holds the same secret, so any instance can validate a session any other instance issued, and scaling the proxy needs no sticky routing.

!!! note "Authentication, not authorization"
    A signed-in user reaches **every** upstream the proxy routes for. The proxy does not ask Ontul whether this person may see this particular dashboard. If a dashboard must be restricted to a subset of your operators, run a second proxy cluster with only those upstreams, or restrict by SSO group (below).

### Directory passwords work with nothing configured

Ontul's login route falls back to the directory when the password is not one it stores, so an operator whose account lives in **LDAP or Active Directory** simply types it into the proxy's form. There is nothing to configure on the proxy for that, and nothing to configure twice.

### Single sign-on (OIDC, SAML)

A password — local or directory — is a form post, so it can be forwarded to Ontul. **OIDC and SAML cannot be**: they send the browser to the identity provider and back, and Ontul's callback redirects only to a path on Ontul and delivers the session in a URL *fragment*, which a browser never sends to a server. So the proxy performs those two flows itself, using the same `ccl-sso` library chango's control plane uses — the same code validates the issuer, audience, expiry and signature on both sides of the product.

Configure them under **Configure → Single Sign-On** on the UI Proxy page. The login page then shows a button per configured provider, and nothing for the ones that are not.

```properties
uiproxy.sso.oidc.enabled      = true
uiproxy.sso.oidc.issuer       = https://keycloak.example.com/realms/company
uiproxy.sso.oidc.client.id    = chango-uiproxy
uiproxy.sso.oidc.client.secret= …
uiproxy.sso.oidc.redirect.uri = https://spark-prod-ui.chango.local/chango-auth/sso/oidc/callback
uiproxy.sso.oidc.groups.claim = groups

uiproxy.sso.saml.enabled      = true
uiproxy.sso.saml.idp.entity.id= https://idp.example.com/realms/company
uiproxy.sso.saml.idp.sso.url  = https://idp.example.com/protocol/saml
uiproxy.sso.saml.idp.certificate = MIIC…
uiproxy.sso.saml.sp.entity.id = chango-uiproxy
uiproxy.sso.saml.sp.acs.url   = https://spark-prod-ui.chango.local/chango-auth/sso/saml/acs

uiproxy.sso.group.mappings    = platform-ops:viewers
```

**Register the proxy at your provider in its own right.** Its callback URL is its own, not the console's — this is a second relying party, which is inherent to a redirect flow rather than a chango decision. The proxy publishes its SAML SP metadata at `/chango-auth/sso/saml/metadata`, which beats transcribing the entity id and ACS URL by hand.

**Group mapping is the only restriction available.** Left empty, any identity the provider authenticated is let through — the proxy fronts dashboards, and an operator who wrote no mapping asked for no restriction. Once set it is exhaustive: an identity whose groups all map to nothing is refused rather than admitted with none, because the latter produces someone who is signed in and sees everything.

!!! warning "Replay protection is per-instance"
    A SAML assertion is single-use, and the proxy records used ones **in memory**. With several proxy instances behind one address, an assertion replayed to a different instance inside its validity window would be accepted. The control plane keeps that record in ZooKeeper; the proxy has no coordination service to keep it in. Keep the assertion validity window short at the provider. `ccl-sso` logs a warning at startup when no shared guard is configured.

Behind several proxy instances, the login state — including the PKCE verifier — is sealed with the same cluster-wide session secret and carried in the `state` parameter rather than held in one JVM. Unsealing it is also the login-CSRF check. Without that, SSO would work on a single instance and fail on roughly half of all attempts behind a load balancer, looking like a problem at the provider.

## What it is not

- **Not a load balancer**. UI Proxy maps a hostname to a single upstream URL. For load balancing across multiple Trino coordinators, run Trino Gateway in front and point the UI Proxy at the gateway.
- **Not a TLS terminator only**. The point is the auth layer. If you only want TLS, run a customer nginx instead.
- **Not for component-to-component traffic**. Chango's internal NIO and Ontul authz API are separate paths — the UI Proxy is strictly the human-facing entry.

## Day-2 ops

- **Add an upstream** — open the Configure panel, edit upstreams, save. The change rewrites the proxy config on every instance and the routing applies on the next request (no restart needed).
- **Rotate the Ontul service token** — Configure → "Ontul Authz" tab → update endpoint / token. Chango re-renders the proxy config on every instance and restarts them.
- **Scale** — install another proxy instance on a different host through the Scale panel. Hostnames in front of the proxies are resolved by your DNS or by chango's [Hosts Sync](hosts-sync.md) — load-balancing across multiple proxies is your DNS / LB layer's job.
