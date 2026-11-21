#!/usr/bin/env python3
"""Generates docs/api/<area>.md from the platform source tree.

  python3 tools/gen_api_reference.py <chango repo>

Sources (nothing is typed by hand):
  - route table   : `java -jar <repo>/chango-ctl/build/libs/changoctl.jar routes --markdown`
                    (METHOD, PATH, body class — transcribed from AdminHttpServer / AdminApiHandler)
  - body fields   : <repo>/chango-ctl/build/generated/fieldcatalog/changoctl/fields.json
                    (every field of each *Request class, its type, default and javadoc,
                    read with the server's own Jackson mapper at build time)
  - permissions   : AdminApiHandler.isPublic / adminRequired, mirrored below
Each route's literal path segments are also searched for in the master sources; a
segment that is not found is printed so the table can be corrected before publishing.
"""
import json, os, re, subprocess, sys

REPO = os.path.abspath(sys.argv[1])
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "api")
HOST = "https://node-1.example.com:8080"

routes_md = subprocess.run(["java", "-jar", os.path.join(REPO, "chango-ctl/build/libs/changoctl.jar"),
                            "routes", "--markdown"], capture_output=True, text=True, check=True).stdout
catalog = json.load(open(os.path.join(REPO, "chango-ctl/build/generated/fieldcatalog/changoctl/fields.json")))["classes"]

rows = []
for line in routes_md.splitlines()[2:]:
    if not line.startswith("|"):
        continue
    cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
    if len(cells) != 4:
        continue
    cmd, method, path, body = cells
    rows.append({"cmd": cmd.strip("`").replace("\\|", "|"), "method": method,
                 "path": path.strip("`"), "body": body})

API = "/admin/api/"


def rest_of(path):
    return path[len(API):] if path.startswith(API) else None


def permission(method, path):
    """Mirrors AdminApiHandler.isPublic + adminRequired (the server's authoritative gate)."""
    if not path.startswith(API):
        return "Public"
    rest = rest_of(path)
    if rest in ("auth/login", "auth/refresh") or rest.startswith("auth/sso/"):
        return "Public"
    mutating = method != "GET"
    reveals = (rest.startswith("iam/download-key/") or rest.endswith("/admin-password")
               or rest.endswith("/password") or rest.endswith("/catalog-config")
               or rest.endswith("/catalog-connection") or rest.startswith("credentials/download")
               or rest.endswith("/credentials"))
    if (mutating or reveals) and not rest.startswith("auth/"):
        return "Administrator"
    return "Any signed-in user" if not rest.startswith("auth/") else "Signed-in user (self)"


def area(path):
    rest = rest_of(path)
    if rest is None:
        return "control-plane"
    head = rest.split("/")[0].split("?")[0]
    groups = {
        "auth": "control-plane", "nodes": "control-plane", "monitoring": "control-plane",
        "clusters": "shannonstore", "components": "components", "credentials": "control-plane",
        "iam": "security", "sso": "security", "kms": "security", "sts": "security",
        "license": "security", "retired-keys": "security", "truststore": "security",
        "patch": "patch-backup", "backup": "patch-backup", "gateway": "trino-gateway",
    }
    return groups.get(head, head)


TITLES = {
    "control-plane": "Control Plane — health, cluster, auth, nodes, metrics",
    "components": "Component instances (all types)",
    "security": "Security — IAM users, SSO, KMS, STS, license, trust store",
    "patch-backup": "Patches & Backup",
    "postgres": "PostgreSQL", "polaris": "Polaris (catalog server)", "ontul": "Ontul (IAM engine)",
    "trino": "Trino (query engine)", "trino-gateway": "Trino Gateway", "spark": "Spark (+ Livy)",
    "flink": "Flink", "kafka": "Kafka (+ Connect, topics)", "schema-registry": "Schema Registry",
    "kiok": "Kiok (workflow)", "ui-proxy": "UI Proxy", "mium": "Mium", "neorunbase": "NeoRunBase",
    "itdastream": "ItdaStream", "shannonstore": "ShannonStore",
}


