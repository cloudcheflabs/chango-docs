# Kafka Connect & Topics

A Kafka cluster installed by chango can also run **Kafka Connect**, with its
plugins managed from the console — including Debezium, which ships in the chango
bundle. The same screen lists, creates and deletes **topics**.

## One Connect cluster per Kafka cluster

Connect is a fourth role on an existing Kafka cluster, alongside `zookeeper`,
`broker` and `registry`. It is not a separate component, and there is no second
Connect cluster to create.

That is a design decision rather than a simplification. A Connect cluster is
identified by its `group.id` and by three internal topics — `config.storage.topic`,
`offset.storage.topic`, `status.storage.topic`. Two Connect clusters on one Kafka
that share any of them overwrite each other's connector configurations, with no
error at either end. Deriving all four from the Kafka cluster id removes the
question instead of asking an operator to get it right:

```
group.id              = connect-<kafkaClusterId>
config.storage.topic  = connect-configs-<kafkaClusterId>
offset.storage.topic  = connect-offsets-<kafkaClusterId>
status.storage.topic  = connect-status-<kafkaClusterId>
```

These are provisioner-owned and cannot be edited.

Install several Kafka clusters and each gets its own Connect, bound to its own
brokers. Adding nodes adds **workers** to that one Connect cluster; connector
tasks spread across them.

!!! note "No separate download"
    `connect-distributed` ships inside the Apache Kafka distribution, so a Connect
    worker installs from the same tarball as a broker. Nothing extra is fetched.

### Ports

Connect's REST port comes from the existing **`kafka-broker` band**, not a band of
its own. Connect belongs to one Kafka cluster, so keeping its port in the same
200-wide window as that cluster's brokers means one firewall rule per Kafka
cluster rather than one per role. Widening
`chango.component.port.kafka-broker.range` widens it for Connect too — that
coupling is intended. See [Port Allocator](port-allocator.md).

### Converters

When the Kafka cluster has a Schema Registry, Connect defaults to Avro against it.
Without one it defaults to JSON with schemas off. Either can be overridden per
connector.

## Plugins

**The master holds the authoritative copy; the workers get pushed copies.**

Pushing an upload straight at the workers and keeping nothing is the obvious
design, and it breaks on the first scale-out: a worker added later installs from
the Kafka package with none of the plugins the others picked up since, so
connectors run until a task happens to land on it and then fail with a missing
connector class. Keeping the set on the master makes a scale-out a replay of it.

```
master:  <base.data.dir>/master/connect-plugins/<kafkaClusterId>/<pluginId>/
worker:  <installPath>/plugins/<pluginId>/        ← plugin.path points at the parent
```

Each plugin gets **its own directory**, which is not cosmetic: Connect gives every
directory under `plugin.path` its own classloader. Flattening two connectors into
one directory is how a dependency clash becomes a `NoSuchMethodError` that neither
connector produces on its own.

### Installing or removing restarts the workers

Connect scans `plugin.path` **once, at startup**. A plugin copied to a running
worker is on disk and invisible — which looks exactly like the upload having
failed. chango therefore restarts every Connect worker after a plugin changes,
and the console says so before you click.

The brokers are not involved; only the Connect workers restart.

### Bundled Debezium

Debezium **2.6.2.Final** ships in the chango bundle, for MySQL, PostgreSQL,
SQL Server and MongoDB. One click installs it with no internet access — the
deployments that most need change data capture are the air-gapped ones, and
Confluent Hub is not reachable from them.

The version is pinned to the one Ontul's flow embeds (`debezium-embedded
2.6.2.Final`), so a CDC pipeline assembled through chango's Connect and one
assembled inside Ontul produce the same records. A different connector version
would not fail; it would quietly change the envelope, which is worse.

It installs with the Connect role when *Install the bundled Debezium connectors*
is left ticked, and afterwards from the Plugins tab:

```bash
# all four
curl -X POST "http://master:8080/admin/api/kafka/<id>/connect/plugins/default" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'

# or name the ones you want
… -d '{"connectors":["postgres","mysql"]}'
```

### Uploading your own

The console accepts a `.zip`, a `.tar.gz` or a bare `.jar`. The archive is
unpacked on the master, checked to contain at least one jar, and pushed to every
worker.

```bash
curl -X POST "http://master:8080/admin/api/kafka/<id>/connect/plugins?pluginId=my-connector" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/octet-stream' \
  --data-binary @my-connector-1.0.0.zip
```

`name` and `version` may be passed as query parameters too; they are recorded
with the plugin and shown in the console. `pluginId` is required, because it is
the directory name on every worker and therefore the identity chango replays on a
scale-out.

A wrapper directory inside the archive is collapsed: Connect looks exactly one
level under `plugin.path`, and a plugin nested one deeper is simply not found —
reported as a connector class that does not exist.

A bare jar is accepted as a jar and not unpacked. A jar *is* a zip, so an unpacker
that trusts the magic bytes turns one into a directory of class files that Connect
cannot load; the archive is checked for a jar entry inside before it is treated as
a bundle.

!!! warning "Installed is not the same as loaded"
    The Plugins tab also shows **what the workers actually loaded**, read back from
    Connect. The two lists differ exactly when something went wrong, which is when
    you are looking at them.

## Connectors

Connector configuration is **proxied to Connect and stored nowhere by chango**.
Connect keeps it in `config.storage.topic`; a second copy here would drift the
moment anything touched Connect directly — a `kafka-connect` CLI, another
console, a connector that reconfigured itself.

```
GET/POST/PUT/DELETE  /admin/api/kafka/<id>/connect/connectors[/<name>[/...]]
GET                  /admin/api/kafka/<id>/connect/connector-plugins
```

Connect's own errors pass through unchanged. They name the failing field
("Connector configuration is invalid and contains the following 1 error(s)"),
and rewrapping them in a chango error loses the part that matters.

## Topics

List, create and delete from the Kafka page.

- **Internal topics are shown and marked**, not hidden. Connect's own
  configuration lives in one, and a console that hides it cannot answer "where
  did my connector go". Deleting one is refused.
- **A replication factor above the broker count is refused**, with that fact in
  the message. Kafka's own error names the topic and not the cause, and on a
  single-broker development cluster this is the mistake people actually make.

Topic operations go through the Kafka admin client from the master, not a
subprocess on a node manager. One client library is a far smaller surface than a
generic "run this command on a node" capability.

## Walkthrough

1. Install a Kafka cluster (ZK + brokers, Schema Registry optional).
2. Open the cluster → **Kafka Connect** → *Workers* → pick nodes → **Install
   Kafka Connect**. Leave *Install the bundled Debezium connectors* ticked for CDC.
3. *Plugins* — confirm the workers loaded what you installed.
4. *Connectors* — create one. For Debezium against PostgreSQL:

   ```json
   {
     "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
     "tasks.max": "1",
     "database.hostname": "pg.internal",
     "database.port": "5432",
     "database.user": "debezium",
     "database.password": "…",
     "database.dbname": "inventory",
     "topic.prefix": "inventory"
   }
   ```

5. **Topics** — the connector's topics appear as it starts emitting.

## See also

- [Port Allocator](port-allocator.md) — why Connect has no band of its own.
- [Component Lifecycle](../architecture/component-lifecycle.md) — how a role is installed, scaled and removed.
