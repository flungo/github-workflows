# github-workflows

Reusable GitHub Actions workflows and shared CI standards for `flungo`'s repositories. Instead of each repo copy-pasting (and silently drifting) its CI, repos call these reusable workflows and pin the moving `@v1` branch. Fix or improve a workflow once here; merging to `main` advances `v1` automatically and every consumer follows.

Two families:

- **Terraform** — `terraform.yml`, `terraform-drift.yml`, for the Terraform repos.
- **Markdown** — `markdown-lint.yml`, `markdown-links.yml`, for any repo with Markdown docs (most repos).

## Reusable workflows

| Workflow | Purpose |
|---|---|
| [`terraform.yml`](.github/workflows/terraform.yml) | Terraform plan on PR (posted as a PR comment), apply on merge to the default branch or on `workflow_dispatch` |
| [`terraform-drift.yml`](.github/workflows/terraform-drift.yml) | Daily drift remediation with GitHub-issue notifications (opt-in; for repos with auto-rotating credentials) |
| [`markdown-lint.yml`](.github/workflows/markdown-lint.yml) | `markdownlint-cli2` style/structure check |
| [`markdown-links.yml`](.github/workflows/markdown-links.yml) | lychee internal link/anchor check (blocking) + daily external-URL sweep that reports via an issue |

## Using them

A consumer repo calls a workflow and passes its own inputs and secrets. Pin to the moving major branch (`@v1`):

```yaml
jobs:
  markdown-links:
    uses: flungo/github-workflows/.github/workflows/markdown-links.yml@v1
    secrets:
      LYCHEE_GITHUB_TOKEN: ${{ secrets.LYCHEE_GITHUB_TOKEN }}
```

See the adopting runbooks for every workflow's inputs, secrets, and a copy-paste caller: [Terraform](docs/runbooks/adopting-terraform-workflows.md), [Markdown](docs/runbooks/adopting-markdown-workflows.md).

## Standards & rationale

- **Terraform CI** contract (triggers, HCP Local execution, secret model, drift pause) — [`docs/reference/terraform-workflow.md`](docs/reference/terraform-workflow.md).
- **Markdown validation** (repo-agnostic) — [`docs/reference/markdown-validation.md`](docs/reference/markdown-validation.md).
- Design rationale (why a shared public repo, what stays repo-local) — [decision records](docs/decisions/).

## Versioning

Consumers pin `@v1` — a moving **branch**, not a tag ([ADR-003](docs/decisions/003-version-via-moving-v1-branch.md)). Every merge to `main` runs [`release.yml`](.github/workflows/release.yml), which fast-forwards `v1` to `main`, so consumers following `@v1` pick fixes up automatically. A breaking change cuts a new major branch (`v2`) by bumping `MAJOR_BRANCH` in that workflow — see [`docs/runbooks/releasing.md`](docs/runbooks/releasing.md). This repo's own workflows and docs are validated on every PR by [`ci.yml`](.github/workflows/ci.yml) (actionlint plus the repo's own Markdown workflows).
