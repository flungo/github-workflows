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
    uses: flungo/github-workflows/.github/workflows/terraform.yml@v1
    with:
      tf-var-name: TF_VAR_github_token
      operation: ${{ github.event.inputs.operation || 'plan' }}
    secrets:
      TF_TOKEN_APP_TERRAFORM_IO: ${{ secrets.TF_TOKEN_APP_TERRAFORM_IO }}
      provider_token: ${{ secrets.FLUNGO_GITHUB_TOKEN }}
```

For a directory-per-owner repo, add `working-directory`, and set an owner-scoped `concurrency-group` and `plan-comment-marker` (e.g. `terraform-flungo`, `<!-- terraform-plan-flungo -->`).

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
- **`terraform-github`** — calls `terraform.yml` with `working-directory: owners/flungo`, `concurrency-group: terraform-flungo`, `plan-comment-marker: <!-- terraform-plan-flungo -->`, `tf-var-name: TF_VAR_github_token`. No drift workflow.
- **`stalwart.flungo.net`** — does **not** use these; its Terraform pipeline is bespoke (ephemeral-container tests, a LAN apply; see [ADR-001](../decisions/001-centralised-reusable-workflows.md)). It adopts only the Markdown workflows.
