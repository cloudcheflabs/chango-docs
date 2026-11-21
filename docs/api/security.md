# Security — IAM users, SSO, KMS, STS, license, trust store

Generated from the platform source — see [API overview](index.md) for authentication, errors and the permission model. Every route below is also a `changoctl` command ([CLI](../operations/cli.md)).

| Method | Path | Permission | changoctl |
|---|---|---|---|
| GET | [`/admin/api/sso/settings`](#get-admin-api-sso-settings) | Any signed-in user | `changoctl sso settings get` |
| PUT | [`/admin/api/sso/settings`](#put-admin-api-sso-settings) | Administrator | `changoctl sso settings set -f body.json \| --set K=V` |
| GET | [`/admin/api/sso/saml/metadata`](#get-admin-api-sso-saml-metadata) | Any signed-in user | `changoctl sso saml metadata [-O FILE]` |
| POST | [`/admin/api/sso/saml/idp-metadata`](#post-admin-api-sso-saml-idp-metadata) | Administrator | `changoctl sso saml idp-metadata -f body.json \| --set K=V` |
| POST | [`/admin/api/sso/saml/keypair`](#post-admin-api-sso-saml-keypair) | Administrator | `changoctl sso saml keypair` |
| POST | [`/admin/api/sso/test`](#post-admin-api-sso-test) | Administrator | `changoctl sso test --provider V` |
| GET | [`/admin/api/kms/list`](#get-admin-api-kms-list) | Any signed-in user | `changoctl kms list` |
| GET | [`/admin/api/kms/status/{keyId}`](#get-admin-api-kms-status-keyid) | Any signed-in user | `changoctl kms status KEYID` |
| POST | [`/admin/api/kms/create`](#post-admin-api-kms-create) | Administrator | `changoctl kms create --key-id V` |
| POST | [`/admin/api/kms/rotate/{keyId}`](#post-admin-api-kms-rotate-keyid) | Administrator | `changoctl kms rotate KEYID` |
| GET | [`/admin/api/iam/users`](#get-admin-api-iam-users) | Any signed-in user | `changoctl users list` |
| POST | [`/admin/api/iam/users`](#post-admin-api-iam-users) | Administrator | `changoctl users create` |
| DELETE | [`/admin/api/iam/users/{user}`](#delete-admin-api-iam-users-user) | Administrator | `changoctl users delete USER` |
| POST | [`/admin/api/iam/keys`](#post-admin-api-iam-keys) | Administrator | `changoctl keys create --user V [--expires-at V]` |
| DELETE | [`/admin/api/iam/users/{user}/keys/{keyId}`](#delete-admin-api-iam-users-user-keys-keyid) | Administrator | `changoctl keys delete USER KEYID` |
| GET | [`/admin/api/iam/download-key/{user}/{keyId}`](#get-admin-api-iam-download-key-user-keyid) | Administrator | `changoctl keys download USER KEYID [-O FILE]` |
| GET | [`/admin/api/iam/groups`](#get-admin-api-iam-groups) | Any signed-in user | `changoctl groups list` |
| POST | [`/admin/api/iam/groups`](#post-admin-api-iam-groups) | Administrator | `changoctl groups create --group V` |
| DELETE | [`/admin/api/iam/groups/{group}`](#delete-admin-api-iam-groups-group) | Administrator | `changoctl groups delete GROUP` |
| POST | [`/admin/api/iam/add-user-to-group`](#post-admin-api-iam-add-user-to-group) | Administrator | `changoctl groups add-user --user V --group V` |
| POST | [`/admin/api/iam/remove-user-from-group`](#post-admin-api-iam-remove-user-from-group) | Administrator | `changoctl groups remove-user --user V --group V` |
| POST | [`/admin/api/iam/attach-group-policy`](#post-admin-api-iam-attach-group-policy) | Administrator | `changoctl groups attach-policy --group V --policy V` |
| POST | [`/admin/api/iam/detach-group-policy`](#post-admin-api-iam-detach-group-policy) | Administrator | `changoctl groups detach-policy --group V --policy V` |
| GET | [`/admin/api/iam/policies`](#get-admin-api-iam-policies) | Any signed-in user | `changoctl policies list` |
| POST | [`/admin/api/iam/policies`](#post-admin-api-iam-policies) | Administrator | `changoctl policies create --name V --document V` |
| DELETE | [`/admin/api/iam/policies/{policy}`](#delete-admin-api-iam-policies-policy) | Administrator | `changoctl policies delete POLICY` |
| POST | [`/admin/api/sts/assume-role`](#post-admin-api-sts-assume-role) | Administrator | `changoctl sts assume-role --parent-access-key-id V [--role-session-name V] [--duration-seconds V]` |
| GET | [`/admin/api/sts/sessions`](#get-admin-api-sts-sessions) | Any signed-in user | `changoctl sts sessions list` |
| DELETE | [`/admin/api/sts/sessions`](#delete-admin-api-sts-sessions) | Administrator | `changoctl sts sessions delete --access-key-id V` |
| POST | [`/admin/api/sts/sessions/clear`](#post-admin-api-sts-sessions-clear) | Administrator | `changoctl sts sessions clear` |
| GET | [`/admin/api/sts/sessions/download/{accessKeyId}`](#get-admin-api-sts-sessions-download-accesskeyid) | Any signed-in user | `changoctl sts sessions download ACCESSKEYID [-O FILE]` |
| GET | [`/admin/api/truststore`](#get-admin-api-truststore) | Any signed-in user | `changoctl truststore list` |
| POST | [`/admin/api/truststore`](#post-admin-api-truststore) | Administrator | `changoctl truststore add [--cert V] [--name V] [--from-gateway V]` |
| DELETE | [`/admin/api/truststore`](#delete-admin-api-truststore) | Administrator | `changoctl truststore delete --name V` |
| GET | [`/admin/api/license`](#get-admin-api-license) | Any signed-in user | `changoctl license list` |
| POST | [`/admin/api/license`](#post-admin-api-license) | Administrator | `changoctl license install --token V` |
| DELETE | [`/admin/api/license/{component}`](#delete-admin-api-license-component) | Administrator | `changoctl license delete COMPONENT` |
| GET | [`/admin/api/retired-keys`](#get-admin-api-retired-keys) | Any signed-in user | `changoctl retired-keys list [--component-type V]` |
| DELETE | [`/admin/api/retired-keys/{clusterId}`](#delete-admin-api-retired-keys-clusterid) | Administrator | `changoctl retired-keys purge CLUSTERID` |

## GET `/admin/api/sso/settings` { #get-admin-api-sso-settings }

- **Permission:** Any signed-in user
- **CLI:** `changoctl sso settings get`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/sso/settings" -H "Authorization: Bearer $T"
```

## PUT `/admin/api/sso/settings` { #put-admin-api-sso-settings }

- **Permission:** Administrator
- **CLI:** `changoctl sso settings set -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X PUT "https://node-1.example.com:8080/admin/api/sso/settings" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## GET `/admin/api/sso/saml/metadata` { #get-admin-api-sso-saml-metadata }

- **Permission:** Any signed-in user
- **CLI:** `changoctl sso saml metadata [-O FILE]`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/sso/saml/metadata" -H "Authorization: Bearer $T"
```

## POST `/admin/api/sso/saml/idp-metadata` { #post-admin-api-sso-saml-idp-metadata }

- **Permission:** Administrator
- **CLI:** `changoctl sso saml idp-metadata -f body.json | --set K=V`

**Body:** JSON object (see the handler; `changoctl … -f body.json`).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/sso/saml/idp-metadata" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d @body.json
```

## POST `/admin/api/sso/saml/keypair` { #post-admin-api-sso-saml-keypair }

- **Permission:** Administrator
- **CLI:** `changoctl sso saml keypair`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/sso/saml/keypair" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## POST `/admin/api/sso/test` { #post-admin-api-sso-test }

- **Permission:** Administrator
- **CLI:** `changoctl sso test --provider V`

**Body (JSON):**

| Field | Type |
|---|---|
| `provider` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/sso/test" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"provider": "<value>"}'
```

## GET `/admin/api/kms/list` { #get-admin-api-kms-list }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kms list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kms/list" -H "Authorization: Bearer $T"
```

## GET `/admin/api/kms/status/{keyId}` { #get-admin-api-kms-status-keyid }

- **Permission:** Any signed-in user
- **CLI:** `changoctl kms status KEYID`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/kms/status/<keyId>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/kms/create` { #post-admin-api-kms-create }

- **Permission:** Administrator
- **CLI:** `changoctl kms create --key-id V`

**Body (JSON):**

| Field | Type |
|---|---|
| `keyId` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kms/create" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"keyId": "<value>"}'
```

## POST `/admin/api/kms/rotate/{keyId}` { #post-admin-api-kms-rotate-keyid }

- **Permission:** Administrator
- **CLI:** `changoctl kms rotate KEYID`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/kms/rotate/<keyId>" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## GET `/admin/api/iam/users` { #get-admin-api-iam-users }

- **Permission:** Any signed-in user
- **CLI:** `changoctl users list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/iam/users" -H "Authorization: Bearer $T"
```

## POST `/admin/api/iam/users` { #post-admin-api-iam-users }

- **Permission:** Administrator
- **CLI:** `changoctl users create`

**Body (JSON):**

| Field | Type | Description |
|---|---|---|
| `username` | string |  |
| `password` | string | initial password |
| `groups` | list | optional |
| `policyNames` | list | optional |
| `attributes` | map | optional |
| `userId` | string | optional |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/users" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"username": "<value>", "password": "<value>"}'
```

## DELETE `/admin/api/iam/users/{user}` { #delete-admin-api-iam-users-user }

- **Permission:** Administrator
- **CLI:** `changoctl users delete USER`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/iam/users/<user>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/iam/keys` { #post-admin-api-iam-keys }

- **Permission:** Administrator
- **CLI:** `changoctl keys create --user V [--expires-at V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `user` | string |
| `expiresAt` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/keys" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"user": "<value>", "expiresAt": "<value>"}'
```

## DELETE `/admin/api/iam/users/{user}/keys/{keyId}` { #delete-admin-api-iam-users-user-keys-keyid }

- **Permission:** Administrator
- **CLI:** `changoctl keys delete USER KEYID`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/iam/users/<user>/keys/<keyId>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/iam/download-key/{user}/{keyId}` { #get-admin-api-iam-download-key-user-keyid }

- **Permission:** Administrator
- **CLI:** `changoctl keys download USER KEYID [-O FILE]`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/iam/download-key/<user>/<keyId>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/iam/groups` { #get-admin-api-iam-groups }

- **Permission:** Any signed-in user
- **CLI:** `changoctl groups list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/iam/groups" -H "Authorization: Bearer $T"
```

## POST `/admin/api/iam/groups` { #post-admin-api-iam-groups }

- **Permission:** Administrator
- **CLI:** `changoctl groups create --group V`

**Body (JSON):**

| Field | Type |
|---|---|
| `group` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/groups" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"group": "<value>"}'
```

## DELETE `/admin/api/iam/groups/{group}` { #delete-admin-api-iam-groups-group }

- **Permission:** Administrator
- **CLI:** `changoctl groups delete GROUP`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/iam/groups/<group>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/iam/add-user-to-group` { #post-admin-api-iam-add-user-to-group }

- **Permission:** Administrator
- **CLI:** `changoctl groups add-user --user V --group V`

**Body (JSON):**

| Field | Type |
|---|---|
| `user` | string |
| `group` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/add-user-to-group" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"user": "<value>", "group": "<value>"}'
```

## POST `/admin/api/iam/remove-user-from-group` { #post-admin-api-iam-remove-user-from-group }

- **Permission:** Administrator
- **CLI:** `changoctl groups remove-user --user V --group V`

**Body (JSON):**

| Field | Type |
|---|---|
| `user` | string |
| `group` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/remove-user-from-group" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"user": "<value>", "group": "<value>"}'
```

## POST `/admin/api/iam/attach-group-policy` { #post-admin-api-iam-attach-group-policy }

- **Permission:** Administrator
- **CLI:** `changoctl groups attach-policy --group V --policy V`

**Body (JSON):**

| Field | Type |
|---|---|
| `group` | string |
| `policy` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/attach-group-policy" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"group": "<value>", "policy": "<value>"}'
```

## POST `/admin/api/iam/detach-group-policy` { #post-admin-api-iam-detach-group-policy }

- **Permission:** Administrator
- **CLI:** `changoctl groups detach-policy --group V --policy V`

**Body (JSON):**

| Field | Type |
|---|---|
| `group` | string |
| `policy` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/detach-group-policy" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"group": "<value>", "policy": "<value>"}'
```

## GET `/admin/api/iam/policies` { #get-admin-api-iam-policies }

- **Permission:** Any signed-in user
- **CLI:** `changoctl policies list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/iam/policies" -H "Authorization: Bearer $T"
```

## POST `/admin/api/iam/policies` { #post-admin-api-iam-policies }

- **Permission:** Administrator
- **CLI:** `changoctl policies create --name V --document V`

**Body (JSON):**

| Field | Type |
|---|---|
| `name` | string |
| `document` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/iam/policies" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"name": "<value>", "document": "<value>"}'
```

## DELETE `/admin/api/iam/policies/{policy}` { #delete-admin-api-iam-policies-policy }

- **Permission:** Administrator
- **CLI:** `changoctl policies delete POLICY`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/iam/policies/<policy>" -H "Authorization: Bearer $T"
```

## POST `/admin/api/sts/assume-role` { #post-admin-api-sts-assume-role }

- **Permission:** Administrator
- **CLI:** `changoctl sts assume-role --parent-access-key-id V [--role-session-name V] [--duration-seconds V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `parentAccessKeyId` | string |
| `roleSessionName` | string |
| `durationSeconds` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/sts/assume-role" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"parentAccessKeyId": "<value>", "roleSessionName": "<value>", "durationSeconds": "<value>"}'
```

## GET `/admin/api/sts/sessions` { #get-admin-api-sts-sessions }

- **Permission:** Any signed-in user
- **CLI:** `changoctl sts sessions list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/sts/sessions" -H "Authorization: Bearer $T"
```

## DELETE `/admin/api/sts/sessions` { #delete-admin-api-sts-sessions }

- **Permission:** Administrator
- **CLI:** `changoctl sts sessions delete --access-key-id V`

**Body (JSON):**

| Field | Type |
|---|---|
| `accessKeyId` | string |

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/sts/sessions" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"accessKeyId": "<value>"}'
```

## POST `/admin/api/sts/sessions/clear` { #post-admin-api-sts-sessions-clear }

- **Permission:** Administrator
- **CLI:** `changoctl sts sessions clear`

**Body:** `{}` (empty object).

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/sts/sessions/clear" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d {}
```

## GET `/admin/api/sts/sessions/download/{accessKeyId}` { #get-admin-api-sts-sessions-download-accesskeyid }

- **Permission:** Any signed-in user
- **CLI:** `changoctl sts sessions download ACCESSKEYID [-O FILE]`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/sts/sessions/download/<accessKeyId>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/truststore` { #get-admin-api-truststore }

- **Permission:** Any signed-in user
- **CLI:** `changoctl truststore list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/truststore" -H "Authorization: Bearer $T"
```

## POST `/admin/api/truststore` { #post-admin-api-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl truststore add [--cert V] [--name V] [--from-gateway V]`

**Body (JSON):**

| Field | Type |
|---|---|
| `cert` | string |
| `name` | string |
| `fromGateway` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/truststore" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"cert": "<value>", "name": "<value>", "fromGateway": "<value>"}'
```

## DELETE `/admin/api/truststore` { #delete-admin-api-truststore }

- **Permission:** Administrator
- **CLI:** `changoctl truststore delete --name V`

**Query parameters:** `name`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/truststore?name=<value>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/license` { #get-admin-api-license }

- **Permission:** Any signed-in user
- **CLI:** `changoctl license list`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/license" -H "Authorization: Bearer $T"
```

## POST `/admin/api/license` { #post-admin-api-license }

- **Permission:** Administrator
- **CLI:** `changoctl license install --token V`

**Body (JSON):**

| Field | Type |
|---|---|
| `token` | string |

```bash
curl -s -X POST "https://node-1.example.com:8080/admin/api/license" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"token": "<value>"}'
```

## DELETE `/admin/api/license/{component}` { #delete-admin-api-license-component }

- **Permission:** Administrator
- **CLI:** `changoctl license delete COMPONENT`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/license/<component>" -H "Authorization: Bearer $T"
```

## GET `/admin/api/retired-keys` { #get-admin-api-retired-keys }

- **Permission:** Any signed-in user
- **CLI:** `changoctl retired-keys list [--component-type V]`

**Query parameters:** `componentType`

```bash
curl -s -X GET "https://node-1.example.com:8080/admin/api/retired-keys?componentType=<value>" -H "Authorization: Bearer $T"
```

## DELETE `/admin/api/retired-keys/{clusterId}` { #delete-admin-api-retired-keys-clusterid }

- **Permission:** Administrator
- **CLI:** `changoctl retired-keys purge CLUSTERID`

```bash
curl -s -X DELETE "https://node-1.example.com:8080/admin/api/retired-keys/<clusterId>" -H "Authorization: Bearer $T"
```
