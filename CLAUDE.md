# CLAUDE.md — github-workflows

Reusable GitHub Actions workflows and shared CI standards for `flungo`'s repositories. Instead of copy-pasting CI, each repo calls these workflows via `workflow_call` and pins a tag. Two families:

- **Terraform** (`terraform.yml`, `terraform-drift.yml`) — for the Terraform repos (`terraform-grafana-cloud`, `terraform-github`, `terraform-cloudflare`, …).
- **Markdown** (`markdown-lint.yml`, `markdown-links.yml`) — repo-agnostic; for any repo with Markdown docs.

## Repo layout

- `.github/workflows/*.yml` — the reusable workflows and this repo's own self-CI (`ci.yml`).
- `docs/` follows the [Divio/Diátaxis](https://diataxis.fr/) split, matching the sibling repos — each subdirectory has a `README.md` index:
  - `reference/` — information-oriented lookup: `terraform-workflow.md` (the Terraform CI standard) and `markdown-validation.md` (the Markdown workflows, for any repo).
  - `runbooks/` — repeatable how-to guides: `adopting-terraform-workflows.md`, `adopting-markdown-workflows.md`.
  - `decisions/` — ADRs, numbered sequentially and never renumbered.
  - `plans/` — one-time procedures, tracked to completion then retired.
- `scripts/` — helper scripts referenced by the runbooks (e.g. `reflow.py`, the render-gated semantic-line-break reflow used when adopting the Markdown workflows).

## Conventions

- **The workflows are the product** — they contain no secrets; callers pass every credential. Keep them provider-agnostic (the Terraform provider token is a generic `provider_token` secret named by the caller's `tf-var-name` input). Never hard-code a repo, workspace, or token here.
- **Pin actions and version this repo.** Consumers pin `@v1`; move the `v1` tag forward for fixes, a new major tag for breaking changes. Any change to inputs/secrets is a change to the contract — update the relevant adopting runbook and the consumers.
- **Validate before tagging.** `ci.yml` runs actionlint and the repo's own Markdown checks on every PR. A workflow change is not done until CI is green.
- **Git & docs conventions** follow the fleet standard (Conventional Commits, linear history, squash-vs-rebase, no fixup commits, PR-only landing) — the same as the consumer repos and Fabrizio's `code-review-workflow` skill. Never commit directly to `main`; work on a feature branch and land via PR.

## Documentation standards

Same rules as the sibling repos, following the Diátaxis split: docs are task-oriented (`runbooks/`), information-oriented (`reference/`), or decision-oriented (`decisions/`); plans (`plans/`) are one-time and retired when done. After any change under `docs/`, refresh the relevant `README.md` index in the same commit — a stale index row is actively misleading. After an architectural decision, add an ADR in `docs/decisions/` and a one-line summary to its `README.md`.

## Working in this repo with Claude Code

Use the GitHub MCP (`mcp__github__*`) for PRs, CI status, and comments — there is no `gh` CLI. Trigger on-demand runs with `mcp__github__actions_run_trigger` (`workflow_id`, `ref`), surface the run URL (`https://github.com/flungo/github-workflows/actions/runs/<run_id>`), and report the outcome.
