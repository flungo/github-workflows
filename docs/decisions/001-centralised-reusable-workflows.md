# ADR-001: Centralised reusable workflows

Date: 2026-07-21
Status: Accepted

> **Revised by [ADR-003](003-version-via-moving-v1-branch.md):** the versioning
> mechanism below (a moving `v1` **tag**) is superseded by a moving `v1`
> **branch**. Consumers still pin `@v1`; only how the ref advances changed. The
> rest of this ADR stands.

## Context

Several `flungo` repositories ran near-identical GitHub Actions CI. The Terraform repos (`terraform-grafana-cloud`, `terraform-github`, `stalwart.flungo.net`, with `terraform-cloudflare` and `authentik.flungo.net` to follow) each had a plan-on-PR / apply-on-merge workflow, and one had a daily drift-remediation workflow; the implementations were copied by hand and had begun to drift (`terraform-github`'s was explicitly "adapted from `terraform-grafana-cloud`"). Separately, `stalwart.flungo.net` maintained repo-agnostic Markdown-validation workflows — applicable to *any* repo with docs, not just Terraform ones — whose stated end state was "a shared reusable workflow or template repo". A fix had to be re-applied by hand in each repo, with nothing keeping them in sync.

## Decision

Extract the shared CI into `workflow_call` reusable workflows in a dedicated repository, `flungo/github-workflows`, and have each consumer call them. Two families:

- **Terraform** (`terraform.yml`, `terraform-drift.yml`) — for the Terraform repos.
- **Markdown** (`markdown-lint.yml`, `markdown-links.yml`) — repo-agnostic; any repo with Markdown can adopt them.

Details:

- **Public repository.** The workflows contain no secrets (callers pass every credential), and a public reusable workflow can be called by private repos with no Actions cross-repo sharing configuration.
- **Provider-agnostic Terraform workflow.** The provider token is a generic `provider_token` secret plus a `tf-var-name` input naming the `TF_VAR_*` env var; the shared file names no specific provider. Other variation (`working-directory`, `concurrency-group`, `plan-comment-marker`, `terraform-version`) is exposed as inputs.
- **Moving major tag.** Consumers pin `@v1`; the tag moves forward for fixes, a new major tag for breaking input/secret changes.
- **Repo-local content stays local.** Terraform config (`*.tf`) and version pins, and each repo's `.markdownlint-cli2.jsonc`, `.lycheeignore`, and secrets remain in the consumer.
- **Drift remediation is opt-in.** Daily apply is only wired for repos with auto-rotating credentials that must stay authoritative (currently `terraform-grafana-cloud`).
- **`stalwart.flungo.net`'s Terraform pipeline is exempt.** Its needs are genuinely different (ephemeral-container tests, a disabled LAN apply, a cross-repo provider-regression job), so it keeps its bespoke Terraform workflow and adopts only the Markdown workflows.

## Consequences

**Positive:**

- One source of truth: a workflow fix lands once and propagates via a tag bump.
- Onboarding a repo is a short caller file — Terraform or Markdown, whichever it needs.
- The reusable workflows are validated on every PR here (actionlint + the repo's own Markdown checks) before a tag moves.

**Negative / trade-offs:**

- A tag bump in each consumer is still required to pick up changes; pairing this with Renovate/Dependabot is a follow-up so the bumps don't themselves silently lag. (Both parts are since superseded: the moving branch of [ADR-003](003-version-via-moving-v1-branch.md) removes the routine bump, and [ADR-004](004-version-check-opt-in.md) replaces the dependency-bot follow-up with an opt-in version check.)
- Reusable-workflow constraints (secrets must be declared; some contexts are restricted) make the shared files more abstract than the inline originals.
- Two-hop indirection (caller → reusable workflow) is marginally harder to read than a single inline workflow.
