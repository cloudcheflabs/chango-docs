# Config Runtime-Only Policy

Every chango-managed component exposes a `POST /admin/api/<component>/<instanceId>/config` endpoint that writes a configuration file (or merges into one) under the instance's install dir on the live host. The endpoint **requires the target instance to be RUNNING**. Hitting it against a STOPPED instance returns `400 Bad Request`:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error":"instance 'ontul-main-master' is STOPPED — config changes require RUNNING; start the instance first."}
```

This is policy, not a limitation — chango deliberately refuses to mutate files on a stopped instance.

## Why

The admin REST API and the on-disk install dir need to be in lockstep about what the next process start will read. Two failure modes the policy prevents:

1. **Silent drift on next start.** A daemon whose `start-*.sh` re-derives content from chango master cluster settings (e.g. Postgres writing `postgresql.conf` from sweep state, ShannonStore writing `server.conf` from the leader's metadata copy, Trino writing `config.properties` from the install request) would overwrite the just-edited file the moment it starts. The config endpoint would have returned `200` ten minutes earlier; the running process never sees the change. Restricting config to RUNNING means the change lands while the daemon is alive, and the next stop / start round-trips through the same file the operator just edited.
2. **Inventory desync.** Some component services keep the latest applied config in the metadata RocksDB so a follower master can serve the same view a freshly-restarted instance would. Editing the on-disk file when the chango-side state machine says "STOPPED" leaves those two copies divergent — and an admin UI that says "you can edit" but a component that says "we're not running" is a footgun.

The policy is enforced centrally in `ComponentService.requireRunningForConfigChange()` — every component handler (`handleOntul`, `handleKiok`, `handleTrino`, …) routes its config write through it.

## What is gated

The runtime-only gate applies to **post-install config mutation**:

- `POST /admin/api/<comp>/<id>/config` — apply a properties map to a properties file.
- `POST /admin/api/<comp>/<id>/file` (where exposed) — write a multi-line file.

It does **not** apply to:

- `DELETE /admin/api/<comp>/<id>/file` — file deletion is a cleanup that's safe on STOPPED instances.
- The install request body itself (`POST /admin/api/<comp>`) — install always lands while the instance is not RUNNING yet; the gate would defeat install.
- Read-only routes (`GET /admin/api/<comp>/<id>/...`) — reads work in any state.

## What you do instead

Start the instance, then edit. The flow is the same for every component:

```bash
# 1. Start (or restart) the instance
curl -X POST -H "Authorization: Bearer $TOK" \
     $BASE/admin/api/ontul/ontul-main-master/start

# 2. Wait for RUNNING (the instance shows status=RUNNING in the topology view)

# 3. Apply the config change
curl -X POST -H "Authorization: Bearer $TOK" \
     -H 'Content-Type: application/json' \
     -d '{"file":"conf/ontul-master.properties","properties":{"…":"…"}}' \
     $BASE/admin/api/ontul/ontul-main-master/config

# 4. Restart for the change to take effect
curl -X POST -H "Authorization: Bearer $TOK" \
     $BASE/admin/api/ontul/ontul-main-master/restart
```

The admin UI's Configure panels enforce the same flow — the **Save** button is disabled (with a tooltip "instance is STOPPED — start it first") while the instance's live status is not RUNNING.

## Install-time properties + JVM

If you need a configuration value baked in from the very first start — heap size, custom `ontul.master.…` property, custom `trino-extra.config.properties` line — set it at **install** time. Every component's CreatePanel (Install / Properties / JVM tabs) accepts a per-role JVM config block + a `properties` map that lands on disk **before** the first `start-*.sh` is called. See [Component Operations](../operations/component-operations.md) for the install-request shape.

The runtime-only policy is for **post-install** drift; install-time config is the right surface for first-start values.
