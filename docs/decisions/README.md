# Architecture Decision Records

Decisions are numbered sequentially and never deleted or renumbered. Each file documents the context, decision, and consequences for a key architectural choice. Superseded decisions keep their file and get a note at the top pointing to the newer ADR.

| # | Title | Status | Summary |
| --- | --- | --- | --- |
| [001](001-centralised-reusable-workflows.md) | Centralised reusable workflows | Accepted (versioning revised by ADR-003) | Extract the fleet's copy-pasted CI into `workflow_call` reusable workflows in this public repo — a Terraform family (plan/apply, drift) and a repo-agnostic Markdown family. Consumers call them and pin the moving `v1` ref; secrets stay with callers; stalwart's bespoke Terraform pipeline is exempt. |
| [002](002-markdown-validation-tooling.md) | Markdown validation tooling | Accepted | lychee (Rust) for all link + anchor resolution (offline internal PR check + online external sweep); markdownlint-cli2 for style; remark-validate-links the documented fallback if lychee's GitHub-slugger parity ever fails. Rejects markdown-link-check, remark-lint-for-style, and SSG strict modes. |
| [003](003-version-via-moving-v1-branch.md) | Version via a moving major branch, advanced automatically | Accepted | Version the reusable workflows with a moving major **branch** rather than a `v1` tag: consumers still pin `@v1`, but `release.yml` fast-forwards it to `main` on every merge; a breaking change cuts the next major by bumping `MAJOR_BRANCH` in that workflow (freezing the old major). Revises ADR-001's tag mechanism. |
| [004](004-version-check-opt-in.md) | Opt-in consumer version check | Accepted (renamed by ADR-012) | Surface a consumer that pins a now-frozen major via an opt-in reusable `version-check.yml`: each consumer runs it on a schedule, comparing its own pins to the latest published major and opening/closing a tracking issue in its own repo — no cross-owner credential. Supersedes ADR-001's Renovate/Dependabot follow-up; producer-side rollup census left out of scope. |
| [005](005-extend-terraform-workflow-via-plan-artifact.md) | Extend the Terraform workflow via a published plan artifact | Accepted | The Terraform workflow publishes its plan (`plan.jsonl`/`plan.txt`) as an artifact so consumers can extend it with a *separate* job (`needs:` the caller job, gated on its `result`) that consumes the plan — reusable workflows can't take injected steps, and the artifact contract avoids the drift of forking or re-orchestrating. |
| [006](006-terraform-provider-ci-family.md) | A reusable CI family for the Terraform providers | Accepted | Centralise the standard provider scaffold's CI — build/lint/test + docs-sync (`terraform-provider-test.yml`), docs regenerate-and-commit (`terraform-provider-docs.yml`), GoReleaser publish (`terraform-provider-release.yml`) — as a third reusable family; acceptance tests stay in each consumer as a local `testacc` job because a live backend and coverage/diagnostics don't generalise. |
| [007](007-track-third-party-actions-with-dependabot.md) | Track third-party actions with Dependabot | Accepted | Enable Dependabot (`github-actions` ecosystem) to keep the reusable workflows' third-party actions current; each bump rides the moving `@v1` to the whole fleet. Distinct from this repo's own `@vN` versioning (moving branch + version-check, which Dependabot can't track); consumers add their own per-repo config for direct refs, ignoring `flungo/github-workflows`. |
| [008](008-secret-terraform-variables.md) | Inject secret Terraform variables via a masked env-var explosion | Accepted | Add an optional `tf_secret_vars` secret (a JSON map) to the Terraform workflows, exploded into masked `TF_VAR_*` env vars — chosen over a `*.auto.tfvars.json` file for masking-at-source, no on-disk secret, and an escape-safe `toJSON()` caller. Secret and non-secret vars travel distinct paths (the plain `tf_vars` input name is reserved); the step fails loud on bad input; plan-output redaction still needs `sensitive = true`. |
| [009](009-composite-action-via-workflow-identity-checkout.md) | Reference shared composite actions via a workflow-identity checkout | Accepted | Extract the duplicated TF_VAR export shell to the `export-terraform-variables` composite action, fetched by each Terraform job via a sparse checkout of this repo at `job.workflow_sha` — the workflow file's own commit — so the action always matches the ref the caller pinned and is testable from a feature branch (plus per-action self-CI in `action-tests.yml`), clearing ADR-008's deferral. |
| [010](010-caller-job-ids-match-the-workflow-filename.md) | A caller's job ID matches the reusable workflow's filename | Accepted | A check's context is `<caller job id> / <reusable job name>`, so the half an adopter types is part of the contract — and the runbooks' own examples were inconsistent, six of eight using a short generic word (`lint`, `links`, `ci`, `docs`, `release`, `drift`). A caller job ID is a repository-wide namespace, and those are exactly the names a repo wants for something else. The rule is now mechanical: job ID = the reusable workflow's filename without `.yml`, which makes the caller half predictable — what lets `terraform-github` hardcode the strings its `markdown` flag requires. Caller-side only, so nothing here changes behaviour and existing adopters realign at leisure; ADR-011 does the other half. |
| [011](011-reusable-job-ids-are-the-check-name.md) | A reusable job's ID is its check name, and that lands as `v2` | Proposed | The right-hand half of a context was inconsistent — nine of twelve jobs reported their bare ID, three reported prose (`Internal links & anchors`), and none was discoverable without running the workflow. Reusable jobs now set no `name:`: the ID is the check name, short and lowercase, describing the role within its own workflow (the filename already carries the family). Every context becomes derivable from the filename plus the job IDs, and punctuation-free. Renaming a context breaks branch protection rather than a run, which `releasing.md` did not count as breaking — it now does — so this cuts **`v2`** and is the whole of it. Done now rather than deferred so `terraform-github` hardcodes each string once and the eventual `@v2` migration stays a pin bump. `terraform / terraform` is unchanged. |
| [012](012-flungo-workflows-meta-workflow.md) | `version-check.yml` becomes `flungo-workflows.yml` | Proposed | Applying ADR-010 and ADR-011 to `version-check.yml` degenerates to `version-check / version-check`: `version` is not a family and the job is the whole concern, so both halves collapse. It is also ambiguous — a caller job called `version-check` says nothing about *whose* version. The file is renamed to `flungo-workflows.yml` with `version-check` as a job in it, giving `flungo-workflows / version-check` and a home for future jobs that keep a consumer correctly wired to this repository. ADR-004's mechanism is unchanged; its packaging and runbook are not. Rides `v2` with ADR-011 so consumers migrate once. |

## Adding a new ADR

1. Create `docs/decisions/<NNN>-<kebab-case-title>.md` using the template below.
2. Update this index with a one-sentence summary.
3. If the new decision supersedes an existing one, update the older ADR's status to `Superseded by ADR-NNN`.

### ADR template

```markdown
# ADR-NNN: Title

Date: YYYY-MM-DD
Status: Accepted

## Context

Why does this decision need to be made?

## Decision

What was decided?

## Consequences

**Positive:**
- ...

**Negative / trade-offs:**
- ...
```
