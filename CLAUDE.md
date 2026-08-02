# CLAUDE.md — github-workflows

Reusable GitHub Actions workflows and shared CI standards for `flungo`'s repositories. Instead of copy-pasting CI, each repo calls these workflows via `workflow_call` and pins the moving `@v2` branch. Three families:

- **Terraform** (`terraform.yml`, `terraform-drift.yml`) — for the Terraform repos (`terraform-grafana-cloud`, `terraform-github`, `terraform-cloudflare`, …).
- **Terraform provider** (`terraform-provider-test.yml`, `terraform-provider-docs.yml`, `terraform-provider-release.yml`) — for the Terraform provider repos (`terraform-provider-stalwart`, …); acceptance tests stay in each consumer as a local `testacc` job ([ADR-006](docs/decisions/006-terraform-provider-ci-family.md)).
- **Markdown** (`markdown-lint.yml`, `markdown-links.yml`) — repo-agnostic; for any repo with Markdown docs.

## Repo layout

- `.github/workflows/*.yml` — the reusable workflows and this repo's own self-CI (`ci.yml`, `action-tests.yml`); `.github/actions/` — shared composite actions any of the reusable workflows can fetch at their own commit via `job.workflow_sha` ([ADR-009](docs/decisions/009-composite-action-via-workflow-identity-checkout.md)) — the Terraform family is the first consumer, not the scope.
- `docs/` follows the [Divio/Diátaxis](https://diataxis.fr/) split, matching the sibling repos — each subdirectory has a `README.md` index:
  - `reference/` — information-oriented lookup: `terraform-workflow.md` (the Terraform CI standard), `terraform-provider-workflow.md` (the provider CI standard) and `markdown-validation.md` (the Markdown workflows, for any repo).
  - `runbooks/` — repeatable how-to guides: `adopting-terraform-workflows.md`, `adopting-terraform-provider-workflows.md`, `adopting-markdown-workflows.md`, `adopting-flungo-workflows.md`, `releasing.md`.
  - `decisions/` — ADRs, numbered sequentially and never renumbered.
  - `plans/` — one-time procedures, tracked to completion then retired.
- House-style conventions, and the tooling that applies them, are **not** in this repo. Each workflow family has a matching standards plugin in the [`flungo-plugins` marketplace](https://github.com/flungo/claude-plugins) — `terraform-standards`, `terraform-provider-standards`, `markdown-standards` — so every family's workflows stay adoptable by a repo that wants none of the house style.

## Conventions

- **The workflows are the product** — they contain no secrets; callers pass every credential. Keep them provider-agnostic (the Terraform provider token is a generic `provider_token` secret named by the caller's `tf-var-name` input). Never hard-code a repo, workspace, or token here.
- **Pin actions and version this repo.** Consumers pin `@v2` — a moving **branch**, not a tag ([ADR-003](docs/decisions/003-version-via-moving-v1-branch.md)). `release.yml` fast-forwards `v2` to `main` automatically on every merge, so fixes reach consumers with no bump step. A **breaking** input/secret change must bump `MAJOR_BRANCH` in `release.yml` (`v2` → `v3`) in the same PR — that reviewed one-line edit is the whole major-version decision, and it freezes the old major. Never create a `vN` tag (`@vN` would then be ambiguous), and never push a `v*` branch directly — it moves only via `release.yml` or a PR that targets it. The whole `v[0-9]*` namespace is **create-restricted** to the release App, so never name a working branch `v3`, `v2x` or similar: the push is rejected, and the message won't say why. See [`docs/runbooks/releasing.md`](docs/runbooks/releasing.md); any change to inputs/secrets is a change to the contract — update the relevant adopting runbook and the consumers.
- **Every consumer adopts `flungo-workflows`.** Onboarding any consumer includes the opt-in [`flungo-workflows` caller](docs/runbooks/adopting-flungo-workflows.md), whose `version-check` job flags the repo — credential-free, via an issue in the repo itself — if a future major bump leaves it on a frozen `@vN`. Add it to every consumer we create, and to existing ones.
- **Names are the check contract.** A check context is `<caller job id> / <reusable job name>`, and both halves are fixed by convention so an adopter can derive them without running anything: a **caller's** job id is the reusable workflow's filename without `.yml` ([ADR-010](docs/decisions/010-caller-job-ids-match-the-workflow-filename.md)), and a **reusable** job never sets `name:`, so its job id is the check name ([ADR-011](docs/decisions/011-reusable-job-ids-are-the-check-name.md)). Job ids are short, kebab-case, and name the role within the workflow — the filename already carries the family, so don't repeat it (`markdown-links.yml`'s jobs are `internal` and `external`). Adding a `name:` to a reusable job silently renames a check and breaks any branch protection requiring it.
- **Validate before it reaches `main`.** `ci.yml` runs actionlint and the repo's own Markdown checks on every PR; `action-tests.yml` gives every composite action its own isolated test job (colocated `test.sh` + a wiring smoke step, with a `coverage` guard so a new action can't land untested). The merge that passes them is what advances `v2`; a workflow change is not done until CI is green.
- **Git & docs conventions** follow the fleet standard (Conventional Commits, linear history, squash-vs-rebase, no fixup commits, PR-only landing) — the same as the consumer repos and Fabrizio's `code-review-workflow` skill. Never commit directly to `main`; work on a feature branch and land via PR.

## Documentation standards

Same rules as the sibling repos, following the Diátaxis split: docs are task-oriented (`runbooks/`), information-oriented (`reference/`), or decision-oriented (`decisions/`); plans (`plans/`) are one-time and retired when done. After any change under `docs/`, refresh the relevant `README.md` index in the same commit — a stale index row is actively misleading. After an architectural decision, add an ADR in `docs/decisions/` and a one-line summary to its `README.md`.

## Deferred follow-ups

Improvements intentionally not done yet:

- **Deprecate `tf-var-name` + `provider_token`.** The bespoke provider-token pair predates `tf_secret_vars` and was poorly designed from the start (review of #23): a provider token is just one more secret variable, so a `tf_secret_vars` entry already achieves the same masked `TF_VAR_*` export without the caller naming an env var. A later PR should design the migration path — every Terraform consumer moves off the pair, and removal is a breaking contract change (`v3`, or a deprecation-warning period on `v2` first).
- **Consistent input naming.** The workflow inputs mix kebab case (`tf-var-name`, `working-directory`, `terraform-version`, `concurrency-group`, `plan-comment-marker`) and snake case (`tf_vars`, `tf_secret_vars`, `force_run`) (review of #23). Converging on one convention renames inputs — a breaking contract change — so fold it into the same `v3` design as the deprecation above.
- **Separate the products from the self-CI more visibly.** GitHub discovers workflows only flat in `.github/workflows/` (no subdirectories), so the reusable products and the self-CI (`ci.yml`, `action-tests.yml`, `release.yml`) can only be separated by naming and docs — the status quo everywhere, but worth tightening (#23 follow-up). A product's filename is its public contract (consumers pin the full path), so the convention burdens the *internal* files: a **`self-` prefix** (`self-ci.yml`, `self-action-tests.yml`, `self-release.yml`) — it takes the slot the product family name occupies on the other filenames, and the rename is non-breaking, any time. Ideally add a self-CI guard asserting unprefixed workflows are `workflow_call`-only (accommodating the dogfooded Markdown calls). Renaming the products themselves (GitHub's `reusable-*` docs style) is a breaking contract change that would have to ride the `v3` batch above.

## Working in this repo with Claude Code

Use the GitHub MCP (`mcp__github__*`) for PRs, CI status, and comments — there is no `gh` CLI. Trigger on-demand runs with `mcp__github__actions_run_trigger` (`workflow_id`, `ref`), surface the run URL (`https://github.com/flungo/github-workflows/actions/runs/<run_id>`), and report the outcome.
