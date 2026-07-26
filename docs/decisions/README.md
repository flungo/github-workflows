# Architecture Decision Records

Decisions are numbered sequentially and never deleted or renumbered. Each file documents the context, decision, and consequences for a key architectural choice. Superseded decisions keep their file and get a note at the top pointing to the newer ADR.

| # | Title | Status | Summary |
|---|---|---|---|
| [001](001-centralised-reusable-workflows.md) | Centralised reusable workflows | Accepted (versioning revised by ADR-003) | Extract the fleet's copy-pasted CI into `workflow_call` reusable workflows in this public repo — a Terraform family (plan/apply, drift) and a repo-agnostic Markdown family. Consumers call them and pin the moving `v1` ref; secrets stay with callers; stalwart's bespoke Terraform pipeline is exempt. |
| [002](002-markdown-validation-tooling.md) | Markdown validation tooling | Accepted | lychee (Rust) for all link + anchor resolution (offline internal PR check + online external sweep); markdownlint-cli2 for style; remark-validate-links the documented fallback if lychee's GitHub-slugger parity ever fails. Rejects markdown-link-check, remark-lint-for-style, and SSG strict modes. |
| [003](003-version-via-moving-v1-branch.md) | Version via a moving major branch, advanced automatically | Accepted | Version the reusable workflows with a moving major **branch** rather than a `v1` tag: consumers still pin `@v1`, but `release.yml` fast-forwards it to `main` on every merge; a breaking change cuts the next major by bumping `MAJOR_BRANCH` in that workflow (freezing the old major). Revises ADR-001's tag mechanism. |
| [004](004-version-check-opt-in.md) | Opt-in consumer version check | Accepted | Surface a consumer that pins a now-frozen major via an opt-in reusable `version-check.yml`: each consumer runs it on a schedule, comparing its own pins to the latest published major and opening/closing a tracking issue in its own repo — no cross-owner credential. Supersedes ADR-001's Renovate/Dependabot follow-up; producer-side rollup census left out of scope. |
| [005](005-extend-terraform-workflow-via-plan-artifact.md) | Extend the Terraform workflow via a published plan artifact | Accepted | The Terraform workflow publishes its plan (`plan.jsonl`/`plan.txt`) as an artifact so consumers can extend it with a *separate* job (`needs:` the caller job, gated on its `result`) that consumes the plan — reusable workflows can't take injected steps, and the artifact contract avoids the drift of forking or re-orchestrating. |
| [006](006-terraform-provider-ci-family.md) | A reusable CI family for the Terraform providers | Accepted | Centralise the standard provider scaffold's CI — build/lint/test + docs-sync (`terraform-provider-test.yml`), docs regenerate-and-commit (`terraform-provider-docs.yml`), GoReleaser publish (`terraform-provider-release.yml`) — as a third reusable family; acceptance tests stay in each consumer as a local `testacc` job because a live backend and coverage/diagnostics don't generalise. |
| [007](007-track-third-party-actions-with-dependabot.md) | Track third-party actions with Dependabot | Accepted | Enable Dependabot (`github-actions` ecosystem) to keep the reusable workflows' third-party actions current; each bump rides the moving `@v1` to the whole fleet. Distinct from this repo's own `@vN` versioning (moving branch + version-check, which Dependabot can't track); consumers add their own per-repo config for direct refs, ignoring `flungo/github-workflows`. |

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
