# github-workflows

Reusable GitHub Actions workflows and shared CI standards for `flungo`'s repositories.
Instead of each repo copy-pasting (and silently drifting) its CI, repos call these reusable workflows and pin the moving `@v2` branch.
Fix or improve a workflow once here; merging to `main` advances `v2` automatically and every consumer follows.

Three families:

- **Terraform** — `terraform.yml`, `terraform-drift.yml`, for the Terraform repos.
- **Terraform provider** — `terraform-provider-test.yml`, `terraform-provider-docs.yml`, `terraform-provider-release.yml`, for the Terraform provider repos.
- **Markdown** — `markdown-lint.yml`, `markdown-links.yml`, for any repo with Markdown docs (most repos), plus the opt-in `markdown-sembr.yml` for repos that write one sentence per source line.

## Reusable workflows

| Workflow | Purpose |
| --- | --- |
| [`terraform.yml`](.github/workflows/terraform.yml) | Terraform plan on PR (posted as a PR comment), apply on merge to the default branch or on `workflow_dispatch` |
| [`terraform-drift.yml`](.github/workflows/terraform-drift.yml) | Daily drift remediation with GitHub-issue notifications (opt-in; for repos with auto-rotating credentials) |
| [`terraform-provider-test.yml`](.github/workflows/terraform-provider-test.yml) | Terraform provider CI: build + vet, gofmt + golangci-lint, unit tests, and an optional docs-in-sync check |
| [`terraform-provider-docs.yml`](.github/workflows/terraform-provider-docs.yml) | Regenerate `tfplugindocs` Registry docs on a branch and commit them back (no local Terraform needed) |
| [`terraform-provider-release.yml`](.github/workflows/terraform-provider-release.yml) | GoReleaser build + GPG-signed publish of a provider to the Terraform + OpenTofu registries on a `v*` tag |
| [`markdown-lint.yml`](.github/workflows/markdown-lint.yml) | `markdownlint-cli2` style/structure check |
| [`markdown-links.yml`](.github/workflows/markdown-links.yml) | lychee internal link/anchor check (blocking) + daily external-URL sweep that reports via an issue |
| [`markdown-sembr.yml`](.github/workflows/markdown-sembr.yml) | Opt-in: flags two sentences sharing a source line — the one hard [semantic line break](https://sembr.org/) rule |
| [`flungo-workflows.yml`](.github/workflows/flungo-workflows.yml) | Opt-in: the jobs every consumer should run against this repo. Today `version-check` — flags a consumer pinning a now-frozen major by opening/closing a migration issue in its own repo (no credential) |

## Using them

A consumer repo calls a workflow and passes its own inputs and secrets.
Pin to the moving major branch (`@v2`):

```yaml
jobs:
  markdown-links:
    uses: flungo/github-workflows/.github/workflows/markdown-links.yml@v2
    secrets:
      LYCHEE_GITHUB_TOKEN: ${{ secrets.LYCHEE_GITHUB_TOKEN }}
```

See the adopting runbooks for every workflow's inputs, secrets, and a copy-paste caller: [Terraform](docs/runbooks/adopting-terraform-workflows.md), [Provider](docs/runbooks/adopting-terraform-provider-workflows.md), [Markdown](docs/runbooks/adopting-markdown-workflows.md).

**Every consumer should also adopt [`flungo-workflows`](docs/runbooks/adopting-flungo-workflows.md)** — a one-line, credential-free opt-in caller whose `version-check` job raises an issue in the consumer's own repo if a future major bump ever leaves it pinning a frozen `@vN`.
Recommended for every repo that pins these workflows.

## Standards & rationale

- **Terraform CI** contract (triggers, HCP Local execution, secret model, drift pause) — [`docs/reference/terraform-workflow.md`](docs/reference/terraform-workflow.md).
- **Provider CI** contract (build/lint/test, docs regenerate/check, release/signing, why acceptance tests stay local) — [`docs/reference/terraform-provider-workflow.md`](docs/reference/terraform-provider-workflow.md).
- **Markdown validation** (repo-agnostic) — [`docs/reference/markdown-validation.md`](docs/reference/markdown-validation.md).
- Design rationale (why a shared public repo, what stays repo-local) — [decision records](docs/decisions/).

## Versioning

Consumers pin `@v2` — a moving **branch**, not a tag ([ADR-003](docs/decisions/003-version-via-moving-v1-branch.md)).
Every merge to `main` runs [`release.yml`](.github/workflows/release.yml), which fast-forwards `v2` to `main`, so consumers following `@v2` pick fixes up automatically.
A breaking change cuts a new major branch (`v3`) by bumping `MAJOR_BRANCH` in that workflow — see [`docs/runbooks/releasing.md`](docs/runbooks/releasing.md).
This repo's own workflows and docs are validated on every PR by [`ci.yml`](.github/workflows/ci.yml) (actionlint plus the repo's own Markdown workflows).
