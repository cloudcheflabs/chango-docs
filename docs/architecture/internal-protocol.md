# Internal Protocol

Chango's masters and node managers talk over a custom binary protocol on TCP. The protocol is small, length-framed, KMS-envelope-encrypted in flight, and serves a single purpose — let the master ship `ComponentInstance` lifecycle commands to NMs and pull metrics / log tails back.

## Why not gRPC / HTTP

- The admin UI surface is HTTP — chango already serves HTTP on the admin port. The internal protocol is between **chango processes**, not between a client and chango.
- Component install streams large tarballs (4 GB+). A binary length-prefixed protocol with chunked frames was simpler than HTTP/2 over TLS, especially under air-gapped operation where TLS certificate provisioning is its own problem.
- The same protocol carries KMS envelope encryption end-to-end, so the cluster works without TLS on the wire.

## Wire format

```
+---------+------+----------------+----------+
| length  | code | correlation id | payload  |
| 4 bytes | 2 B  | 8 B            | length-12|
+---------+------+----------------+----------+
```

- `length` — total frame length in bytes, big-endian.
- `code` — `OpCode` (see below).
- `correlation id` — opaque request / response pairing; the responder echoes the request's id so the caller can match.
- `payload` — opcode-specific. If KMS-envelope encryption is enabled (`chango.kms.internal.protocol.encrypt = true`, default), the payload is `{ wrappedDek || iv || ciphertext || gcmTag }`. The wrappedDek is unwrapped by the receiver using the KMS provider, the ciphertext is AES-256-GCM with the unwrapped DEK.

## Opcodes

The opcode set is small. The ones that matter most:

| OpCode | Direction | Purpose |
|---|---|---|
| `PING` (1) | Either | Keepalive |
| `MASTER_LEADER_GET` (2) | NM → master | Ask any master for the leader's address |
| `KMS_SYNC_PUSH` (10) | Leader → follower / NM | Push the latest KMS state |
| `IAM_SYNC_PUSH` (11) | Leader → follower / NM | Push the latest IAM state |
| `METADATA_SYNC_PUSH` (12) | Leader → follower | Push the latest component-inventory state |
| `KMS_SYNC_PULL_REQ` (20) | Follower / NM → leader | Pull current KMS snapshot |
| `IAM_SYNC_PULL_REQ` (21) | Follower / NM → leader | Pull current IAM snapshot |
| `METADATA_SYNC_PULL_REQ` (22) | Follower → leader | Pull current metadata snapshot |
| `COMPONENT_INSTALL_BEGIN` (213) | Master → NM | Install header — instanceId, install path, run-as, start / stop commands, env, config files, binary artifacts |
| `COMPONENT_INSTALL_DATA` (214) | Master → NM | One chunk of the install tarball payload |
| `COMPONENT_INSTALL_END` (215) | Master → NM | Finish + verify hash |
| `COMPONENT_INSTALL_RES` (201) | NM → master | Install result (status, install path, pid file, runtime pid if known) |
| `COMPONENT_START` (202) | Master → NM | Start instance |
| `COMPONENT_STOP` (203) | Master → NM | Stop instance |
| `COMPONENT_RESTART` (204) | Master → NM | Restart instance |
| `COMPONENT_DELETE` (205) | Master → NM | Delete instance + remove install dir |
| `COMPONENT_STATUS_REQ` (206) | Master → NM | Pull instance status + pid |
| `COMPONENT_METRICS_REQ` (208) | Master → NM | Pull CPU / memory sample for one instance |
| `LOG_TAIL_REQ` | Master → NM | Stream the last N lines of an instance log |
| `COMPONENT_CONFIG_PUT` (212) | Master → NM | Update an instance's launch fields (startCommand, stopCommand, pidFile, env, config) without reinstalling |
| `COMPONENT_FILE_GET` / `_PUT` / `_DELETE` | Master ↔ NM | Read / write / delete a config file inside the instance's install dir (for the admin UI's Configure panels) |
| `NGINX_APPLY` / `NGINX_APPLY_MULTI` / `NGINX_STATUS` | Master → NM | Apply / inspect the component-nginx config on the NM's host |

The full enum lives in `chango-protocol/src/main/java/.../OpCode.java`.

## Streaming installs

For a 4 GB component tarball the protocol does not buffer the whole payload in memory. The master issues:

1. `COMPONENT_INSTALL_BEGIN` — header (instanceId, install path, run-as, the start / stop scripts, env, and the *list of files* the NM should extract).
2. Many `COMPONENT_INSTALL_DATA` chunks, each `chango.master.component.transfer.chunk.bytes` long (default 4 MB), in order.
3. `COMPONENT_INSTALL_END` — final SHA-256 check; the NM verifies the assembled tarball matches before extraction.

The NM writes each chunk straight to a temp file on its `/opt` volume so the master never needs to hold the bytes in memory either.

## Correlation, retries, timeouts

- The master assigns a monotonically increasing 64-bit correlation id per request. The NM echoes the id on every response and every install chunk's ack.
- A single operation has a timeout (`chango.master.component.op.timeout.ms`, default 120 000). If the NM does not ack within that window the master gives up and returns an error to the admin REST caller.
- Long-running ops (install of a multi-GB tarball, slow cluster start) use a longer per-operation timeout configured per provisioner.

## KMS envelope on the wire

When `chango.kms.internal.protocol.encrypt = true` (default), every `InternalMessage` payload is AES-256-GCM:

1. Sender requests a wrapped DEK from chango's KMS provider for the wire key (`internal-protocol`).
2. AES-GCM-encrypts the cleartext payload with the unwrapped DEK and a fresh 96-bit IV.
3. Frames the wire payload as `wrappedDek || iv || ciphertext || gcmTag`.
4. Receiver unwraps the DEK and decrypts.

A wrong key (the cluster root secret diverged between master and NM, for example) fails to decrypt with `AEADBadTagException`. The NM logs the failure and refuses the message — no plaintext fallback.

## When to disable encryption

`chango.kms.internal.protocol.encrypt = false` exists for **diagnosis only**. It removes the envelope and sends payloads in cleartext, which lets you tcpdump the wire to see what's actually being sent during a slow install. Never run with this disabled in production.

## Sync push + pull cadence

State propagation from leader to followers / NMs is dual:

- **Push** — the leader writes a change locally, then fires `KMS_SYNC_PUSH` / `IAM_SYNC_PUSH` / `METADATA_SYNC_PUSH` to every known peer in parallel.
- **Pull** — every non-leader runs a periodic `*_SYNC_PULL_REQ` against the leader on a fixed interval (`chango.cluster.sync.pull.interval.ms`, default 30 000) to catch any push that was missed (peer was offline, network blip).

This belt-and-suspenders pattern is what keeps the cached state on every NM consistent without requiring at-least-once delivery on the push path.
