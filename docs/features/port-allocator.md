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

| Band | Default base | Used for |
|---|---|---|
| `shannonstore-zk-client` / `-peer` / `-leader` | 2181 / 2888 / 3888 | ShannonStore bundled ZK |
| `shannonstore-api-nio` | 9090 | ShannonStore API server — S3 |
| `shannonstore-api-admin` | 8888 | ShannonStore API server — admin |
| `shannonstore-data-nio` | 9500 | ShannonStore data node |
| `polaris` | 8180 | Apache Polaris (Iceberg REST catalog) |
| `postgresql` | 5432 | Managed PostgreSQL |
| `trino-coordinator` / `trino-worker` | 8480 / 8580 | Trino |
| `trino-gateway` | 8680 | Trino Gateway |
| `spark-master` / `spark-worker` | 8780 / 8880 | Spark |
| `flink-jobmanager` / `flink-taskmanager` | 8980 / 9080 | Flink |
| `kafka-broker` | 9092 | Kafka |
| `schema-registry` | 8081 | Confluent Schema Registry |
| `itdastream-broker` | 9092 | ItdaStream |
| `ontul-zk-client` / `-peer` / `-leader` | 2181 / 2888 / 3888 | Ontul bundled ZK |
| `ontul-master` / `ontul-worker` | 18080 / 18200 | Ontul |
| `neorunbase-coordinator` / `-datanode` | 18090 / 18260 | NeoRunBase |
| `kiok-master` / `kiok-worker` | 18400 / 18500 | kiok |
| `mium-master` / `mium-worker` | 18600 / 18700 | Mium |
| `ui-proxy` | 9180 | UI Proxy |
| `kafka-registry-nginx` | 19081 | nginx in front of Schema Registry |
| `itdastream-registry-nginx` | 19181 | nginx in front of ItdaStream registry |
| `shannonstore-nginx` | 19200 | nginx in front of ShannonStore |
| `ontul-nginx` / `ontul-flightsql-nginx` | 19220 / 19240 | nginx in front of Ontul HTTP / Flight SQL |
| `neorunbase-nginx` / `neorunbase-pgwire-nginx` | 19260 / 19280 | nginx in front of NeoRunBase admin / pgwire |
| `trino-gateway-nginx` | 19300 | nginx in front of Trino Gateway |

Every component that bundles its own ZooKeeper (Ontul, kiok, NeoRunBase, Kafka, ItdaStream, Mium, ShannonStore) has its own `-zk-client` / `-zk-peer` / `-zk-leader` bands at 2181 / 2888 / 3888. They share the same bases and are separated by host occupancy, not by band — see [host-awareness](#host-awareness) below.

Chango's own ports are fixed rather than allocated: `8080` (master admin + UI), `19999` (master internal), `19998` (node-manager internal), and `2181 / 2888 / 3888` for the control-plane ZK quorum.

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

The `*-nginx` bands start at 19200 and their bases are spaced 20 apart, so each component's proxy has a predictable place to look for.

Note what that does **not** mean: the bases are 20 apart but the default range is 200, so the nominal windows overlap. Collisions still cannot happen — occupancy is derived by scanning every live instance on the host, not by trusting band boundaries — but a component's nginx can legitimately land outside the 20-port stretch after its base if the host is busy.

For a firewall rule, that leaves two honest options:

- Open each band from its base for the full range (`19200–19399` for ShannonStore's). Wide, but no re-request when a component is added.
- Pin the windows first, by narrowing the range so they really are disjoint:

    ```properties
    chango.component.port.shannonstore-nginx.range = 20
    chango.component.port.ontul-nginx.range       = 20
    ```

    Then the band is exactly the stretch the rule names, and an exhausted band fails loudly at install time instead of quietly using a port nobody opened.

Either way, the ports actually allocated are recorded in each instance's config and readable from the admin UI or `GET /admin/api/clusters/<id>` — which is the list to hand a security team as installed-state evidence, rather than the bands above.
