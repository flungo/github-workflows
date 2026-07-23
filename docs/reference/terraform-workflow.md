# The Terraform CI workflow standard

The contract the `flungo` Terraform repositories follow by calling the **Terraform** reusable workflows in this repo. Consumer `CLAUDE.md` files point here rather than restating it. For the concrete inputs, secrets, and caller snippets, see [`adopting-terraform-workflows.md`](../runbooks/adopting-terraform-workflows.md). Markdown validation is a separate, repo-agnostic family — see [`markdown-validation.md`](markdown-validation.md).

## Execution model — HCP Terraform, Local execution

State lives in HCP Terraform (org `flungo`), in **Local execution mode**: HCP provides state, locking, and run history only. GitHub Actions (the runner) is the executor — it runs `terraform plan`/`apply` with the provider and backend credentials in its environment. This is why credentials live in GitHub Actions secrets, not HCP workspace variables, and why a plan can run against live infrastructure from the runner.

## Workflows & triggers

| Workflow | Trigger | Effect |
|---|---|---|
| [`terraform.yml`](../../.github/workflows/terraform.yml) | `pull_request` | `plan`; posts/updates a plan comment on the PR |
| `terraform.yml` | `push` to the default branch | `apply` |
| `terraform.yml` | `workflow_dispatch` (`plan`/`apply`) | on-demand plan or apply |
| [`terraform-drift.yml`](../../.github/workflows/terraform-drift.yml) | daily `schedule` (on the caller) | apply the default branch to remediate drift; open/close a `drift` issue |

The PR plan comment is upserted (found and updated via a hidden marker), so a PR carries a single, current plan rather than a growing stack of comments. `fmt` and `validate` outcomes are surfaced in the comment's table; a `fmt` failure is reported but does not fail the run.

## Secret model

- All credentials are **GitHub Actions secrets**, never HCP workspace variables.
- `TF_TOKEN_APP_TERRAFORM_IO` authenticates the HCP state backend (shared, org-wide).
- The **provider token** is passed generically: the caller sets the `tf-var-name` input (e.g. `TF_VAR_github_token`) and supplies the `provider_token` secret; the workflow exports it under that name for Terraform. The provider token is **never Terraform-managed** — a broken apply must not be able to lock a repo out of its own credentials.

## Drift remediation & pausing

`terraform-drift.yml` applies the default branch on a daily schedule so live state cannot silently diverge — valuable mainly where auto-rotating credentials must stay authoritative, so it is **opt-in**. It never auto-applies destroys (it opens a review issue instead), opens a `drift`-labelled issue when it remediates, and closes those issues on a clean run.

Two ways to pause it, both read from the caller repo:

- **`DRIFT_REMEDIATION_PAUSED` repository variable** — quick, unaudited emergency brake.
- **A committed `.drift-paused` file** at the repo root — auditable, reviewed in the diff. Use it for a change set spanning multiple PRs: add it in the first PR, remove it in the last.

A `workflow_dispatch` with `force_run: true` overrides both. Default to *not* pausing: a change that will be merged gets applied anyway, so an extra scheduled apply is rarely a problem — reach for a pause only when the default branch will be knowingly divergent for a meaningful window.

## Triggering runs from Claude Code

Sessions use the GitHub MCP — there is no `gh` CLI. Trigger on-demand runs with `mcp__github__actions_run_trigger` (`workflow_id`, `ref`), give the user the run URL (`https://github.com/flungo/<repo>/actions/runs/<run_id>`), then report the outcome.

## Adoption & versioning

Consumers call each workflow with `uses: flungo/github-workflows/.github/workflows/<name>@v1` and pass their inputs/secrets — see [`adopting-terraform-workflows.md`](../runbooks/adopting-terraform-workflows.md). `@v1` is a moving **branch**, not a tag ([ADR-003](../decisions/003-version-via-moving-v1-branch.md)): it advances automatically on every merge to `main`, and a breaking input/secret change cuts a new major branch (`v2`) — see [`releasing.md`](../runbooks/releasing.md). Anything repo-specific — `*.tf`, the `terraform.tf` version pins, and the secrets themselves — stays in the consumer.
