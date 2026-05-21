# Node Preparation

Chango installs onto a fleet of **Rocky Linux 9** hosts (master + node managers). Before running the install playbook, every host needs the following preparation. This is a one-time, idempotent setup — skip it and the install will fail in subtle ways (nginx port bind, JVM file-descriptor exhaustion, RocksDB mmap limits).

## SSH access

The ansible controller (typically the master host) reaches every node over SSH as a sudoers user (Rocky 9 default `rocky`). The SSH key for the playbook user must be the same across all hosts, and `sudo` must be passwordless.

Verify before installing:

```bash
ssh -i ~/.ssh/<key>.pem rocky@<each-host>   "sudo -n true && echo ok"
```

## SELinux

**Disable SELinux.** Rocky 9's default `enforcing` mode restricts nginx to bind only the `http_port_t` set (80, 443, 8080) and rejects every other port. Chango's per-component nginx bands live well outside that range — leaving SELinux on means every component nginx fails at first start.

```bash
sudo sed -i 's/^SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config
sudo setenforce 0      # take effect immediately (Permissive)
sudo reboot            # required for SELINUX=disabled to fully take effect
```

`setenforce 0` switches to **Permissive** without a reboot, which is enough to get chango installed; the `SELINUX=disabled` line then makes it permanent across reboots.

## ulimit (per-user)

JVM components (Trino, Spark, Flink, ZooKeeper, NeoRunBase, kiok, …) open many file descriptors and threads. Raise the limits at the OS level so the JVM defaults don't cap behaviour.

```bash
sudo tee /etc/security/limits.d/chango.conf > /dev/null <<'EOF'
*  soft  nofile  65536
*  hard  nofile  65536
*  soft  nproc   32768
*  hard  nproc   32768
EOF
```

Use a wildcard (`*`) so the same limits apply to every system user chango creates per component (`chango`, `trino`, `spark`, `flink`, `postgres`, …).

## Kernel sysctl

For larger clusters, raise:

```bash
sudo tee /etc/sysctl.d/99-chango.conf > /dev/null <<'EOF'
vm.max_map_count = 262144
net.core.somaxconn = 4096
fs.file-max = 2000000
EOF
sudo sysctl --system
```

- `vm.max_map_count` — RocksDB / Iceberg use mmap heavily.
- `net.core.somaxconn` — nginx + Trino HTTP backlog.
- `fs.file-max` — system-wide FD ceiling for many JVMs on one host.

## Disk layout

Chango defaults its data path to `/opt`:

| Path | Used by |
|---|---|
| `/opt/chango` | Chango master/NM install dir |
| `/opt/components/<instanceId>` | Each managed component instance |
| `/var/lib/chango` | RocksDB stores (KMS, IAM, metadata) on the master |
| `/var/log/chango` | Chango master + NM log files |

Mount a dedicated data volume at `/opt`:

```bash
# Example for an AWS EBS volume attached as /dev/xvdb
sudo mkfs.xfs -f /dev/xvdb
sudo mount /dev/xvdb /opt
echo "UUID=$(sudo blkid -s UUID -o value /dev/xvdb)  /opt  xfs  defaults,nofail  0 2" | sudo tee -a /etc/fstab
```

If `/opt` already has content (a previously installed JDK, for example), copy it across the new mount first:

```bash
sudo mount /dev/xvdb /mnt/newopt
sudo rsync -a /opt/ /mnt/newopt/
sudo umount /mnt/newopt
sudo mount /dev/xvdb /opt
```

## hostnames

Chango supports two hostname models:

- **Real FQDNs already in DNS** (AWS Private DNS, your corporate DNS, …) — chango registers the OS canonical hostname (`hostname -f`) as the node's FQHN and **does not** rewrite `/etc/hosts`. Component-to-component connections use those FQDNs directly.
- **Short hostnames only** — chango synthesizes `<short>.<chango.cluster.domain>` (default `chango.private`) for every node and keeps a managed block in `/etc/hosts` on every host in sync with cluster membership.

Either model works; nothing to configure beforehand. See [Hosts Sync](../features/hosts-sync.md) for details.

## Verifying prep

Quick sanity check before running the playbook:

```bash
# On every host
getenforce                       # → Permissive or Disabled
ulimit -n                         # → 65536
ulimit -u                         # → 32768
sysctl vm.max_map_count           # → 262144
df -h /opt                        # → dedicated volume mounted
```

Once every host clears these, you're ready to [Download & Install](installation.md).
