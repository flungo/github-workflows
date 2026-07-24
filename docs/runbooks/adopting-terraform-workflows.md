# Adopting the Terraform workflows

How a Terraform repo calls `terraform.yml` and `terraform-drift.yml`. Pin `@v1`. The workflows hold no secrets — the caller passes them. Repo-specific files (`*.tf`, the `terraform.tf` version pins) stay in the consumer. For the Markdown workflows (which any repo can also adopt), see [`adopting-markdown-workflows.md`](adopting-markdown-workflows.md).

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

### Consuming the plan artifact (follow-on jobs)

A job that `uses:` a reusable workflow can't add steps to it, so anything that must run *after* the plan lives in a **separate job** that `needs:` the caller's Terraform job and downloads the plan artifact (default name `terraform-plan` — see [the contract](../reference/terraform-workflow.md#plan-artifact)). Gate it on the Terraform job's `result` (available even on failure), so upstream changes to the plan sequence never ripple into the follow-on job — the artifact is the only contract:

```yaml
jobs:
  terraform:
    uses: flungo/github-workflows/.github/workflows/terraform.yml@v1
    # ... with/secrets as above ...

  inspect:
    needs: terraform
    if: needs.terraform.result == 'failure'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with: { name: terraform-plan }
      - run: |
          plan="$(find . -name plan.jsonl -print -quit)"   # path depends on working-directory
          # plan.jsonl carries the JSON diagnostics from the failed plan:
          jq -rR 'fromjson? | select(.["@level"] == "error") | .diagnostic.summary' "$plan"
```

## `terraform-drift.yml`

Opt-in. Same `working-directory` / `terraform-version` / `concurrency-group` / `tf-var-name` inputs as above, plus `force_run` (boolean). Same secrets. The caller keeps the `schedule` trigger — reusable workflows can't be scheduled directly.

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
