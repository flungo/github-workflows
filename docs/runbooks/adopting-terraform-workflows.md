# Adopting the Terraform workflows

How a Terraform repo calls `terraform.yml` and `terraform-drift.yml`. Pin `@v1`. The workflows hold no secrets — the caller passes them. Repo-specific files (`*.tf`, the `terraform.tf` version pins) stay in the consumer. For the Markdown workflows (which any repo can also adopt), see [`adopting-markdown-workflows.md`](adopting-markdown-workflows.md).

> **Highly recommended:** also adopt the [version check](adopting-version-check.md) — a one-line opt-in caller that raises an issue in this repo if a future major bump ever leaves it pinning a frozen `@vN`. Especially worth it when this is the first `github-workflows` workflow the repo adopts.

## `terraform.yml`

### Inputs

| Input | Default | Purpose |
|---|---|---|
| `working-directory` | `.` | Root module directory (e.g. `owners/flungo` for a directory-per-owner repo) |
| `terraform-version` | `latest` | Passed to `setup-terraform` |
| `concurrency-group` | `terraform` | Share with the drift caller so plan/apply and drift never overlap |
| `plan-comment-marker` | `<!-- terraform-plan -->` | Hidden marker keying this repo's upserted plan comment |
| `plan-artifact-name` | `terraform-plan` | Name the plan (`plan.jsonl`, `plan.txt`) is uploaded under, for follow-on jobs to consume |
| `tf-var-name` | `''` | Env var name for the provider token, e.g. `TF_VAR_github_token` |
| `operation` | `plan` | Pass through the caller's `workflow_dispatch` operation |

### Secrets

| Secret | Required | Purpose |
|---|---|---|
| `TF_TOKEN_APP_TERRAFORM_IO` | yes | HCP state backend |
| `provider_token` | no | Provider credential, exported as `${tf-var-name}` |
| `tf_secret_vars` | no | JSON map `{"<var>":"<value>"}` of extra *secret* vars (string values), each exported as a masked `TF_VAR_<var>`; declare the consuming variable `sensitive` |

### Caller

```yaml
name: Terraform
on:
  pull_request: { branches: [main] }
  push: { branches: [main] }
  workflow_dispatch:
    inputs:
      operation: { description: Operation, required: true, default: plan, type: choice, options: [plan, apply] }
jobs:
  terraform:
    permissions:
      contents: read
      pull-requests: write
    uses: flungo/github-workflows/.github/workflows/terraform.yml@v1
    with:
      tf-var-name: TF_VAR_github_token
      operation: ${{ github.event.inputs.operation || 'plan' }}
    secrets:
      TF_TOKEN_APP_TERRAFORM_IO: ${{ secrets.TF_TOKEN_APP_TERRAFORM_IO }}
      provider_token: ${{ secrets.FLUNGO_GITHUB_TOKEN }}
```

**The `permissions:` block on the calling job is required, not optional.** A reusable workflow's own `permissions:` only *caps* the token; the caller grants it. If the repo's default `GITHUB_TOKEN` is read-only (a common hardening default), omitting this makes the run fail at startup (`startup_failure`) because the reusable workflow requests `pull-requests: write` (to upsert the plan comment) — more than the caller granted. `terraform.yml` needs `contents: read` + `pull-requests: write`; `terraform-drift.yml` needs `contents: read` + `issues: write`.

For a directory-per-owner repo, add `working-directory`, and set an owner-scoped `concurrency-group` and `plan-comment-marker` (e.g. `terraform-flungo`, `<!-- terraform-plan-flungo -->`).

To pass **extra secret variables** the config needs (beyond the provider token — e.g. a database password or an API key a resource needs), add the `tf_secret_vars` secret, assembling the JSON map inline from your own standalone secrets so each stays independently rotatable:

```yaml
    secrets:
      TF_TOKEN_APP_TERRAFORM_IO: ${{ secrets.TF_TOKEN_APP_TERRAFORM_IO }}
      provider_token: ${{ secrets.FLUNGO_GITHUB_TOKEN }}
      tf_secret_vars: >-
        {"db_password": ${{ toJSON(secrets.DB_PASSWORD) }}}
```

