# ADR-008: Inject secret Terraform variables via a masked env-var explosion

Date: 2026-07-29
Status: Accepted

## Context

The reusable Terraform workflows (`terraform.yml`, `terraform-drift.yml`) passed exactly one secret value into Terraform — the provider token, via the generic `tf-var-name` input + `provider_token` secret.
A config that consumes *further* secret values has no way to receive them: `github_actions_secret` (and any resource configured with a credential — a database password, a third-party API key) needs the plaintext value as a `TF_VAR` at plan/apply time, and the workflow supplied none.

Two mechanisms were prototyped in parallel ([#15](https://github.com/flungo/github-workflows/pull/15) and [#16](https://github.com/flungo/github-workflows/pull/16)):

- **A var file** — write the JSON to `ci.auto.tfvars.json` in the working directory, which Terraform auto-loads.
- **An env-var explosion** — parse the JSON and export each entry as a `TF_VAR_<name>` env var.

The choice shapes the workflow's secret contract (a new `@v1` secret, and how secret values are handled), so it is recorded here — in the same class as [ADR-005](005-extend-terraform-workflow-via-plan-artifact.md)'s plan-artifact seam.

## Decision

Add an optional **`tf_secret_vars`** secret to both workflows: a JSON object `{"<var>": "<value>", …}` that the workflow explodes into masked `TF_VAR_<var>` env vars, naming no specific variable.

**Env-var explosion over the `*.auto.tfvars.json` file**, on secret-hygiene grounds:

- Each value is `::add-mask::`ed at the point of handling — line by line, because `::add-mask::` is line-oriented and a multi-line value masked as one string leaks from line 2 — rather than relying on every consumer to mark its variables `sensitive`.
- Nothing secret is written to the workspace disk.
- The caller assembles the map inline from its own standalone secrets via `toJSON()`, so each value stays an independently-rotatable secret and the JSON is always well-formed.

**Secret and non-secret variables travel distinct paths.**
Secrets go through `tf_secret_vars` (a `secrets:` entry, always masked); the plain `tf_vars` name is **reserved** for a future non-secret `inputs:` mechanism — kept distinct so a secret is never routed through a non-masked path.

**Fail loud at the point of error.**
The export step rejects invalid JSON, an invalid Terraform-variable-name key, or an empty value with an `::error::` and non-zero exit, and writes to `GITHUB_ENV` with a random heredoc delimiter so a value cannot terminate it early and inject arbitrary entries.

**Plan-output redaction remains the consumer's responsibility.**
Masking covers the run *logs* only; the plan text also lands in the `terraform-plan` artifact and the PR/`drift` comment, which do not pass through log masking — so the consuming variable must be declared `sensitive = true`.

## Consequences

**Positive:**

- A config can consume any secret value beyond the provider token, with the workflow naming no specific variable — additive and backward-compatible, so it rides `@v1` with no major bump.
- Masking at the point of handling, no on-disk secret, and an escape-safe caller give strong secret hygiene that does not depend on each consumer getting `sensitive` right.
- The secret/non-secret split makes it structurally impossible to route a secret through a non-masked path.

**Negative / trade-offs:**

- The export step is duplicated in both workflows. Extracting it to a shared composite action was deferred: a reusable workflow must reference it by full path (`flungo/github-workflows/.github/actions/…@v1`, since a local `./` action resolves against the *caller's* checkout), which creates a pre-merge testing chicken-and-egg. *(Since resolved — [ADR-009](009-composite-action-via-workflow-identity-checkout.md) extracts the step and fetches it at the workflow file's own commit instead of `@v1`.)*
- Per-line masking registers every line of every value for the whole job, so a short or common value redacts later log output — mitigated by documenting that values must be genuinely secret.
- Plan-output redaction can't be enforced by the workflow; it relies on the consumer declaring `sensitive = true`.