AREA_NOTES = {
    "kafka": ["!!! note \"Kafka Connect pass-through\"",
              "    `/admin/api/kafka/{id}/connect/connectors…` is forwarded verbatim to the Kafka Connect REST",
              "    API of that cluster (`/connectors…`, query string included), so `pause`, `resume`, `restart`,",
              "    `status` and `config` behave exactly as Kafka Connect documents them.", ""],
    "polaris": ["!!! note \"Ontul authorization and catalog S3 keys\"",
                "    - `POST /admin/api/polaris/{id}/config` with `ontulAuthzOp` = `enable` | `update` | `disable` turns",
                "      the Ontul authorization extension on or off. Blank `ontulAuthzEndpoint` / `ontulAuthzToken` keep the",
                "      stored values, else use this platform's Ontul cluster; `ontulAuthzCatalogMap`",
                "      (`lakehouse=iceberg,…`) maps Polaris catalog names to the catalog names IAM policies use — blank",
                "      derives it from the query engine's catalogs. The servers restart one at a time. The extension",
                "      itself is installed as a Polaris patch (`server/` directory).",
                "    - Catalogs carry no S3 credentials; the servers use their own (`s3-credentials`). For catalogs",
                "      created by an earlier version, `POST …/catalogs/{catalog}/remove-s3-keys` removes the keys from",
                "      the catalog and from every table and view in it. Engines started before that keep the old",
                "      defaults and copy the keys into tables they create until restarted — restart them and call it",
                "      again.", ""],
}


def camel(flag):
    p = flag.lstrip("-").split("-")
    return p[0] + "".join(x[:1].upper() + x[1:] for x in p[1:])


# Bodies the route table leaves blank because changoctl builds them itself — field names read
# from the handlers (AdminApiHandler: auth, change-password, LDAP login, IAM users, patch apply).
SPECIAL = {
    ("POST", "/admin/api/auth/login"): [("username", "string", "console user"), ("password", "string", "")],
    ("POST", "/admin/api/auth/refresh"): [("refreshToken", "string", "the refresh token of the last login/refresh — it rotates")],
    ("POST", "/admin/api/auth/change-password"): [("oldPassword", "string", ""), ("newPassword", "string", "")],
    ("POST", "/admin/api/auth/sso/ldap/login"): [("username", "string", "directory user"), ("password", "string", "")],
    ("POST", "/admin/api/iam/users"): [("username", "string", ""), ("password", "string", "initial password"),
                                        ("groups", "list", "optional"), ("policyNames", "list", "optional"),
                                        ("attributes", "map", "optional"), ("userId", "string", "optional")],
    ("POST", "/admin/api/patch/{patchId}/apply"): [
        ("clusterId", "string", "target cluster — required for a component patch, omitted for the platform's own patch"),
        ("restartMode", "string", "default `rolling`")],
}


def query_section(r):
    """Options of a body-less route travel as query parameters (?purgeData=true, ?name=…)."""
    flags = re.findall(r"--([a-z][a-z0-9-]*)", r["cmd"])
    flags = [f for f in flags if f not in ("file",)]
    if not flags or r["body"]:
        return [], ""
    lines = ["**Query parameters:** " + ", ".join("`%s`" % camel(f) for f in flags), ""]
    qs = "?" + "&".join("%s=%s" % (camel(f), "true" if f.startswith("purge") else "<value>") for f in flags)
    return lines, qs


def body_section(r):
    b = r["body"]
    sp = SPECIAL.get((r["method"], r["path"]))
    if sp:
        lines = ["**Body (JSON):**", "", "| Field | Type | Description |", "|---|---|---|"]
        lines += ["| `%s` | %s | %s |" % f for f in sp]
        return lines, "'" + json.dumps({f[0]: "<value>" for f in sp[:2]}) + "'"
    if b.startswith("raw"):
        return ["**Body:** the patch tarball as raw bytes (`Content-Type: application/gzip`)."], "RAW"
    if not b:
        return [], None
    if b == "{}":
        return ["**Body:** `{}` (empty object)."], "{}"
    if b == "json":
        flags = [f for f in re.findall(r"--([a-z][a-z0-9-]*)", r["cmd"]) if f not in ("set",)]
        if not flags:
            return ["**Body:** JSON object (see the handler; `changoctl … -f body.json`)."], "@body.json"
        lines = ["**Body (JSON):**", "", "| Field | Type |", "|---|---|"]
        for f in flags:
            lines.append("| `%s` | string |" % camel(f))
        example = "'" + json.dumps({camel(f): "<value>" for f in flags}) + "'"
        return lines, example
    cls = catalog.get(b)
    if not cls:
        return ["**Body:** `%s`." % b], "@body.json"
    lines = ["**Body:** `%s`" % b, "", "| Field | Type | Default | Description |", "|---|---|---|---|"]
    ex = {}
    for name, f in cls["fields"].items():
        d = f.get("default")
        dtxt = "" if d is None else ("`%s`" % json.dumps(d, ensure_ascii=False))
        doc = (f.get("doc") or "").replace("|", "\\|").replace("\n", " ")
        lines.append("| `%s` | %s | %s | %s |" % (name, f.get("type", ""), dtxt, doc))
        if d not in (None, "", [], {}) and len(ex) < 4:
            ex[name] = d
    if not ex:
        first = list(cls["fields"])[:2]
        ex = {k: "<value>" for k in first}
    return lines, "'" + json.dumps(ex, ensure_ascii=False) + "'"


