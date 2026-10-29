# Config Change Gate

Every chango-managed component exposes a `POST /admin/api/<component>/<instanceId>/config` endpoint that writes a configuration file (or merges into one) under the instance's install dir on its host. The admin UI's **Configure → Apply & Restart** goes through the same path.

The endpoint refuses exactly two situations, both with `400 Bad Request`:

```http
HTTP/1.1 400 Bad Request

{"error":"instance 'flink-1-jobmanager-1' is STARTING — wait until it has finished starting or stopping, then repeat the request. Cluster-wide settings in the same request (the log directory, for example) were already applied and do not need repeating."}
```

```http
HTTP/1.1 400 Bad Request

{"error":"instance 'flink-1-taskmanager-2' — its node manager nm-cp-3_chango_private-19998 is not reachable, so its config files cannot be written: …"}
```

| Instance status | Config write |
|---|---|
| `RUNNING` | accepted — restart for the process to read it (Apply & Restart does this) |
| `STOPPED`, `ERROR`, `INSTALLED` | **accepted** — the next start reads the new file |
| `STARTING`, `STOPPING` | refused — wait and repeat |
| node manager unreachable | refused — nothing can write the file |

## Why only the transitional states

A stopped process reads its files the next time it starts, so writing to a `STOPPED` or `ERROR` instance cannot make the API's "success" disagree with what the process runs. A write *during* a start or stop can: whether the process read the old file or the new one is unknowable. That is the only window the gate closes.

Earlier releases accepted config only on `RUNNING` instances. That turned out to be a dead end: an instance whose configuration broke its own startup was in `ERROR`, could not be fixed until it ran, and could not run until it was fixed. The only way out was to delete and reinstall the cluster — losing jobs and state on a production system. With the current gate the recovery is the ordinary one:

1. a bad value (for example Flink `taskmanager.memory.network.fraction=5`) is applied → the TaskManagers fail to start, the cluster shows `ERROR` / `DEGRADED`
2. **Configure** → correct the value (`0.1`) → **Apply & Restart**
3. the cluster returns to `RUNNING` and the workers re-register with their master

The gate is enforced centrally in `ComponentService.requireRunningForConfigChange()` (the name is historical) — every component handler routes its config writes through it.

## What is gated

- `POST /admin/api/<comp>/<id>/config` — apply a properties map to a properties file.
- `POST /admin/api/<comp>/<id>/file` (where exposed) — write a multi-line file.

It does **not** apply to:

- `DELETE /admin/api/<comp>/<id>/file` — file deletion.
- The install request body itself (`POST /admin/api/<comp>`) — install-time properties land before the first start.
- Read-only routes (`GET /admin/api/<comp>/<id>/...`) — reads work in any state.

## Install-time properties + JVM

If you need a configuration value baked in from the very first start — heap size, custom `ontul.master.…` property, custom `trino-extra.config.properties` line — set it at **install** time. Every component's CreatePanel (Install / Properties / JVM tabs) accepts a per-role JVM config block + a `properties` map that lands on disk **before** the first `start-*.sh` is called. See [Component Operations](../operations/component-operations.md) for the install-request shape.

The gate covers **post-install** changes; install-time config is the right surface for first-start values.

For heap specifically — including chango's node-proportional Trino default and how an explicit `-Xmx` override is merged onto the packaged flags — see [JVM & Heap Tuning](../operations/jvm-tuning.md).
