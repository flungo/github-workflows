# CLAUDE.md — github-workflows

Reusable GitHub Actions workflows and shared CI standards for `flungo`'s repositories.
Instead of copy-pasting CI, each repo calls these workflows via `workflow_call` and pins the moving `@v2` branch.
Three families:

- **Terraform** (`terraform.yml`, `terraform-drift.yml`) — for the Terraform repos (`terraform-grafana-cloud`, `terraform-github`, `terraform-cloudflare`, …).
- **Terraform provider** (`terraform-provider-test.yml`, `terraform-provider-docs.yml`, `terraform-provider-release.yml`) — for the Terraform provider repos (`terraform-provider-stalwart`, …); acceptance tests stay in each consumer as a local `testacc` job ([ADR-006](docs/decisions/006-terraform-provider-ci-family.md)).
- **Markdown** (`markdown-lint.yml`, `markdown-links.yml`) — repo-agnostic; for any repo with Markdown docs.
  `markdown-sembr.yml` joins the family but is **opt-in by adoption**: it is the one workflow here that imposes a prose style (one sentence per source line), so it stays a separate caller rather than a flag on `markdown-lint.yml` ([ADR-015](docs/decisions/015-semantic-line-break-check.md)).

## Repo layout

- `.github/workflows/*.yml` — the reusable workflows, plus this repo's own self-CI under a `self-` prefix (`self-ci.yml`, `self-action-tests.yml`, `self-release.yml`); an unprefixed file is one of the products and is therefore `workflow_call`-only, which `self-ci.yml`'s `workflow-scope` job enforces.
  `.github/actions/` — shared composite actions any of the reusable workflows can fetch at their own commit via `job.workflow_sha` ([ADR-009](docs/decisions/009-composite-action-via-workflow-identity-checkout.md)) — the Terraform family was the first consumer, `markdown-sembr.yml`, `flungo-workflows.yml` and `markdown-links.yml` followed; the pattern is not scoped to any of them.
  `issue-upsert` and `pr-comment-upsert` are the cross-family pair: every workflow that keeps a single marked issue or pull request comment in sync with a condition places it through one of them, and [ADR-018](docs/decisions/018-one-upsert-action-per-resource.md) records why that is two actions rather than one with a `resource:` switch.
