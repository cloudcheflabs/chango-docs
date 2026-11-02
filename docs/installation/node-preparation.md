# Node Preparation

Chango installs onto a fleet of **Rocky Linux 9** hosts (master + node managers). The install playbook ships a `node-prep` ansible role that runs first against every host and applies SELinux + ulimit + sysctl. You do not need to do those steps by hand — they are listed here for reference, and so operators can run the same commands manually on hosts they prepared before they had ansible access.

## What `node-prep` does

| Step | Where it lands | Effective |
|---|---|---|
| SELinux → `disabled` | `/etc/selinux/config` (+ immediate `setenforce 0`) | Permissive now, fully disabled after the next reboot |
| ulimit (nofile / nproc) | `/etc/security/limits.d/chango.conf` | New login sessions / service starts |
| sysctl (mmap / somaxconn / file-max) | `/etc/sysctl.d/99-chango.conf` (+ `sysctl --system`) | Immediate |

The role is idempotent — re-running `install.yml` is safe.

## SSH access

The ansible controller (typically the master host) reaches every node over SSH as a sudoers user (Rocky 9 default `rocky`). The SSH key for the playbook user must be the same across all hosts, and `sudo` must be passwordless.

Verify before installing:

```bash
ssh -i ~/.ssh/<key>.pem rocky@<each-host>   "sudo -n true && echo ok"
```

## SELinux (applied by `node-prep`)

Chango requires SELinux **disabled**. Rocky 9's default `enforcing` mode restricts nginx to bind only the `http_port_t` set (80, 443, 8080) and rejects every other port; chango's per-component nginx bands live well outside that range, and the SELinux policy interferes with the JVM components' RocksDB + mmap usage as well.

`node-prep` runs the equivalent of:

```bash
sudo setenforce 0                                                                # Permissive now
sudo sed -i 's/^SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config         # persist across reboots
```

`setenforce 0` takes effect immediately, which is enough to get chango installed and running. The `SELINUX=disabled` line in `/etc/selinux/config` makes it permanent — you should reboot the host at the next convenient maintenance window so the kernel reloads in disabled mode.

## firewalld and umask

firewalld is **optional**. On sites that run without it (stopped/disabled or not installed), security groups or network firewalls do the filtering and the installers skip their firewall steps. When firewalld is running, the installers open the platform's port bands for the node subnet.

The operator shell's umask may be hardened (`027`, `077`). Platform processes set their own umask (`0022`) when they start, so shared directories such as `/opt/components` and `/etc/chango/certs` stay readable by components that run as other users; secret files are still created `0600`. Builds of 3.0.0 before this change inherited the shell's umask — if a component install failed with `tar extract failed (exit=2)` and `Permission denied`, check those directories with `stat -c '%a %n'` and `chmod 755` them once after patching.

## ulimit (applied by `node-prep`)

JVM components (Trino, Spark, Flink, ZooKeeper, NeoRunBase, kiok, …) open many file descriptors and threads. `node-prep` writes a single drop-in:

```bash
sudo tee /etc/security/limits.d/chango.conf > /dev/null <<'EOF'
*  soft  nofile  131072
*  hard  nofile  131072
*  soft  nproc   128000
*  hard  nproc   128000
EOF
```

The values match Trino's recommended limits (it is the largest single consumer in the bundle). The wildcard (`*`) covers every per-component system user chango creates (`chango`, `trino`, `spark`, `flink`, `postgres`, …).

## Kernel sysctl (applied by `node-prep`)

`node-prep` writes a single drop-in and runs `sysctl --system`:

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
| `<install_dir>/data` | RocksDB stores on the master — `master/kms`, `master/iam`, `metadata` |
| `/var/lib/chango` | Bundled ZooKeeper's data dir |
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

Set each node's OS hostname to its FQDN (`sudo hostnamectl set-hostname cp-1.chango.private`) — chango
registers that name and builds every console URL and internal connection from it.

Every node must then resolve every node's FQDN, either through DNS (AWS Private DNS, corporate DNS, …) or
through the same `/etc/hosts` entries on every node:

```bash
for h in cp-1.chango.private cp-2.chango.private cp-3.chango.private; do
  getent hosts "$h" || echo "MISSING: $h"
done
```

Chango never writes `/etc/hosts`; resolution is part of node preparation. The installer runs the same check
on every node and stops before changing anything if a name does not resolve.

## Verifying prep

Quick sanity check before running the playbook:

```bash
# On every host
getenforce                       # → Permissive or Disabled
ulimit -n                         # → 131072
ulimit -u                         # → 128000
sysctl vm.max_map_count           # → 262144
df -h /opt                        # → dedicated volume mounted
```

Once every host clears these, pick your install path — [Manual Install](manual.md) for a step-by-step shell-driven bring-up, or [Automated Install (Ansible)](automated.md) for a multi-host repeatable install.