The workflow exports each entry as a masked `TF_VAR_<key>` (here `TF_VAR_db_password`). Use `toJSON(...)` so each value is correctly quoted and escaped into the JSON; values are strings (multi-line is fine). Only *secret* values belong in `tf_secret_vars` — every value is masked.

**Declare the consuming Terraform variable `sensitive = true`.** `::add-mask::` keeps each value out of the run *logs*, but the plan text also lands unmasked in the `terraform-plan` artifact and the upserted PR comment (and, from drift, in the `drift` issue) — only `sensitive` keeps a value out of plan output. If the repo also runs `terraform-drift.yml`, pass the same `tf_secret_vars` there too (below) so scheduled drift runs the same config rather than perpetually re-planning the missing variables.

### Consuming the plan artifact (follow-on jobs)

A job that `uses:` a reusable workflow can't add steps to it, so anything that must run *after* the plan lives in a **separate job** that `needs:` the caller's Terraform job and downloads the plan artifact (default name `terraform-plan` — see [the contract](../reference/terraform-workflow.md#plan-artifact)). Gate it on the Terraform job's `result` — and note the `always() &&`: a job whose `needs` failed is **skipped by default** unless its `if` uses a status function, so a bare `needs.terraform.result == 'failure'` self-skips in exactly the case (a failed plan) it exists to handle. Because the artifact is the only contract, upstream changes to the plan sequence never ripple into the follow-on job:

```yaml
jobs:
  terraform:
    uses: flungo/github-workflows/.github/workflows/terraform.yml@v1
    # ... with/secrets as above ...

  inspect:
    needs: terraform
    if: ${{ always() && needs.terraform.result == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v8
        with: { name: terraform-plan }
      - run: |
          plan="$(find . -name plan.jsonl -print -quit)"   # path depends on working-directory
          # plan.jsonl carries the JSON diagnostics from the failed plan:
          jq -rR 'fromjson? | select(.["@level"] == "error") | .diagnostic.summary' "$plan"
```

## `terraform-drift.yml`

Opt-in. Same `working-directory` / `terraform-version` / `concurrency-group` / `tf-var-name` inputs as above, plus `force_run` (boolean). Same secrets — **including `tf_secret_vars`**: if the config consumes extra secret values, mirror the `terraform.yml` caller's `tf_secret_vars` here, or scheduled drift will fail or perpetually re-plan the missing variables (and it pastes plan output into the `drift` issue, so the same `sensitive = true` guidance applies). The caller keeps the `schedule` trigger — reusable workflows can't be scheduled directly.

```yaml
name: Terraform Drift Remediation
on:
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:
    inputs:
      force_run: { description: Run even if paused, type: boolean, default: false }
jobs:
  drift:
    permissions:
      contents: read
      issues: write
    uses: flungo/github-workflows/.github/workflows/terraform-drift.yml@v1
    with:
      tf-var-name: TF_VAR_grafana_cloud_access_policy_token
      force_run: ${{ github.event.inputs.force_run == 'true' }}
    secrets:
      TF_TOKEN_APP_TERRAFORM_IO: ${{ secrets.TF_TOKEN_APP_TERRAFORM_IO }}
      provider_token: ${{ secrets.GRAFANA_CLOUD_ACCESS_POLICY_TOKEN }}
```

## Per-consumer notes

- **`terraform-grafana-cloud`** — calls `terraform.yml` and `terraform-drift.yml`; `tf-var-name: TF_VAR_grafana_cloud_access_policy_token`.
- **`terraform-github`** — calls `terraform.yml` with `working-directory: owners/flungo`, `concurrency-group: terraform-flungo`, `plan-comment-marker: <!-- terraform-plan-flungo -->`, `tf-var-name: TF_VAR_github_token`. No drift workflow. Adds a follow-on `inspect` job that consumes the plan artifact to surface classic branch protection blocking its branch-protection ruleset guard.
- **`stalwart.flungo.net`** — does **not** use these; its Terraform pipeline is bespoke (ephemeral-container tests, a LAN apply; see [ADR-001](../decisions/001-centralised-reusable-workflows.md)). It adopts only the Markdown workflows.
