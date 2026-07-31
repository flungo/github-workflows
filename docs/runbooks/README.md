# Runbooks

Step-by-step operational procedures for repeatable tasks — task-oriented how-to guides referenced indefinitely (no completion checkboxes). Contrast [`../plans/`](../plans/) (one-time procedures, retired when done) and [`../reference/`](../reference/) (information-oriented lookup).

| Document | Purpose |
| --- | --- |
| [`adopting-terraform-workflows.md`](adopting-terraform-workflows.md) | How a Terraform repo calls `terraform.yml` / `terraform-drift.yml` — inputs, secrets, and copy-paste callers |
| [`adopting-terraform-provider-workflows.md`](adopting-terraform-provider-workflows.md) | How a Terraform provider repo calls `terraform-provider-test.yml` / `terraform-provider-docs.yml` / `terraform-provider-release.yml` — inputs, secrets, copy-paste callers, and why acceptance tests stay local |
| [`adopting-markdown-workflows.md`](adopting-markdown-workflows.md) | How any repo adopts the Markdown lint/link workflows — callers, required permissions, per-repo config, token provisioning, verifying each check, and the adoption pitfalls; plus the optional `markdown-standards` plugin for Fabrizio's own conventions |
| [`adopting-version-check.md`](adopting-version-check.md) | How any consumer opts into the version check — a one-line caller that flags (via an issue in its own repo) when it's left pinning a now-frozen major; highly recommended |
| [`releasing.md`](releasing.md) | How `@vN` advances — automatic fast-forward on merge, cutting the next major by bumping `MAJOR_BRANCH` in a breaking PR, dry-run testing, branch protection and the release-push identity (the release App), and recovery |
