# Port Allocator

Every chango component instance needs ports — admin, internal, web UI, gossip — and many components ship more than one role (ZooKeeper + master + worker, …). The port allocator picks free, in-band, host-aware port blocks at install time so no two instances on the same host ever collide.

## What it solves

Without an allocator, every component would have to hard-code its ports. That fails as soon as:

- Two clusters of the same component land on the same host (e.g. two Trino clusters for blue / green).
- A second component reuses a port the operator has already given to another (Ontul ZK on `:2181`, Mium ZK on `:2181` on the same host).
- Chango itself uses a port a component would otherwise grab (the bundled `chango-zk` already owns `:2181` on every master host).

The allocator centralises this. Every component provisioner calls `PortAllocator.Session.allocate(host, band, count)` instead of picking a port itself, and the allocator returns a free, contiguous, in-band block.

## Bands

A **band** is a named (base, range) tuple for a specific role of a specific component. For example:

| Band | Default base | Range | Used for |
|---|---|---|---|
| `shannonstore-zk-client` | 2181 | 200 | ShannonStore bundled ZK |
| `ontul-zk-client` | 2181 | 200 | Ontul bundled ZK |
| `ontul-master` | 18080 | 200 | Ontul master (admin + internal + flightsql ports) |
| `ontul-worker` | 18200 | 200 | Ontul worker (internal + flight) |
| `mium-master` | 18600 | 200 | Mium master |
| `mium-worker` | 18700 | 200 | Mium worker |
| `shannonstore-nginx` | 19200 | 200 | Component nginx in front of ShannonStore |
| `ontul-nginx` | 19220 | 200 | Component nginx in front of Ontul HTTP |
| `ontul-flightsql-nginx` | 19240 | 200 | Component nginx in front of Ontul Flight SQL gRPC |
| `neorunbase-nginx` | 19260 | 200 | Component nginx in front of NeoRunBase admin |
| `neorunbase-pgwire-nginx` | 19280 | 200 | Component nginx stream block for NeoRunBase pgwire |

Defaults live in `PortAllocator.DEFAULT_BASE`; every band's base and range is overridable in `chango.properties` (`chango.component.port.<band>.base` / `.range`).

When `allocate(host, band, 3)` is called, the allocator scans the band from `base` to `base + range`, picking the first contiguous 3-port block that is not already in use on that host.

## Host-awareness

Two instances on **different** hosts can have the same port. The allocator scope is per-host — every host has its own occupied-port set. This is what makes the small-cluster layout (master + NM + several components on a single host) work: ports collide within a host but not across hosts.

Occupancy of a host comes from three sources:

1. **Managed component instance config** — every `port`-shaped field in the persistent `ComponentInstance` record on that host (`webuiPort`, `adminPort`, `rpcPort`, …).
2. **Chango itself** — the master admin / internal port and the chango-bundled ZK ports (`2181 / 2888 / 3888`) are reserved on every master host. The node manager's internal port is reserved on its host.
3. **In-flight reservations** — the allocator session reserves ports it has handed out for the duration of a single provision call, so a multi-role install (ZK + master + worker) does not hand the same port to two of its own roles.

The "chango-itself" reservation is what prevents the most common foot-gun: installing a component ZK (Ontul, Mium, ItdaStream) on the same host as a chango master used to silently collide on `:2181`. Now the component's ZK is automatically pushed to the next free port in its band — typically `:2182 / :2889 / :3889`.

## Sessions

Provisioners allocate ports inside a **session** (`PortAllocator.Session`). A session is one provision-or-scale operation; ports it hands out are remembered for the life of that session so a later `allocate` in the same call does not reuse them. Once the operation persists the new `ComponentInstance` records, the session ends — subsequent operations see the freshly-persisted ports through source 1 (managed component config) above.

## Failure mode

If a band is fully exhausted on a host the allocator throws `IllegalStateException` with a message like:

```
no free 3-port block for band 'ontul-master' on host 10.0.0.11 within [18080, 18280)
```

This is a deliberately loud failure — collapsing into "let's overlap" silently is much worse. The fix is either:

- Move the new instance to a less-loaded host, or
- Widen the band in `chango.properties` (`chango.component.port.ontul-master.range = 500`), or
- Delete an unused component instance that has been sitting on the host.

## Component nginx ports

The `*-nginx` bands above are deliberately spaced to non-overlapping 20-port stretches starting at 19200. This is so the operator can list well-known nginx ports per component in their firewall / security-group rules without having to look up which port a particular install landed on. The allocator still picks the actual port within the band, but the band itself is stable.
