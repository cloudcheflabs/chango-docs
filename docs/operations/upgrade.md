# Upgrade

Every component chango manages can be upgraded independently — install a fresh cluster of the new version alongside the old one, migrate workloads, then delete the old cluster. Component upgrades do not require taking the platform down.

## Upgrade a managed component (blue / green)

Components don't support in-place version upgrades — chango installs each component cluster as an immutable set of instance dirs (`/opt/components/<instanceId>/...`). The supported flow is to bring up a fresh cluster of the new version alongside the old one and cut over.

Example — upgrading Trino from 479 to 480:

1. **Stage the new tarball** on the master host:

   ```bash
   # On master
   sudo cp /path/to/trino-server-480.tar.gz /opt/chango/components/trino/
   sudo chown chango:chango /opt/chango/components/trino/trino-server-480.tar.gz
   ```

2. **Install the new cluster** from the admin UI, picking version 480 and a new cluster id (`trino-green`). Wire it up the same way as the old one — same exchange manager, same resource-group PG, same Ontul authz token. The new cluster picks fresh ports automatically (PortAllocator).

3. **Cut over** clients to the new cluster. If the Trino Gateway is in front, change the gateway's routing target; otherwise point JDBC / spark-sql at the new coordinator URL.

4. **Stop and delete** the old cluster from the admin UI once you're confident.

The same pattern works for Spark, Flink, ItdaStream, NeoRunBase, ShannonStore, and the rest — the components are designed to coexist on the same host fleet, each with their own ports and install dirs.

### Why blue / green and not rolling

A rolling upgrade of a JVM cluster (Trino, Spark, …) requires careful coordination of the engine's own state machine (running queries, exchange data, catalog state) that chango as a control plane doesn't try to know about. Blue / green is simpler, safer, and gives you a working escape hatch — the old cluster keeps running until you delete it.

## Upgrade a chango plugin (authz)

The first-party `chango-trino-authz` / `chango-spark-authz` / `chango-flink-authz` plugin JARs ship with the engine package. To upgrade a plugin in place on an existing cluster:

1. Drop the new plugin JAR into the master's `components/<engine>-authz/` directory.
2. Use the engine's Configure panel ("Ontul Authz" tab) to trigger a config update — chango re-stages the new JAR on every instance and restarts the cluster.

If you need to roll back a plugin, drop the older JAR in place and trigger the same flow.

## Upgrade JDKs

The chango install ships its own JDKs under `/opt/openlogic-openjdk-*`. To install a newer JDK:

1. Add the new JDK tarball to `ansible/roles/java<version>/files/` and bump the role's `java_version` variable.
2. Re-run the install playbook — the role installs the new JDK alongside existing ones.
3. Restart any component cluster that should use the new JDK (the engine's `javaVersion` in its install request controls which JDK its launcher picks).
