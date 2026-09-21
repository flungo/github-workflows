# Architecture Decision Records

Decisions are numbered sequentially and never deleted or renumbered.
Each file documents the context, decision, and consequences for a key architectural choice.
Superseded decisions keep their file and get a note at the top pointing to the newer ADR.

| # | Title | Status | Summary |
| --- | --- | --- | --- |
| [001](001-centralised-reusable-workflows.md) | Centralised reusable workflows | Accepted (versioning revised by ADR-003) | Extract the fleet's copy-pasted CI into `workflow_call` reusable workflows in this public repo — a Terraform family (plan/apply, drift) and a repo-agnostic Markdown family. Consumers call them and pin the moving `v1` ref; secrets stay with callers; stalwart's bespoke Terraform pipeline is exempt. |
| [002](002-markdown-validation-tooling.md) | Markdown validation tooling | Accepted | lychee (Rust) for all link + anchor resolution (offline internal PR check + online external sweep); markdownlint-cli2 for style; remark-validate-links the documented fallback if lychee's GitHub-slugger parity ever fails. Rejects markdown-link-check, remark-lint-for-style, and SSG strict modes. |
| [003](003-version-via-moving-v1-branch.md) | Version via a moving major branch, advanced automatically | Accepted | Version the reusable workflows with a moving major **branch** rather than a `v1` tag: consumers still pin `@v1`, but `self-release.yml` fast-forwards it to `main` on every merge; a breaking change cuts the next major by bumping `MAJOR_BRANCH` in that workflow (freezing the old major). Revises ADR-001's tag mechanism. |
| [004](004-version-check-opt-in.md) | Opt-in consumer version check | Accepted (renamed by ADR-012; retargeted by ADR-014) | Surface a consumer that pins a now-frozen major via an opt-in reusable `version-check.yml`: each consumer runs it on a schedule, comparing its own pins to the latest published major and opening/closing a tracking issue in its own repo — no cross-owner credential. Supersedes ADR-001's Renovate/Dependabot follow-up; producer-side rollup census left out of scope. |
| [005](005-extend-terraform-workflow-via-plan-artifact.md) | Extend the Terraform workflow via a published plan artifact | Accepted | The Terraform workflow publishes its plan (`plan.jsonl`/`plan.txt`) as an artifact so consumers can extend it with a *separate* job (`needs:` the caller job, gated on its `result`) that consumes the plan — reusable workflows can't take injected steps, and the artifact contract avoids the drift of forking or re-orchestrating. |
| [006](006-terraform-provider-ci-family.md) | A reusable CI family for the Terraform providers | Accepted | Centralise the standard provider scaffold's CI — build/lint/test + docs-sync (`terraform-provider-test.yml`), docs regenerate-and-commit (`terraform-provider-docs.yml`), GoReleaser publish (`terraform-provider-release.yml`) — as a third reusable family; acceptance tests stay in each consumer as a local `testacc` job because a live backend and coverage/diagnostics don't generalise. |
| [007](007-track-third-party-actions-with-dependabot.md) | Track third-party actions with Dependabot | Accepted | Enable Dependabot (`github-actions` ecosystem) to keep the reusable workflows' third-party actions current; each bump rides the moving `@v1` to the whole fleet. Distinct from this repo's own `@vN` versioning (moving branch + version-check, which Dependabot can't track); consumers add their own per-repo config for direct refs, ignoring `flungo/github-workflows`. |
| [008](008-secret-terraform-variables.md) | Inject secret Terraform variables via a masked env-var explosion | Accepted | Add an optional `tf_secret_vars` secret (a JSON map) to the Terraform workflows, exploded into masked `TF_VAR_*` env vars — chosen over a `*.auto.tfvars.json` file for masking-at-source, no on-disk secret, and an escape-safe `toJSON()` caller. Secret and non-secret vars travel distinct paths (the plain `tf_vars` input name is reserved); the step fails loud on bad input; plan-output redaction still needs `sensitive = true`. |
| [009](009-composite-action-via-workflow-identity-checkout.md) | Reference shared composite actions via a workflow-identity checkout | Accepted | Extract the duplicated TF_VAR export shell to the `export-terraform-variables` composite action, fetched by each Terraform job via a sparse checkout of this repo at `job.workflow_sha` — the workflow file's own commit — so the action always matches the ref the caller pinned and is testable from a feature branch (plus per-action self-CI in `self-action-tests.yml`), clearing ADR-008's deferral. |
| [010](010-caller-job-ids-match-the-workflow-filename.md) | A caller's job ID matches the reusable workflow's filename | Accepted | A check's context is `<caller job id> / <reusable job name>`, so the half an adopter types is part of the contract — and the runbooks' own examples were inconsistent, six of eight using a short generic word (`lint`, `links`, `ci`, `docs`, `release`, `drift`). A caller job ID is a repository-wide namespace, and those are exactly the names a repo wants for something else. The rule is now mechanical: job ID = the reusable workflow's filename without `.yml`, which makes the caller half predictable — what lets `terraform-github` hardcode the strings its `markdown` flag requires. Caller-side only, so nothing here changes behaviour and existing adopters realign at leisure; ADR-011 does the other half. |
| [011](011-reusable-job-ids-are-the-check-name.md) | A reusable job's ID is its check name | Accepted | Reusable jobs set no `name:`, so a job's ID is its check name — which, with ADR-010's caller-side rule, makes every context in the fleet derivable from a filename plus the job IDs inside it. It cuts **`v2`** — with ADR-012 and nothing else — because the contexts are contract: a renamed one fails a caller's branch protection silently, leaving a required check permanently pending rather than failing a run. The record carries the before/after context table, why it lands now rather than at a later major, why this reverses the earlier plan's rejection of the same idea, and what is lost with the prose check names. |
| [012](012-flungo-workflows-meta-workflow.md) | `version-check.yml` becomes `flungo-workflows.yml` | Accepted | `version-check.yml` becomes `flungo-workflows.yml` with `version-check` as a job inside it, giving the context `flungo-workflows / version-check`. The naming rules degenerate otherwise: `version` is not a family and the job is the whole concern, so both halves collapse into one word, and a caller job called `version-check` says nothing about *whose* version. The record covers why naming a workflow after the producer repository is accurate rather than odd, the rejected alternatives, and the runbook renames that follow; it rides `v2` with ADR-011 so consumers migrate once. |
| [013](013-per-major-upgrade-guide.md) | A per-major upgrade guide, scoped to breaking changes only | Accepted | `docs/reference/upgrading.md` carries one `## vN` section per major, recording only what breaks and what a consumer must do about it, and writing that section becomes a step in cutting a major. The scope rule follows from the moving-major model: a non-breaking change arrives automatically and leaves the reader nothing to act on, while a breaking one does not arrive at all until they act. The record covers why it is an upgrade guide rather than a changelog, the shape of a section, and why the version-check issue's deep links had to land on `v1` before the `v2` cut to reach anyone. |
| [014](014-promote-a-major-to-stable-by-hand.md) | A major is published by the cut and promoted to stable by hand | Accepted | Cutting a major publishes it but leaves it *settling*: `self-release.yml` gains `STABLE_MAJOR` alongside `MAJOR_BRANCH`, and a second, manual bump promotes it — which is what starts prompting consumers. A contract is only proved by adopting it, so the settling window lets a new major take corrections in place instead of forcing either a mega-pull-request or a `v3` for a mistake found on day two. The record covers what `version-check` compares against and how it fails towards prompting, why each upgrade-guide section is linked on its own major's branch, and the three alternatives it rejects — a fixed grace period, a long-lived settling branch, and moving the default branch. |
| [015](015-semantic-line-break-check.md) | Enforce the semantic line break MUST rule in its own workflow | Accepted | `markdown-sembr.yml` and the `check-semantic-line-breaks` action check the one hard sembr rule — a line break MUST follow a sentence — reporting two sentences on one source line and nothing else. The rest of the specification is SHOULD/MAY and needs the sentence understood, so it stays convention. A separate workflow rather than a `markdown-lint.yml` flag: default-on would break every consumer's prose without a major bump, and default-off would couple a house-style gate to the style-neutral linter, so adoption is the opt-in. Dependency-free Python, conservative where the source is ambiguous, and the tests' larger half asserts it stays quiet. |
| [016](016-sembr-inherits-markdownlint-ignores.md) | The semantic-line-break check inherits markdownlint's `ignores` | Accepted | Both Markdown checks must skip the same pre-canned data, but only the linter knew about it, so a repo stated the exclusion twice in two glob dialects and kept them in step by hand. The first consumer diverged immediately, and invisibly — its fixtures happened to be conformant, so the gap showed as a green build. The checker now reads `ignores` from the repo's markdownlint-cli2 config, on by default, translating globby's `**/` (zero or more directories) into this checker's bare-name form so an imported pattern does not quietly under-exclude. A config it cannot read, a mid-segment wildcard, and a negated entry are each reported rather than passed over. |
| [017](017-keep-home-grown-sembr-tooling-over-mdformat-sembr.md) | Keep the home-grown semantic-line-break tooling rather than adopting mdformat-sembr | Accepted | mdformat plus mdformat-sembr was evaluated as a replacement for both `sembr_check.py` and `reflow.py`, against the documented intent and the checker's unit-test cases. A formatter's `--check` is a whole-style gate with no finding position and no suppression, and the plugin collapses a paragraph before re-breaking it, so it joins the clause-level breaks the convention endorses — it undid 550 lines across the two already-conformant repos. Three bugs (hard breaks refuse the file, a sentence opening with a link or code span never breaks, non-ASCII capitals) are fixed in pull requests upstream rather than in a fork; the reflow is re-evaluated once upstream carries them and an insert-only mode. |
| [018](018-one-upsert-action-per-resource.md) | One marker-upsert action per resource, not one shared by both | Accepted | The marker upsert — find the thing carrying a hidden marker, then create it, update it in place, or retire it — is a composite action per resource: `issue-upsert` and `pr-comment-upsert`. One action for both would be two disjoint behaviours behind one name, since only a `paginate` and a `find` are common to them; leaving either inline leaves a copy no test reaches. The record sets out what the two resources share and what they do not, why the marker search stays duplicated, and the drift-issue behaviour the change carries with it. |

## Adding a new ADR

1. Create `docs/decisions/<NNN>-<kebab-case-title>.md` using the template below.
2. Update this index with a one-sentence summary.
3. If the new decision supersedes an existing one, update the older ADR's status to `Superseded by ADR-NNN`.

### ADR template

```markdown
# ADR-NNN: Title

- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Superseded by ADR-MMM | Deprecated

## Context

Why does this decision need to be made?

## Decision

What was decided?

## Consequences

What becomes easier or harder as a result.

### Positive

- ...

### Negative — trade-offs

- ...
```
