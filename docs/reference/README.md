# Reference

Information-oriented lookup docs — descriptive, not procedural. If it has no steps and exists to be looked up, it goes here. Contrast [`../runbooks/`](../runbooks/) (repeatable how-to guides) and [`../decisions/`](../decisions/) (ADRs).

| Document | Purpose |
|---|---|
| [`terraform-workflow.md`](terraform-workflow.md) | The Terraform CI contract the Terraform repos follow — triggers, the HCP Local-execution model, the secret model, and drift-pause behaviour |
| [`terraform-provider-workflow.md`](terraform-provider-workflow.md) | The provider CI contract the Terraform provider repos follow — build/lint/test, the docs regenerate-and-check model, the release/signing model, and why acceptance tests stay in the consumer |
| [`markdown-validation.md`](markdown-validation.md) | The Markdown lint/link workflows — repo-agnostic; for any repo with docs, not just Terraform ones |
