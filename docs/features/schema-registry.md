# Schema Registry: subjects, versions, compatibility

A Schema Registry cluster installed by chango is managed from the console:
subjects and their versions are listed, schemas are registered and read back,
and the compatibility level that decides which next version is allowed is set
per subject or globally.

## Schema types

Asked of the registry, not assumed by chango. `GET /schemas/types` reports what
the server can actually parse, and the console offers exactly that:

| Type | Provider in the bundled registry |
|---|---|
| `AVRO` | built in |
| `JSON` | `kafka-json-schema-provider` |
| `PROTOBUF` | `kafka-protobuf-provider` |

All three ship with Confluent Community 7.7.1, so all three work out of the box
with no extra install. Hardcoding a list instead would mean a type offered in
the console that the server cannot handle — and the failure arrives at register
time, as a 422 that reads like a malformed schema rather than an unsupported
format.

### What to paste into the console

The **schema body itself**, not wrapped in `{"schema": "…"}` — the console does
that. Protobuf is the one that is not JSON: it is proto IDL text.

```javascript title="AVRO"
{"type":"record","name":"Order","fields":[{"name":"id","type":"string"}]}
```

```javascript title="JSON"
{"type":"object","properties":{"id":{"type":"string"}}}
```

```protobuf title="PROTOBUF"
syntax = "proto3"; message Order { string id = 1; }
```

!!! note "Verified with real clients, not only the REST API"
    The e2e suite produces and consumes a message per type through the Confluent
    serialisers — so what is proven is the client path: the serialiser
    auto-registering its subject on first send, the wire format (magic byte +
    4-byte schema id + payload), and the consumer resolving that id back into a
    schema. Registering over REST and reading it back would prove only that the
    registry stores JSON.

## chango stores none of it

Subjects, versions and schemas live in the registry's own Kafka `_schemas`
topic, and the console proxies every call straight through. A copy kept in
chango would be wrong the moment anything else wrote to the registry — a
producer registering a schema on its first send, a Connect converter, another
console — which is exactly when a stale copy does the most damage.

```
GET    /admin/api/schema-registry/<id>/registry/subjects[?deleted=true]
GET    /admin/api/schema-registry/<id>/registry/subjects/<s>/versions[/<v>|/latest]
POST   /admin/api/schema-registry/<id>/registry/subjects/<s>/versions
DELETE /admin/api/schema-registry/<id>/registry/subjects/<s>[/versions/<v>][?permanent=true]
GET    /admin/api/schema-registry/<id>/registry/config[/<s>]
PUT    /admin/api/schema-registry/<id>/registry/config[/<s>]
POST   /admin/api/schema-registry/<id>/registry/compatibility/subjects/<s>/versions/latest
GET    /admin/api/schema-registry/<id>/registry/schemas/types
```

The registry's errors reach the operator unchanged. They carry an `error_code`
and a message naming the incompatibility, and a chango-shaped wrapper would
drop the part that is acted on.

!!! note "Writes go through the leader"
    Reads are answered by any master. Registration, deletion and compatibility
    changes are leader-forwarded, so two consoles cannot register conflicting
    versions of one subject in the same moment.

Calls are made with the registry's own media type
(`application/vnd.schemaregistry.v1+json`). It tolerates `application/json` on
reads and rejects it on some writes, so sending one content type for everything
would make registration fail against a server that is fine.

## Versions

Registering against an existing subject produces a **new version**, and every
earlier one stays readable. The console lists them as `v1 v2 v3…`; selecting an
older version shows **that** version's schema, which is the point of keeping
them — a consumer still holding an older schema id is still resolving it.

A version number is never reused, including after a delete.

## Registering is adding a version

Registering against an existing subject produces a **new version**. The old one
is not replaced, and a consumer holding an older schema id keeps resolving it —
that is what makes a rolling producer upgrade safe.

Whether the new version is accepted is decided by the subject's compatibility
level. The console offers a **compatibility check before registering**, which
answers the question that matters while there is still time to change the
schema; without it the first signal is a rejected registration.

| Level | Accepts a new version that… |
|---|---|
| `BACKWARD` (default) | a consumer of the **previous** version can still read |
| `BACKWARD_TRANSITIVE` | a consumer of **any** earlier version can still read |
| `FORWARD` | the **previous** version's consumer schema can read data written by |
| `FORWARD_TRANSITIVE` | **any** earlier version can read data written by |
| `FULL` / `FULL_TRANSITIVE` | both directions |
| `NONE` | anything |

A per-subject level overrides the global one. Setting it is a real change in
what the registry will accept, not a label: the e2e suite registers a schema
that `BACKWARD` refuses, sets the subject to `NONE`, and registers the same
schema successfully.

## Deleting

Two kinds, and the difference matters:

- **Soft delete** hides the subject or version from normal reads. It is still
  there under `?deleted=true` and can be recovered, and **its version number is
  never reused**.
- **Permanent delete** removes it from the registry's storage. Any producer or
  consumer still resolving those schema ids fails, and there is no recovery.

A permanent delete requires the target to be soft-deleted first; the registry
answers 404 otherwise, which reads as "no such subject". The console does the
soft delete for you when you ask for a permanent one, so the two-step sequence
is not something to remember.

## Walkthrough

1. Install a Kafka cluster, then a Schema Registry pointed at its brokers.
2. Open the registry → **Schemas**.
3. *Register* — subject, type, schema body. **Check compatibility** first; for a
   brand-new subject there is nothing to check against and it says so.
4. *Subjects* — pick one to see its versions. Selecting an older version shows
   that version, which is the point of keeping them.
5. Set **Compatibility** on the subject if its evolution rule differs from the
   cluster default.

## See also

- [Kafka Connect & Topics](kafka-connect.md) — Connect uses this registry for its Avro converters.
- [Component Catalog](../components/catalog.md) — where Schema Registry sits in the stack.
