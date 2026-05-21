# Hosts Sync

Chango cluster components talk to each other by hostname. For that to work without an external DNS, every host in the cluster needs to resolve every other host's name to its private IP. Chango maintains this automatically — but only when your OS hostnames are *not* already real FQDNs.

## The policy

The chango master and every node manager runs a small `HostsSyncService` in the background. On startup and on every ZooKeeper node-registry change, the service walks the cluster membership and either:

- **Leaves `/etc/hosts` alone** — when the local OS hostname is already a real FQDN (a name with at least one dot, that isn't an IP literal). The assumption is that the operator's DNS resolves that FQDN, and chango should not race with it.
- **Maintains a managed `# BEGIN chango` … `# END chango` block** in `/etc/hosts` — when the local OS hostname is a single short label. Every cluster member is added to the block under `<short>.<chango.cluster.domain>` (default `chango.private`).

The decision is per-host. In a cluster of three hosts where two have real FQDNs and one does not, the two FQDN hosts keep `/etc/hosts` untouched; the short-hostname host writes a chango block for itself. Mixing the two models is unusual but does not break anything — chango uses the registered FQHN, which is empty for FQDN-already hosts and synthesized for short hosts.

## Why "FQDN-already" hosts opt out

Operators with corporate DNS (or AWS Private DNS, GCP internal DNS, etc.) already advertise hostnames their network resolves. Adding chango entries to `/etc/hosts` on those hosts would shadow the DNS answer and break any tool that expects the official resolution path (TLS cert SANs, audit, …).

A node whose `getCanonicalHostName()` returns something like `ip-10-0-0-11.ap-northeast-2.compute.internal` or `host1.example.com` is considered FQDN-already.

## Why short-hostname hosts get a synthesized domain

In environments without DNS — docker compose, Vagrant, single-host laptops, air-gapped lab racks — the OS hostname is a single label like `chango-m1` or `node-3`. Chango needs a stable name to use in JDBC URLs, kafka bootstrap servers, and component configs that cannot use raw IPs. The synthesized `<short>.chango.private` is that stable name. Every host in the cluster writes the same chango block, so every host resolves every other host's name to its private IP.

The domain part is `chango.cluster.domain` (`chango.properties`, default `chango.private`). Change it per-environment if `.chango.private` clashes with anything in your organisation.

## What the block looks like

```
# BEGIN chango — managed by chango, do not edit below
10.0.0.11	chango-m1.chango.private
10.0.0.12	chango-n2.chango.private
10.0.0.13	chango-n3.chango.private
# END chango
```

Only the lines between the markers are touched. Operator-added entries above or below survive untouched.

## Update cadence

- **At startup**, before chango makes any FQHN-based connection, `HostsSyncService.syncNow()` runs synchronously so the first connect attempt always sees a current block.
- **Periodically**, every `chango.cluster.hosts.sync.interval.ms` (default 30 s), the service reconciles the block against the current ZK registry.
- **On node add / remove**, the ZK watch fires immediately and triggers an extra sync within ~1 s — joining nodes appear, departing nodes disappear, without waiting for the next periodic tick.

## How chango writes a root-owned file

`/etc/hosts` is owned by `root`. Chango runs as the `chango` user (with passwordless sudo). The write path is:

1. Write the new content to a temp file under `/tmp/`.
2. `sudo -n cp tmp /etc/hosts`.
3. Delete the temp file.

If sudo is misconfigured the periodic sync logs `sudo cp /etc/hosts failed` and chango carries on — the cluster keeps running, but stale entries persist. The fix is to restore passwordless sudo for the chango user.

## What this does not do

- It does **not** assign hostnames. The hostname is the OS's; chango only adds resolutions.
- It does **not** secure /etc/hosts against poisoning. Anyone with root on the host can edit the block. Use OS-level controls (read-only root fs, immutable bit, SELinux / AppArmor) if that's a concern.
- It does **not** publish to external DNS. The synthesized `.chango.private` domain is local to the cluster's `/etc/hosts` files — no DNS server speaks for it.
