# Checksums & Bill of Materials

An air-gapped installation arrives on physical media and has to clear the customer's import-approval process before anyone may run it. That process asks two separate questions, and they need different answers:

> **Did this arrive as it left?** → checksums
>
> **What is in it?** → a bill of materials

`build-with-comps.sh` produces both. Nothing here needs a network, an extra tool, or a second pass — the files are generated as the bundle is assembled and travel with it.

## What the bundle contains

```
chango-bundle-3.0.0.tar.gz               the media
chango-bundle-3.0.0.tar.gz.sha256        ← its digest, deliberately OUTSIDE the archive
chango-bundle-3.0.0/
├── chango-3.0.0.tar.gz                  node-manager hosts (lean)
├── chango-with-comps-3.0.0.tar.gz       master host (+ JDKs + components)
├── checksums.sha256                     the two tarballs above
├── component-inventory.tsv              products: version, digest, licence, source
├── component-inventory.json             the same list, CycloneDX
└── sbom/
    ├── chango-3.0.0-sbom.json           libraries inside chango's own jars
    └── chango-3.0.0-sbom.xml
```

## Checksums, at three levels

Three levels because three different things get verified, at three different moments.

| Level | File | Covers | Verified |
|---|---|---|---|
| Media | `chango-bundle-<ver>.tar.gz.sha256` | The single file carried in | On arrival, before anything is opened |
| Contents | `checksums.sha256` | The two tarballs inside | After extracting the bundle |
| Products | `component-inventory.tsv` | Every component, JDK and separately-shipped jar | During security review |

The media digest sits **beside** the bundle, not inside it. A checksum stored within the archive it describes proves nothing — an archive rewritten in transit can carry a matching digest for its new contents.

### Verifying

```bash
# 1. the media, before opening it
sha256sum -c chango-bundle-3.0.0.tar.gz.sha256

# 2. its contents
tar -xzf chango-bundle-3.0.0.tar.gz
cd chango-bundle-3.0.0
sha256sum -c checksums.sha256

# 3. what is in it
column -t -s$'\t' component-inventory.tsv
```

### Where checksums stop

At the artifact boundary. Every file listed is one that *arrives as its own file*, so its digest is what proves it arrived intact.

Unpacking a product tarball to checksum the libraries inside it would add hundreds of rows without adding any assurance: the tarball's own digest already covers every byte in it. What lives inside is a question about *composition*, not *integrity*, and that is the bill of materials' job.

A separately-shipped jar — `hadoop-aws-3.3.4.jar`, the Iceberg runtimes — is its own artifact and is listed. A jar inside `trino-server-479.tar.gz` is not.

## Two bills of materials

They answer different questions and neither substitutes for the other.

| | `component-inventory` | `sbom/` |
|---|---|---|
| Lists | Products the bundle ships | Java libraries inside chango's own jars |
| Size | ~36 entries | ~380 entries |
| Format | TSV + CycloneDX JSON | CycloneDX JSON + XML |
| Read by | A security reviewer; an import-approval form | A vulnerability scanner |

When an advisory names a library — "Jackson databind before X" — the SBOM is what answers whether the deployment is affected. When a reviewer asks what products are being brought onto the network, the inventory is what has room on the form.

### component-inventory

One row per artifact:

| Column | Meaning |
|---|---|
| `product` | Normalised product name — `trino`, not `trino-server` |
| `version` | As released |
| `file` | The artifact's filename |
| `sha256` | Its digest |
| `bytes` | Its size |
| `license` | SPDX identifier, or a `LicenseRef-` for non-SPDX terms |
| `source` | Upstream URL it was fetched from, blank if built during packaging |

Sorted first-party first, then everything else alphabetically.

The CycloneDX form carries the same data with the digest in `hashes`, the source in `externalReferences`, and the filename and size as `chango:` properties — so the product level can be fed to the same tooling as the library level instead of being a spreadsheet nobody can scan.

### Licences are a table, not a guess

Licences are looked up from a fixed table rather than inferred from filenames. A licence is a legal fact about a release, and guessing is how a security review ends up with a wrong answer in writing.

One entry is worth flagging before a review rather than during one:

!!! warning "Confluent Community License"
    Schema Registry ships under the **Confluent Community License**, which is source-available but **not** an OSI-approved open-source licence. It may not appear on a customer's approved-licence list.

    It places no restriction on internal use of the kind chango deployments make. What it prohibits is offering the software itself as a service to third parties. If it is nonetheless a blocker, the component can be excluded from the bundle.

Everything else falls into ordinary categories: Apache-2.0 for the Apache engines and the Iceberg / Hadoop / AWS SDK libraries, GPL-2.0-with-classpath-exception for the OpenLogic JDKs, PostgreSQL for PostgreSQL, GPL-3.0-or-later for ansible-core, MIT for SLF4J, and a Cloud Chef Labs commercial licence for the first-party products.

### What is deliberately absent

Support responsibility — who patches what, for how long, and how fast. That is a commitment rather than a fact about an artifact, it belongs in the contract, and a build script has no business asserting it. When an approval form asks, answer it from the agreement.

## Bundling a subset

A deployment that installs part of the catalogue has no reason to carry all of it. The full bundle is over 10 GB; a ShannonStore-and-PostgreSQL deployment needs about a fifth of that.

Stage only the components you need under `components/`, then:

```bash
CHANGO_SKIP_DOWNLOAD=1 bash build-with-comps/build-with-comps.sh
```

The bundle, the checksums and the inventory then describe exactly what is present — which is also what the customer is asked to approve.

The installer's extraction check has to be told the same thing. It fails when a component directory extracts empty, which catches a truncated 10 GB extract but would otherwise reject a deliberate subset:

```yaml
# inventory.yml
all:
  vars:
    chango_expected_components:
      - postgresql
      - shannonstore
```

The check exists to catch a broken extraction, not to insist on the whole catalogue.

## Where the SBOM comes from

`./package.sh` runs the CycloneDX gradle task in the same invocation that builds the jars, so the SBOM can never describe a different build than the one being packaged. It lands in the release at `sbom/` and is copied into the bundle from there.

Regenerating it by hand:

```bash
./gradlew cyclonedxBom
# build/reports/bom.json, build/reports/bom.xml
```

## Recording upstream sources

`download.sh` writes `downloads.sha256` beside `components/` as it fetches — one line per artifact with its digest, its filename and the URL it came from.

The bundle checksums prove the media arrived intact. This proves which upstream artifact each file came from, which is the other half of what a review asks, and it is the only place the source URL is written down. `component-inventory` reads it to fill the `source` column.