CLUSTER_RECORD = {"clusterId": "polaris-1", "componentType": "polaris", "version": "1.4.1",
                  "status": "RUNNING", "createdAt": 1795219200000, "lastUpdatedAt": 1795219260000,
                  "settings": {"realm": "polaris-1", "clientSecret": "***"}}


def response_note(r, comp):
    m, p = r["method"], r["path"]
    rest = rest_of(p) or ""
    parts = rest.split("/")
    if comp in TITLES and comp not in ("control-plane", "components", "security", "patch-backup"):
        if len(parts) == 1 and m == "GET":
            return "Array of cluster records."
        if len(parts) == 2 and parts[1] == "{id}" and m == "GET":
            return "The cluster record (secret settings shown as `***`)."
        if len(parts) == 3 and parts[2] in ("start", "stop", "restart", "config", "scale", "unscale") and m == "POST":
            return "The updated cluster record."
    return None


def curl(r, body_example, qs=""):
    path = r["path"].replace("{", "<").replace("}", ">") + qs
    perm = permission(r["method"], r["path"])
    auth = "" if perm == "Public" else ' -H "Authorization: Bearer $T"'
    data = ""
    if body_example == "RAW":
        data = " -H 'Content-Type: application/gzip' --data-binary @patch.tgz"
    elif body_example == "@body.json":
        data = " -H 'Content-Type: application/json' -d @body.json"
    elif body_example:
        data = " -H 'Content-Type: application/json' -d " + body_example
    return 'curl -s -X %s "%s%s"%s%s' % (r["method"], HOST, path, auth, data)


# source cross-check: every literal segment of a path must appear in the master sources
src = ""
for root, _, files in os.walk(os.path.join(REPO, "chango-master/src/main/java")):
    for f in files:
        if f.endswith(".java"):
            src += open(os.path.join(root, f), encoding="utf-8").read()
missing = []
for r in rows:
    for seg in re.split(r"[/?=&]", r["path"]):
        if not seg or seg.startswith("{") or seg in ("admin", "api", "v1"):
            continue
        if seg not in src:
            missing.append((r["method"], r["path"], seg))

by_area = {}
for r in rows:
    by_area.setdefault(area(r["path"]), []).append(r)

os.makedirs(OUT, exist_ok=True)
for a, rs in sorted(by_area.items()):
    title = TITLES.get(a, a)
    out = ["# %s" % title, "",
           "Generated from the platform source — see [API overview](index.md) for authentication, "
           "errors and the permission model. Every route below is also a `changoctl` command "
           "([CLI](../operations/cli.md)).", ""]
    if a in TITLES and a not in ("control-plane", "components", "security", "patch-backup"):
        out += ["## Cluster record", "",
                "Cluster routes of this component return the cluster record. Secret settings "
                "(passwords, secret keys, tokens) are never returned — they read `***`; download "
                "them with `GET /admin/api/credentials/download` (administrator).", "",
                "```json", json.dumps(dict(CLUSTER_RECORD, componentType=a,
                                           clusterId=a + "-1"), indent=2), "```", ""]
    out += AREA_NOTES.get(a, [])
    out += ["| Method | Path | Permission | changoctl |", "|---|---|---|---|"]
    for r in rs:
        anchor = re.sub(r"[^a-z0-9]+", "-", (r["method"] + " " + r["path"]).lower()).strip("-")
        out.append("| %s | [`%s`](#%s) | %s | `%s` |" % (r["method"], r["path"], anchor,
                                                        permission(r["method"], r["path"]),
                                                        r["cmd"].replace("|", "\\|")))
    out.append("")
    for r in rs:
        anchor = re.sub(r"[^a-z0-9]+", "-", (r["method"] + " " + r["path"]).lower()).strip("-")
        out += ["## %s `%s` { #%s }" % (r["method"], r["path"], anchor), "",
                "- **Permission:** %s" % permission(r["method"], r["path"]),
                "- **CLI:** `%s`" % r["cmd"], ""]
        lines, ex = body_section(r)
        if lines:
            out += lines + [""]
        qlines, qs = query_section(r)
        out += qlines
        out += ["```bash", curl(r, ex, qs), "```", ""]
        note = response_note(r, a)
        if note:
            out += ["**Response:** %s" % note, ""]
    open(os.path.join(OUT, a + ".md"), "w").write("\n".join(out))

print("routes:", len(rows), "pages:", len(by_area))
for a, rs in sorted(by_area.items()):
    print("  %-16s %d" % (a, len(rs)))
print("segments not found in master sources:", len(missing))
for m in missing[:40]:
    print("  ", *m)
