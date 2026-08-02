# Adopting the provider workflows

How a `flungo` Terraform **provider** repo calls `terraform-provider-test.yml`, `terraform-provider-docs.yml`, and `terraform-provider-release.yml`.
Pin `@v2`.
For the contract and rationale, see [`terraform-provider-workflow.md`](../reference/terraform-provider-workflow.md) and [ADR-006](../decisions/006-terraform-provider-ci-family.md).

These cover the standard HashiCorp scaffold (build/lint/test, `tfplugindocs` docs, GoReleaser publish).
**Acceptance tests are not covered** — they stay in the consumer; see [§ Acceptance tests stay local](#acceptance-tests-stay-local).

## `terraform-provider-test.yml`

The PR/push gate: `build` (build + vet), `lint` (gofmt + golangci-lint), `test` (unit), and an optional `docs` sync check.

| Input | Default | Purpose |
| --- | --- | --- |
| `go-version-file` | `go.mod` | File the Go version is read from |
| `golangci-lint-version` | `v2.5.0` | golangci-lint to install — must be v2.x for a v2-format `.golangci.yml` |
| `terraform-version` | `latest` | Terraform used to render docs for the sync check |
| `provider-name` | *(derived)* | Provider's Terraform name; empty derives it from the repo name (strips the `terraform-provider-` prefix) |
| `check-docs` | `true` | Regenerate the docs and `git diff` them; set `false` for a provider without generated docs |

No secrets; runs on the repo-scoped `GITHUB_TOKEN`. The docs check runs `tfplugindocs generate` from your module, so it needs [`tfplugindocs`](https://github.com/hashicorp/terraform-plugin-docs) as a tool dependency in your `go.mod` (the standard for a provider with generated docs) — that pins the version too. Add it with:

```sh
go get -tool github.com/hashicorp/terraform-plugin-docs/cmd/tfplugindocs   # Go 1.24+
```

(Older repos may instead pin it via a `//go:build tools` `tools.go` blank import — either works, as long as `go run github.com/hashicorp/terraform-plugin-docs/cmd/tfplugindocs` resolves.)

```yaml
name: test
on:
  pull_request:
  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  terraform-provider-test:
    uses: flungo/github-workflows/.github/workflows/terraform-provider-test.yml@v2

  # Acceptance tests stay local — see below.
  testacc:
    runs-on: ubuntu-latest
    # ... provider-specific steps: boot a backend, run `TF_ACC=1 go test`, gate
    #     coverage, surface diagnostics ...
```

### Acceptance tests stay local

A reusable workflow composes at the **job** level, so the caller keeps its own `testacc` job in the same file alongside the `ci:` caller — no forking.
Acceptance tests need a live backend (e.g. a throwaway container), plus provider-specific coverage gating and failure diagnostics, none of which generalise, so the consumer owns that job outright ([ADR-006](../decisions/006-terraform-provider-ci-family.md)).
Grant it only the permissions it needs (e.g. `pull-requests: write` if it upserts a diagnostics comment on the PR).

## `terraform-provider-docs.yml`

Regenerates the Registry docs and commits them back to the branch, so contributors need no local Terraform.
Pair it with `check-docs: true` on `terraform-provider-test.yml` (the default), which fails the default branch if committed docs ever drift.

| Input | Default | Purpose |
| --- | --- | --- |
| `go-version-file` | `go.mod` | File the Go version is read from |
| `terraform-version` | `latest` | Terraform used to render the docs |
| `provider-name` | *(derived)* | Provider's Terraform name; empty derives it from the repo name (strips the `terraform-provider-` prefix) |

Like the docs-sync check, this runs `tfplugindocs generate` from your module (the same `tfplugindocs` `go.mod` tool dependency as above).
**Requires `contents: write`** on the caller — the job pushes a docs commit (a reusable workflow's `permissions:` only cap the token).

```yaml
name: docs
on:
  push:
    branches-ignore:
      - main
  workflow_dispatch:

jobs:
  terraform-provider-docs:
    permissions:
      contents: write
    uses: flungo/github-workflows/.github/workflows/terraform-provider-docs.yml@v2
```

## `terraform-provider-release.yml`

GoReleaser build + publish on a `v*` tag (or `workflow_dispatch` with a version).
Signed when the GPG secrets are present, unsigned otherwise (early testing only — neither registry accepts an unsigned release).

| Input | Default | Purpose |
| --- | --- | --- |
| `version` | `''` | Tag to release (e.g. `v0.1.0`); required on `workflow_dispatch`, ignored on tag push |
| `goreleaser-version` | `~> v2` | GoReleaser version constraint |
| `go-version-file` | `go.mod` | File the Go version is read from |

| Secret | Required | Purpose |
| --- | --- | --- |
| `GPG_PRIVATE_KEY` | No | ASCII-armored GPG private key registered with the registries; absent = unsigned |
| `PASSPHRASE` | No | Passphrase for the GPG key |

**Requires `contents: write`** on the caller — it publishes a GitHub release (and, on `workflow_dispatch`, pushes the tag).

```yaml
name: release
on:
  push:
    tags:
      - "v*"
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to release (e.g. v0.1.0)'
        required: true
        type: string

jobs:
  terraform-provider-release:
    permissions:
      contents: write
    uses: flungo/github-workflows/.github/workflows/terraform-provider-release.yml@v2
    with:
      version: ${{ inputs.version }}
    secrets:
      GPG_PRIVATE_KEY: ${{ secrets.GPG_PRIVATE_KEY }}
      PASSPHRASE: ${{ secrets.PASSPHRASE }}
```

On a tag push `inputs.version` is empty and GoReleaser uses the pushed tag; on `workflow_dispatch` the workflow creates and pushes the tag first.

## Version check

Every provider consumer should also adopt [`flungo-workflows`](adopting-flungo-workflows.md) — a one-line, credential-free caller that flags the repo if a future major bump ever leaves it on a frozen `@vN`.
