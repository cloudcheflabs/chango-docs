# Encryption & Key Management

Chango encrypts every cluster-wide secret at rest and every internal NIO message in flight. The KMS layer is built in — no external KMS service is required to bring chango up — and follows a standard envelope-encryption model so external KMS providers can be plugged in later without changing the on-disk format.

## What is encrypted

| Surface | Encrypted with | Notes |
|---|---|---|
| KMS RocksDB (the keystore) | The whole keystore blob is AES-GCM sealed under a key derived from `$CHANGO_MASTER_KEY` | Holds the versioned KEKs that wrap everything else |
| Metadata RocksDB | Every row is envelope-encrypted under the `metadata-encryption` KEK | Component inventory, per-cluster settings (including managed product master keys), gateway topology, backup S3 credentials |
| IAM RocksDB | Same envelope, under the same KEK path | Users, groups, policies, access keys |
| Internal NIO protocol (master ↔ NM, master ↔ master) | Each `InternalMessage` body is AES-GCM with a DEK wrapped by the `internal-protocol` KEK | `chango.kms.encrypt.internal.protocol = true` by default; `KMS_*` opcodes are exempt because a node fetching the keystore has no key yet |
| Backup archive uploaded to S3 | Contents are already envelope-encrypted; server-side encryption is requested on top when the endpoint supports it | See [Backup & Restore](backup.md) |

Rows in the metadata store are encrypted whole, not field-by-field: opening the RocksDB without the master key yields nothing usable, not "the non-sensitive half".

## Envelope encryption model

Chango uses the standard two-key model, plus a third layer for the root:

- **Data Encryption Key (DEK)** — a fresh AES-256 key per payload (one per message, one per row).
- **Key Encryption Key (KEK)** — wraps DEKs. Each KEK id owns a monotonically-versioned list of versions; the newest ACTIVE version wraps new DEKs while older versions stay decryptable until REVOKED. KEKs live in the KMS RocksDB.
- **Master key** — `$CHANGO_MASTER_KEY`. Seals the keystore that holds the KEKs. Never persisted anywhere by chango.

To encrypt a payload chango generates a DEK, encrypts with it (AES-256-GCM, random 96-bit IV), wraps the DEK under the ACTIVE KEK version, and stores `version ‖ iv ‖ wrappedDek ‖ ciphertext` together. To decrypt it reads the KEK version out of the envelope, resolves that exact version, unwraps the DEK, and decrypts.

Because the envelope names its KEK **version**, rotating a KEK never invalidates existing ciphertext.

A reader that is handed bytes which are **not** an envelope — a plaintext
snapshot written before encryption, for example — must reject them so its
plaintext fallback can take over. The first four bytes are read as the length of
the wrapped DEK, and the four bytes `{"us` of a JSON snapshot read as
2,065,973,619: decryption used to allocate a ~2 GB array from that, raising
`OutOfMemoryError` instead of an exception, which passed every `catch
(Exception)` fallback and killed the process during startup — only on a small
heap, since a large one survived the allocation. The length is now checked
against the bytes that are actually there (leaving room for the IV and tag)
before anything is allocated, and a mismatch is rejected as `not an envelope`.

## Algorithms

| Operation | Algorithm |
|---|---|
| Payload / DEK / KEK cipher | AES-256-GCM, 128-bit tag |
| Random IVs | 96-bit, from `SecureRandom` |
| Master-key derivation | PBKDF2-HMAC-SHA256, `chango.kms.pbkdf2.iterations` (default 200000), 256-bit output, fresh 32-byte salt per save |
| Master-key fingerprint | `SHA-256("chango-master-key-fingerprint:v1:" + key)` truncated to 64 bits |
| Admin JWT signing | HS256, key derived from the master key |

GCM authentication tags guard against tampering: a wrong key or a flipped bit fails with an AEAD tag error rather than returning garbage plaintext.

