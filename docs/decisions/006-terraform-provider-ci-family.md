# ADR-006: A reusable CI family for the Terraform providers

Date: 2026-07-26 Status: Accepted

## Context

`flungo` writes Terraform providers (the first is [`terraform-provider-stalwart`](https://github.com/flungo/terraform-provider-stalwart); more are expected).
Every such provider is the same HashiCorp scaffold — a Go module on the Plugin Framework, `tfplugindocs`-generated Registry docs committed under `docs/`, and a GoReleaser publish to the Terraform and OpenTofu registries — so its CI is almost entirely boilerplate: build + vet, gofmt + golangci-lint, unit tests, a docs-in-sync check, a docs auto-regenerate-and-commit job, and a signed release.

This is the same copy-paste-drift problem the Terraform and Markdown families already solve here ([ADR-001](001-centralised-reusable-workflows.md)).
The one part that does **not** generalise is acceptance testing: it needs a live backend (Stalwart boots a throwaway container; another provider would need its own service), plus provider-specific coverage gating and failure diagnostics.
Generalising a test harness from a single example would bake that provider's specifics into the shared contract.

## Decision

Add a **Terraform provider** family of reusable workflows, called by each provider repo and pinned `@v1` like the other families:

- **`terraform-provider-test.yml`** — the PR/push gate: `build` (build + vet), `lint` (gofmt + golangci-lint), `test` (unit), and an optional `docs` job (regenerate docs + `git diff --exit-code docs/`).
- **`terraform-provider-docs.yml`** — regenerate and commit Registry docs on non-default branches, so contributors need no local Terraform.
- **`terraform-provider-release.yml`** — GoReleaser build + GPG-signed publish on a `v*` tag (or `workflow_dispatch` with a version), unsigned when the GPG secrets are absent.

**Acceptance tests stay in the consumer.**
Each provider keeps its own `testacc` job in the same workflow file that calls `terraform-provider-test.yml` — a reusable workflow composes at the job level, so a caller mixes the shared jobs with its own without forking anything.
The consumer owns the backend, the image matrix, the coverage floor, and the diagnostics.

The workflows stay provider-agnostic: they read the Go version from the consumer's `go.mod`, run `tfplugindocs generate` directly (the provider name auto-derives from the repo name — the `terraform-provider-` prefix stripped — and the `tfplugindocs` version is pinned by the consumer's `go.mod` tool dependency), and take the golangci-lint / Terraform / GoReleaser versions as inputs.
Running `tfplugindocs` here rather than delegating to a per-consumer `make generate` target means the doc-generation command lives in one place and a consumer needs no CI-specific Make target — the same auto-commit that removes the need to run it locally.

## Consequences

**Positive:**

- No copy-paste drift for the boilerplate — a fix here reaches every provider on its next run, and `v1` advances automatically ([ADR-003](003-version-via-moving-v1-branch.md)).
- A new provider adopts CI with three thin callers plus its own `testacc` job.
- The generalisation is limited to what is genuinely standard scaffold; the provider-specific harness is not forced into a shared shape from one example.

**Negative / trade-offs:**

- Acceptance testing is not centralised, so each provider still authors that job (by design — revisit if a second provider shows a genuinely shared shape).
- The docs and release workflows assume the standard scaffold (committed `docs/`, `tfplugindocs` as a `go.mod` tool dependency, a `.goreleaser.yml`); a provider without them opts out (`check-docs: false`, or simply not calling the workflow).
  A provider that needs extra code generation beyond `tfplugindocs` would need an added input or its own docs job.
