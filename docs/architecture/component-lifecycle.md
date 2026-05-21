# Component Lifecycle

Every managed component goes through the same lifecycle — install, start, stop, restart, scale, delete. This page traces the actual bytes and processes that move at each step, so the operator knows what to look at when a step gets stuck.

## Install

The master pushes a component package (tarball) to one or more node managers, the NM extracts it into a per-instance directory, writes per-instance config files, and hands ownership to the component's run-as user.

```
[admin UI]          [chango master]                 [node manager]
   |                      |                              |
   |--POST /admin/api---->|                              |
   |  <component>         |                              |
   |  + cluster spec      |                              |
   |                      |--COMPONENT_INSTALL_BEGIN---->|
   |                      |  (header: instanceId,        |
   |                      |   installPath, runAs,        |
   |                      |   startCmd, stopCmd,         |
   |                      |   pidFile, env, config,      |
   |                      |   files{}, binaryArtifacts{})|
   |                      |                              |  (NM extracts tarball,
   |                      |                              |   writes config files,
   |                      |                              |   chowns to runAs user)
   |                      |--COMPONENT_INSTALL_DATA----->|
   |                      |  (chunked tarball bytes)     |
   |                      |--COMPONENT_INSTALL_END------>|
   |                      |                              |
   |                      |<-COMPONENT_INSTALL_RES-------|
   |                      |  (status: INSTALLED)         |
   |<-200 OK--------------|                              |
```

The component instance is now persisted in:

- **Master metadata RocksDB** — `ComponentInstance` record (the source of truth for the cluster).
- **NM local RocksDB** — the NM's cached copy with the same fields plus the runtime pid.

The instance is **not** started yet — install only puts the bytes on disk.

## Start

```
[admin UI]          [chango master]                 [node manager]
   |                      |                              |
   |--POST /api/.../start>|                              |
   |                      |--COMPONENT_START------------>|
   |                      |  (instanceId)                |
   |                      |                              |  (runShell:
   |                      |                              |    sudo -u <runAs>
   |                      |                              |    bin/start-X.sh ... &)
   |                      |                              |
   |                      |                              |  (readPidFile:
   |                      |                              |    open <installPath>/<pidFile>,
   |                      |                              |    retry up to 10×200ms,
   |                      |                              |    sudo cat fallback for 0700 dirs)
   |                      |                              |
   |                      |                              |  inst.setPid(pid)
   |                      |                              |  inst.setStatus(RUNNING)
   |                      |                              |
   |                      |<-status RUNNING-------------|
   |<-200 OK--------------|                              |
```

Start is **idempotent** — calling start on an already-running instance returns success without re-running the start script.

### Daemonizing vs foreground

- A daemonizing start script (Trino's `bin/launcher start`, ZooKeeper's `zkServer.sh start`) returns quickly; the NM reads the pid from the component's pidfile.
- A foreground start (`SparkSubmit`, …) does not return; the NM treats it as a child process and tracks the child pid directly.

The NM knows which is which by whether the start command exits within the operation timeout. Both modes record a `pid` in the instance record so subsequent stop / metrics work the same way.

## Stop

```
[admin UI]          [chango master]                 [node manager]
   |                      |                              |
   |--POST /api/.../stop->|                              |
   |                      |--COMPONENT_STOP------------->|
   |                      |  (instanceId)                |
   |                      |                              |  (runShell:
   |                      |                              |    sudo -u <runAs>
   |                      |                              |    bin/stop-X.sh)
   |                      |                              |
   |                      |                              |  (if stop script absent
   |                      |                              |   or exits non-zero:
   |                      |                              |    kill -TERM <pid>,
   |                      |                              |    wait grace period,
   |                      |                              |    kill -KILL <pid>
   |                      |                              |   — via sudo as runAs)
   |                      |                              |
   |                      |<-status STOPPED--------------|
   |<-200 OK--------------|                              |
```

Stop is idempotent. Killing the process happens as the component's `runAs` user — the NM's own user typically cannot signal another user's process and would silently fail. `sudo -n -u <runAs> kill` is the supported path.

## Restart

Stop then start, but skips the persistent-state changes between them. Equivalent to:

```
POST /api/<component>/<clusterId>/stop
POST /api/<component>/<clusterId>/start
```

Cluster-level restart walks the component's start order in reverse for stop, then forward for start. For Trino: stop workers → stop coordinator → start coordinator → start workers.

## Scale

`POST /api/<component>/<clusterId>/scale` with an additional list of NM nodeIds (one per new instance). The provisioner walks the new entries through the same install + start path; existing instances are not touched. Unscale (remove instances) is the inverse — stop + delete the listed instance ids.

Components with a topology constraint (Trino expects an odd number of workers? No. ZooKeeper expects an odd quorum? Yes) carry the constraint in their provisioner. The provisioner refuses a scale request that would violate it.

## Delete

Delete is destructive — the component's install dir and any data dir it manages are removed.

```
[admin UI]
   |
   |--DELETE /api/.../<clusterId>-->
                |
                |--COMPONENT_STOP--->  (every instance in the cluster)
                |--COMPONENT_DELETE-->
                |    (NM: sudo rm -rf <installPath>; unregister from NM RocksDB)
                |
                |--remove from master metadata RocksDB
                |--remove from any nginx config that referenced the cluster
                |
                <--200 OK
```

A deleted cluster id is free to be reused immediately. Component data that lives outside the install dir (S3 objects, Iceberg files, NeoRunBase data dirs) is **not** removed — chango does not own data-plane state.

## What you do not see in the admin UI

The lifecycle is deliberately narrow — install / start / stop / restart / scale / delete plus config update. Everything richer (rolling upgrade across versions, online repair of a stuck instance, etc.) is built on top of these primitives, either by the operator (blue / green) or by a future provisioner extension.
