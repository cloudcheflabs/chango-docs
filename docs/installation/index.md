# Installation Overview

Chango ships as a tarball and supports three install paths:

| Path | Use when | What you run |
|---|---|---|
| [Manual install](manual.md) | Single-host evaluation, a controlled bring-up where you want to see every step, or an air-gapped host you cannot reach with ansible. | Shell commands directly on each host. |
| [Automated install with ansible](automated.md) | Production. Multi-host clusters. Repeatable bring-up and host scale-out. | `ansible-playbook install.yml` from a controller (typically the future master host). |
| [Local Docker cluster](docker.md) | Quick functional / RBAC / tutorial validation on a developer laptop. Not for production. | `bash tests/cluster/run.sh` — one command, three Rocky 9 containers. |

The first two paths produce the **same** end state on real hosts — a chango master + bundled ZooKeeper running on the master host, a node manager running on every node host, no systemd units, the cluster master key held only in the operator's secret manager and in the JVM process environment. The Docker path produces an equivalent layout inside three Rocky 9 systemd containers so you can run the [tutorials](../tutorials/index.md) end-to-end on one machine.

## Shared prerequisites

Whichever path you take, every chango host is **Rocky Linux 9.x** with:

- SELinux disabled (or Permissive)
- raised ulimit / sysctl (file descriptors, mmap count, somaxconn)
- a dedicated `/opt` mount
- passwordless SSH between hosts (only needed for the automated path)

See [Node Preparation](node-preparation.md) for the exact values. The automated path applies these for you via the `node-prep` ansible role; the manual path means you run them yourself.

## After install

Whichever path you chose, day-2 operations (stop, restart, add hosts) are described in [Cluster Operations](../operations/cluster-operations.md). Stop / restart is always a manual shell action. Host scale-out (add master, add node manager) uses ansible on the automated path and has a manual equivalent for the manual path.

Once the cluster is up, walk through [Getting Started](getting-started.md) to install your first managed component.