!!! note "The fingerprint is domain-separated on purpose"
    It is deliberately *not* `SHA-256(masterKey)` — that value is the JWT signing key. The fingerprint uses its own domain prefix so publishing it (in logs, in a backup manifest, in `master-key status`) can never leak a key that is used for anything else.

## Root of trust — the master key

The master key is supplied as an **environment variable** to `bin/start-master.sh` / `bin/start-node-manager.sh` and lives only in process memory. Chango never writes it to disk, and there is no systemd unit or sysconfig file involved — ansible deliberately creates neither.

Ansible stages the key once at first install in `<install_dir>/.master-key-bootstrap` (mode 0600, root) purely so the operator can move it into a secret store and shred the file:

```bash
sudo cat /opt/chango/.master-key-bootstrap     # read once
# → move the value into Vault / AWS Secrets Manager / a password manager
sudo shred -u /opt/chango/.master-key-bootstrap
```

Every master and every node manager must hold the **same** master key. Confirm without revealing it:

```bash
export CHANGO_MASTER_KEY=<from your secret store>
/opt/chango/bin/chango-cli.sh master-key fingerprint     # run on each node, compare
```

If the master key is lost, the keystore — and therefore the metadata and IAM stores and every backup — is mathematically undecryptable. Chango refuses to start rather than re-initialising an unreadable keystore, because silently treating it as empty would let the first leader overwrite it with fresh keys and destroy every existing row:

```
KMS keystore at /opt/chango/data/master/kms exists but cannot be loaded —
no key in this node's keyring opens it. Accepted fingerprints: [a3f91c04d5e6b7c8].
Supply the right key via $CHANGO_MASTER_KEY, or add the retired one to
$CHANGO_MASTER_KEY_PREVIOUS (comma-separated).
```

## The master-key keyring

The KEK layer has always been versioned, but the master key used to be a single unversioned value — exactly one key could open the keystore at any moment. That made rotation impossible, and it meant an archive sealed under an older key could only be opened by giving up access to the live one.

The keyring fixes both:

| Env var | Role |
|---|---|
| `$CHANGO_MASTER_KEY` | **ACTIVE** — everything is written under this key |
| `$CHANGO_MASTER_KEY_PREVIOUS` | Zero or more retired keys, comma-separated, accepted for **reading only** |

The env var name for retired keys is configurable via `chango.kms.master.key.previous.env` if your secret delivery names it differently.

Sealed payloads carry a self-describing header — `CKMS` magic, a version byte, and the master-key fingerprint — so the right keyring entry is chosen directly instead of by trial, and so tooling can report *which key an archive needs before a restore is attempted*.

!!! tip "Upgrading from an earlier release needs no migration"
    Keystores written before the keyring existed have no header. They are still opened by trying each keyring entry in turn, and they gain the header the next time they are saved. Nothing has to be re-encrypted, and a downgrade window is not required.

### Inspecting keyring state

```bash
$ /opt/chango/bin/chango-cli.sh master-key status
active master key      : 251b8c532ce30e9b
keystore sealed under  : ea65f9199a78782a
accepted for reading   : 251b8c532ce30e9b, ea65f9199a78782a
rewrap needed          : YES
```

Every value is a non-secret fingerprint. `rewrap needed: YES` means the keystore is still sealed under a key that is no longer ACTIVE — i.e. a rotation is staged but not finished.

## Rotating the master key

Because only the keystore blob is master-key wrapped, rotation re-seals exactly one blob. KEKs and every row they protect are untouched, so there is no bulk re-encryption and no downtime window proportional to your data size.

The blob is also the `KMS_SYNC_PUSH` payload, so a leader-side rewrap propagates to followers and node managers over the existing sync path — there is no separate rotation opcode.

