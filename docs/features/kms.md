# Encryption & Key Management

Chango encrypts every cluster-wide secret at rest and every internal NIO message in flight. The KMS layer is built in — no external KMS service is required to bring chango up — and follows a standard envelope-encryption model so external KMS providers can be plugged in later without changing the on-disk format.

## What is encrypted

| Surface | Encrypted with | Notes |
|---|---|---|
| KMS RocksDB | DEKs are envelope-wrapped by a cluster master DEK | Stores per-component KEKs / per-shard DEKs that other components ask chango to wrap on their behalf |
| Component metadata RocksDB | Sensitive fields (component master keys, service tokens, S3 credentials in cluster settings) are field-level envelope-encrypted | Non-sensitive fields (cluster id, instance id, ports) are plain |
| Internal NIO protocol (master ↔ NM, master ↔ master) | Each `InternalMessage` body is AES-GCM with a DEK that itself is KMS-wrapped | Default `chango.kms.internal.protocol.encrypt = true`; can be disabled per cluster for diagnosis only |
| Backup tarball uploaded to S3 | Contents are already KMS-envelope-encrypted; S3 SSE-AES256 is requested as a second layer | See [Backup & Restore](backup.md) |

## Envelope encryption model

Chango uses the standard two-key model:

- **Data Encryption Key (DEK)** — randomly generated AES-256 key, used to encrypt a specific payload (one per message, one per shard, one per backup tarball).
- **Key Encryption Key (KEK)** — wraps DEKs. Stored in chango's KMS RocksDB.
- **Cluster master DEK** — wraps KEKs. Derived from a cluster-wide root secret that the operator owns and supplies at startup.

To encrypt a payload, chango:

1. Generates a fresh DEK.
2. Encrypts the payload with the DEK (AES-256-GCM, random IV, no AAD reuse).
3. Wraps the DEK with the appropriate KEK.
4. Stores the wrapped DEK alongside the ciphertext.

To decrypt:

1. Read the wrapped DEK from the envelope.
2. Unwrap it with the KEK (which itself is unwrapped by the cluster master DEK).
3. Decrypt the payload with the DEK.

KEKs live in RocksDB; DEKs are ephemeral per-payload. The root secret is held only in memory after startup — see "Root of trust" below.

## Algorithms

| Operation | Algorithm |
|---|---|
| DEK / KEK content cipher | AES-256-GCM |
| Random nonces / IVs | 96-bit, from `SecureRandom` |
| Root-secret-derived master DEK | PBKDF2-HMAC-SHA256, default `chango.kms.pbkdf2.iterations = 200000` |
| MAC over backup payloads | HMAC-SHA256 |
| Authn JWTs (admin UI) | HS256, signing key derived from the same cluster master DEK |

GCM authentication tags guard against tampering; a wrong key or a flipped bit fails to decrypt with `AEADBadTagException` rather than returning garbage plaintext.

## Root of trust

Chango's KMS layer derives its cluster master DEK from a cluster-wide root secret that the operator owns. The operator is responsible for:

- Supplying that secret at chango startup (it is held only in process memory after that).
- Storing it out-of-band somewhere that survives the failure mode the backup is meant to protect against (a real secret manager, a Shamir-share split, etc).
- Re-supplying it at restore time on a fresh master node so the backed-up RocksDB contents can be decrypted.

Chango does not embed the root secret in any of its persisted artifacts — neither in the RocksDB files nor in the backup tarball. If you lose the root secret, the backup is mathematically undecryptable.

## What is NOT in chango's KMS

- **Application data at rest** — that's the data plane's concern. ShannonStore, NeoRunBase, Iceberg-on-S3 each manage their own at-rest encryption, sometimes wrapping their own DEKs through chango's KMS API (which is what the per-shard / per-segment wrapping is for).
- **TLS** — chango's NIO protocol does its own AES-GCM at the message layer rather than wrapping the socket in TLS. Operators who want TLS on the admin HTTP layer should terminate it at the ingress (UI Proxy or a customer-supplied reverse proxy).

## REST surface

| Endpoint | Purpose |
|---|---|
| `GET  /admin/api/kms/keys` | List KEK ids managed by chango |
| `POST /admin/api/kms/keys` | Create a new KEK (typically driven by a component install) |
| `POST /admin/api/kms/encrypt` | Wrap a DEK against a named KEK |
| `POST /admin/api/kms/decrypt` | Unwrap a previously-wrapped DEK |

Mutating routes are leader-only. Components rarely call these directly — the chango master sits in front and persists the wrapped DEKs back into the component's own metadata for them.

## State location

- `/var/lib/chango/kms/` — KMS RocksDB (`chango.kms.rocksdb.path`).
- KEKs are stored already-wrapped under the cluster master DEK; opening the RocksDB without the root secret yields no usable key material.
- The KMS RocksDB is included in the [Backup & Restore](backup.md) artifact.
