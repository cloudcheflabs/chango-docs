# Admin Password Recovery

Chango ships with a built-in recovery channel that lets an operator reset the
`admin` user's password **without stopping the master**, even when no one
remembers the current password.

Recovery uses a local Unix domain socket — there is no HTTP back-door, no
network endpoint, no recovery URL. Authentication is performed by the
operating system: only a process that already shares the master's filesystem
identity can open the socket.

## When to use

- The admin password was forgotten or rotated out of the password manager.
- An automation script needs to provision a known admin password during
  first-time setup, without going through the web UI.
- A new operator is onboarded and you need to hand them an admin credential.

For day-to-day password changes (the user remembers the old password and
wants a new one), use the Admin UI's **Change Password** screen instead —
that path requires the old password and does not flag the user for forced
rotation.

## How it works

```
┌────────────────────┐   JSON over UDS    ┌────────────────────┐
│  chango-cli        │ ─────────────────▶ │  Master (running)  │
│  iam:reset-password│                    │   AuthManager      │
└────────────────────┘                    │   .adminResetPwd() │
         ▲                                │                    │
         │ stdout: new password           │  saveToDb()        │
         │ (one-time)                     │  cluster sync push │
                                          │  audit log append  │
                                          └────────────────────┘
```

| Property | Value |
|---|---|
| **Socket path** | `data/admin.sock` (mode `600`) |
| **Authentication** | OS file permission — same user as the master process |
| **Network surface** | none — Unix domain socket only |
| **Downtime** | none — applied in-process on the live master |
| **Cluster sync** | automatic — leader pushes the new IAM snapshot to follower masters and node managers |
| **Audit log** | `data/iam-audit/reset.log` (mode `600`, append-only) |
| **Post-reset state** | `requirePasswordChange = true` (forced rotation on next login) |

## Quick start

The simplest invocation lets the master generate a strong 20-character
password and print it to stdout. The new password must be changed on the
admin's next login (the `requirePasswordChange` flag is set automatically).

```bash
# Inside the master host or container:
bin/chango-cli.sh iam:reset-password
```

Sample output (TTY):

```
  ┌────────────────────────────────────────────────────────────┐
  │  Password reset for user: admin                            │
  │                                                            │
  │  New temporary password: K3p9WvTx7qLm8zXa#-Bd              │
  │                                                            │
  │  Must be changed on next login (requirePasswordChange).    │
  └────────────────────────────────────────────────────────────┘
```

## Input modes

| Mode | Command | When to use |
|---|---|---|
| **Master-generated** | `chango-cli.sh iam:reset-password` | Default. Strong random password printed once on stdout. |
| **Explicit** | `chango-cli.sh iam:reset-password --new-password 'My!Pass'` | Automation that knows the desired value. Beware: argv may show up in `ps`. |
| **Stdin** | `echo 'My!Pass' \| chango-cli.sh iam:reset-password --new-password -` | Automation that wants to avoid argv exposure. |
| **Interactive** | `chango-cli.sh iam:reset-password --interactive` | Operator at a TTY. Prompts for password twice with no echo. |

Resetting a different user is also supported:

```bash
bin/chango-cli.sh iam:reset-password --user some-user --new-password 'NewPass123'
```

## Configuration

The recovery socket is enabled by default. To disable it (for example, in a
hardened production deployment), set:

```properties
# conf/chango.properties
chango.admin.socket.enabled = false
chango.admin.socket.path    = ${chango.base.data.dir}/admin.sock
chango.iam.audit.dir        = ${chango.base.data.dir}/iam-audit
```

The CLI resolves the socket path in this order:

1. `--socket /path/to/admin.sock` command-line flag
2. `CHANGO_ADMIN_SOCKET` environment variable
3. `chango.admin.socket.path` in `conf/chango.properties`
4. `<chango.base.data.dir>/admin.sock` (the default that matches the master)

## Security model

**1. The socket is OS-gated.**
At startup the master creates `data/admin.sock` with mode `600` (owner
read/write only). Even other unprivileged users on the same host cannot
connect. There is no token, no shared secret, no network listener.

**2. The audit log records every reset.**
Every successful reset appends a JSON line to `data/iam-audit/reset.log`
(mode `600`). The plaintext password is **never** logged — only the first
8 characters of its hash, the user, whether it was master-generated, and
the OS user that invoked the CLI.

```json
{"ts":"2026-05-23T16:00:46.922Z","event":"iam.reset-password","user":"admin","generated":true,"hashFp":"OYV/Ojf/","invokedAs":"root"}
```

**3. The new password is exposed exactly once.**
For master-generated passwords, the plaintext is returned only on the
single CLI invocation that triggered the reset. It is not written to the
audit log, not stored in RocksDB, and not retransmitted. Treat scrollback
and shell history accordingly — or use stdin input mode to avoid argv
exposure entirely.

**4. Forced rotation on next login.**
After reset, the user is flagged `requirePasswordChange = true`. The next
successful login forces the user through the change-password flow, so a
temporary password used by the operator is immediately replaced by a
password only the user knows.

**5. The master must be running.**
Because the recovery channel is in-process, the master must be alive for
the CLI to connect. This is intentional: RocksDB requires an exclusive
lock, so an offline edit would either conflict with a running master or
need a complex stale-lock recovery. With this design, the only way to
reset is to be on the host *and* have the master running *and* share its
filesystem identity.

## Limitations

- **Master must be running.** If the master is down (e.g. KMS unseal
  failure during boot), this CLI cannot help. The recovery path in that
  case is to inspect the boot failure, fix the underlying issue, and let
  the master come up — then run the CLI.
- **No knowledge factor.** Any process that shares the master's filesystem
  identity can invoke the CLI. In multi-tenant or shared-shell
  environments, restrict shell access to the master accordingly. A future
  enhancement may add an opt-in "recovery key" requirement for an
  additional knowledge factor.

## Related

- [Identity & Access Management](iam.md) — users, groups, policies
- [Encryption & Key Management](kms.md) — how IAM is encrypted at rest