```bash
# 1. Generate the new key
NEW=$(/opt/chango/bin/chango-cli.sh master-key generate)

# 2. Restart EVERY master and node manager with the new key ACTIVE and the
#    outgoing key still accepted. This is safe: the keystore is still sealed
#    under the old key at this point and opens via the PREVIOUS entry.
export CHANGO_MASTER_KEY=$NEW
export CHANGO_MASTER_KEY_PREVIOUS=<outgoing key>
sudo -u chango -E /opt/chango/bin/start-master.sh \
    -Dchango.zk.serverList=host1:2181,host2:2181,host3:2181 -Dchango.zk.rootPath=/chango
sudo -u chango -E /opt/chango/bin/start-node-manager.sh \
    -Dchango.zk.serverList=host1:2181,host2:2181,host3:2181 -Dchango.zk.rootPath=/chango

# 3. On the LEADER, re-seal the keystore
/opt/chango/bin/chango-cli.sh master-key rotate
#   keystore re-sealed: ea65f9199a78782a → 251b8c532ce30e9b

# 4. Confirm on every node
/opt/chango/bin/chango-cli.sh master-key status     # rewrap needed: no

# 5. Only then drop CHANGO_MASTER_KEY_PREVIOUS from the start environment
```

A few properties of this flow worth knowing:

- **Order is enforced, not assumed.** `rotate` compares the key in your shell against the master's ACTIVE key and refuses if they differ, because a JVM picks up its environment at launch — editing the env without restarting changes nothing.
- **Leader only.** `rotate` is refused on a follower: a follower's local write neither replicates nor survives the next leader snapshot, so it would report success and change nothing.
- **`rotate` refuses an empty keystore**, so a keystore that failed to open can never be replaced by a blank one.
- **Keep the retired key.** Backups taken before the rotation are still sealed under it. `chango-cli backup inspect` reports which fingerprint a given archive needs; see [Backup & Restore](backup.md#which-key-does-this-archive-need).

## Rotating a KEK

Independent of the master key, an individual KEK can be rotated. Existing ciphertext keeps naming the older version and stays readable:

```bash
curl -X POST -H "Authorization: Bearer $TOK" $BASE/admin/api/kms/rotate/metadata-encryption
```

## REST surface

| Endpoint | Purpose |
|---|---|
| `GET  /admin/api/kms/list` | List KEK ids with current version, version count, last rotation |
| `GET  /admin/api/kms/status/{keyId}` | Version metadata for one KEK — version numbers, states, creation times |
| `POST /admin/api/kms/create` | Create a KEK (normally driven by a component install) |
| `POST /admin/api/kms/rotate/{keyId}` | Bump a KEK to a new ACTIVE version |

Mutating routes are leader-only. **Encrypt / decrypt are not exposed over REST** — wrapping is done in-process on behalf of components, and the wrapped DEKs are persisted into the component's own metadata by the master.

Key material — raw KEKs, raw master keys — is never returned by any REST route. The one way to read a managed product's master key is the local admin socket, which requires OS-level access *and* proof of the chango master key; see [Product master keys](product-master-keys.md).

## State location

| Path (default) | Config key | Contents |
|---|---|---|
| `<base.data.dir>/master/kms` | `chango.master.kms.rocksdb.path` | The master's keystore |
| `<base.data.dir>/nm/kms` | `chango.nm.kms.rocksdb.path` | A node manager's local keystore copy |

With the packaged default `chango.base.data.dir = ./data` and an install at `/opt/chango`, the master keystore is `/opt/chango/data/master/kms`.

Master and NM use separate sub-trees deliberately: the two processes are co-located on most hosts and would otherwise fight over the same RocksDB `LOCK`.

Both are included in the [backup artifact](backup.md).

## What is NOT in chango's KMS

- **Application data at rest** — the data plane's concern. ShannonStore, NeoRunBase and Iceberg-on-S3 each manage their own at-rest encryption, mostly under *their own* master keys, which chango stores for them (see [Product master keys](product-master-keys.md)).
- **TLS** — the NIO protocol does AES-GCM at the message layer rather than wrapping the socket. Terminate TLS for the admin HTTP surface at the ingress (UI Proxy or a customer-supplied reverse proxy).