- `docs/` follows the [Divio/Diátaxis](https://diataxis.fr/) split, matching the sibling repos — each subdirectory has a `README.md` index:
  - `reference/` — information-oriented lookup: `terraform-workflow.md` (the Terraform CI standard), `terraform-provider-workflow.md` (the provider CI standard) and `markdown-validation.md` (the Markdown workflows, for any repo, including what the semantic-line-break check deliberately does not flag).
  - `runbooks/` — repeatable how-to guides: `adopting-terraform-workflows.md`, `adopting-terraform-provider-workflows.md`, `adopting-markdown-workflows.md`, `adopting-flungo-workflows.md`, `releasing.md`.
  - `decisions/` — ADRs, numbered sequentially and never renumbered.
  - `plans/` — one-time procedures, tracked to completion then retired.
- House-style conventions, and the tooling that applies them, are **not** in this repo.
  Each workflow family has a matching standards plugin in the [`flungo-plugins` marketplace](https://github.com/flungo/claude-plugins) — `terraform-standards`, `terraform-provider-standards`, `markdown-standards` — so every family's workflows stay adoptable by a repo that wants none of the house style.
  `markdown-sembr.yml` is the single deliberate exception: a prose convention with one machine-decidable MUST rule, kept adoptable-by-omission by being its own caller ([ADR-015](docs/decisions/015-semantic-line-break-check.md)) rather than a flag on a style-neutral workflow.
  Adding a second such workflow needs the same argument made again, not this one cited.

## Conventions

- **The workflows are the product** — they contain no secrets; callers pass every credential.
  Keep them provider-agnostic (the Terraform provider token is a generic `provider_token` secret named by the caller's `tf-var-name` input).
  Never hard-code a repo, workspace, or token here.
- **Pin actions and version this repo.**
  Consumers pin `@v2` — a moving **branch**, not a tag ([ADR-003](docs/decisions/003-version-via-moving-v1-branch.md)).
  `self-release.yml` fast-forwards `v2` to `main` automatically on every merge, so fixes reach consumers with no bump step.
  A **breaking** input/secret change must bump `MAJOR_BRANCH` in `self-release.yml` (`v2` → `v3`) in the same PR — that reviewed one-line edit is the whole major-version decision, and it freezes the old major.
  It does **not** ask anyone to migrate: the cut leaves `STABLE_MAJOR` behind, and the new major *settles* — taking further breaking changes in place, with no consumer prompted onto it — until a second, manual bump of `STABLE_MAJOR` promotes it ([ADR-014](docs/decisions/014-promote-a-major-to-stable-by-hand.md)).
  So cut early and settle the contract by adopting it across the fleet; `self-ci.yml`'s `release-state` job warns on every PR while the two values differ, and the adoption docs are bumped by the promotion, not the cut.
  Never create a `vN` tag (`@vN` would then be ambiguous), and never push a `v*` branch directly — it moves only via `self-release.yml` or a PR that targets it.
  The whole `v[0-9]*` namespace is **create-restricted** to the release App, so never name a working branch `v3`, `v2x` or similar: the push is rejected, and the message won't say why.
  See [`docs/runbooks/releasing.md`](docs/runbooks/releasing.md); any change to inputs/secrets is a change to the contract — update the relevant adopting runbook and the consumers.
- **Every consumer adopts `flungo-workflows`.**
  Onboarding any consumer includes the opt-in [`flungo-workflows` caller](docs/runbooks/adopting-flungo-workflows.md), whose `version-check` job flags the repo — credential-free, via an issue in the repo itself — if a future major bump leaves it on a frozen `@vN`.
  Add it to every consumer we create, and to existing ones.
- **Names are the check contract.**
  A check context is `<caller job id> / <reusable job name>`, and both halves are fixed by convention so an adopter can derive them without running anything: a **caller's** job id is the reusable workflow's filename without `.yml` ([ADR-010](docs/decisions/010-caller-job-ids-match-the-workflow-filename.md)), and a **reusable** job never sets `name:`, so its job id is the check name ([ADR-011](docs/decisions/011-reusable-job-ids-are-the-check-name.md)).
  Job ids are short, kebab-case, and name the role within the workflow — the filename already carries the family, so don't repeat it (`markdown-links.yml`'s jobs are `internal` and `external`).
  Adding a `name:` to a reusable job silently renames a check and breaks any branch protection requiring it.
- **Validate before it reaches `main`.**
  `self-ci.yml` runs actionlint, the `workflow-scope` prefix guard and the repo's own Markdown checks on every PR; `self-action-tests.yml` gives every composite action its own isolated test job (colocated `test.sh` + a wiring smoke step, with a `coverage` guard so a new action can't land untested).
  The merge that passes them is what advances `v2`; a workflow change is not done until CI is green.
- **Git conventions** are the fleet standard, carried by the `git-conventions` plugin this repo enables: Conventional Commits, linear history, squash-vs-rebase, no fixup commits left on a branch, PR-only landing.
  Never commit directly to `main`; work on a feature branch and land via PR.

## Documentation standards

The `docs-standards` plugin carries these, and this repo enables it.
Three of its rules bite on almost every change here, so they are worth having in front of you:

- The Diátaxis split — docs are task-oriented (`runbooks/`), information-oriented (`reference/`), or decision-oriented (`decisions/`); plans (`plans/`) are one-time and retired when done.
- After any change under `docs/`, refresh that directory's `README.md` index in the same commit — a stale index row is actively misleading.
  A row is a pointer: what the document settles, and what a reader finds on opening it.
- After an architectural decision, add an ADR in `docs/decisions/` and a summary row to its `README.md`.

A new ADR copies the template in [`docs/decisions/README.md`](docs/decisions/README.md), which carries the plugin's canonical Nygard shape.

Prose under `docs/`, and the explanatory comments in the workflows and composite actions, follow the **instructional-writing** style in the `writing-styles` skill, which `docs-standards` brings with it.
State what is true now: what changed, and what it replaced, belong in the commit message and the ADR.

## Deferred follow-ups

Improvements intentionally not done yet.
Two of the three major-shaping items from the #23 review are still open, and all three are scoped in **[`docs/plans/v3-cut.md`](docs/plans/v3-cut.md)** — the plan is the source of truth for what rides the v3 cut (v2 was claimed by the ADR-010/011/012 naming changes), the pre-cut work on the current major, and each consumer's migration path:

- **Deprecate `tf-var-name` + `provider_token`** — deprecate-first: a current-major `::warning::` lands pre-cut, removal rides v3 (plan § scope item 1).
- **Consistent input naming** — kebab-case inputs, `UPPER_SNAKE_CASE` secrets; the renames ride v3 (plan § scope item 2).

The third — separating the products from the self-CI more visibly — is **done**: the `self-` prefix and the unprefixed-means-`workflow_call`-only guard landed pre-cut, behind a `version-check` reader that tolerates both release-workflow paths ([ADR-014](docs/decisions/014-promote-a-major-to-stable-by-hand.md), amended).
Renaming the products themselves (GitHub's `reusable-*` docs style) was reconsidered and re-rejected (plan § considered and rejected) — ADR-012's one-file `flungo-workflows.yml` rename is the recorded, forced exception.

## Active work

- [`docs/plans/v3-cut.md`](docs/plans/v3-cut.md) — the v3 major: pre-cut work on `v2`, the staged cut → settle → adopt → promote procedure ([ADR-014](docs/decisions/014-promote-a-major-to-stable-by-hand.md)), and the per-consumer migrations.
- [`docs/plans/mdformat-sembr-upstream-fixes.md`](docs/plans/mdformat-sembr-upstream-fixes.md) — track the mdformat-sembr patches and proposals open upstream, and the conditions under which [ADR-017](docs/decisions/017-keep-home-grown-sembr-tooling-over-mdformat-sembr.md) reopens the `reflow.py` question.

## Working in this repo with Claude Code

This repo adopts the fleet's standards plugins in [`.claude/settings.json`](.claude/settings.json) — `git-conventions`, `markdown-standards` and `docs-standards` from the `flungo-plugins` marketplace.
A local Claude Code session loads them; a **web session does not load a repo's adopted plugins at all**, so this file carries the rules that matter either way, each naming the plugin that owns the detail.

Run the Markdown checks locally before pushing, or you chase findings CI never raises and miss ones it does.
`markdown-standards` covers how, including where the linter version comes from: a recent `markdown-lint` job's log, never a version written down in a file.
This repo dogfoods its own workflows, so its `self-ci.yml` runs carry that job.

Its prose follows semantic line breaks — a `markdown-standards` prose convention — and `markdown-sembr.yml` enforces the MUST rule against this repo itself, so keep one sentence per source line in any Markdown you touch.

Use the GitHub MCP (`mcp__github__*`) for PRs, CI status, and comments — there is no `gh` CLI.
Trigger on-demand runs with `mcp__github__actions_run_trigger` (`workflow_id`, `ref`), surface the run URL (`https://github.com/flungo/github-workflows/actions/runs/<run_id>`), and report the outcome.
