# ADR-009: Reference shared composite actions via a workflow-identity checkout

Date: 2026-07-30 Status: Accepted

## Context

ADR-008 left the "export the Terraform variables" shell (provider token + `tf_secret_vars`) duplicated across `terraform.yml` and `terraform-drift.yml`, deferring its extraction to a shared composite action: a reusable workflow cannot reference a co-located action by a local `./` path — that resolves against the *caller's* checkout — so the reference would have to be the full path `flungo/github-workflows/.github/actions/…@v1`, whose pinned ref creates a pre-merge testing chicken-and-egg (a feature branch's change to the action is not on `@v1` until it merges, so nothing can exercise it before it lands).
The deferral's exit condition was a way to exercise the shared action from a feature branch.

## Decision

Extract the shared step to the **`export-terraform-variables`** composite action (`.github/actions/export-terraform-variables/`, a thin `action.yml` over an `export.sh`), and reference it **without naming any ref at all**: each Terraform job first checks out this repo at the workflow file's own commit, using the `job` context's workflow-identity properties, then `uses:` the action from that checkout by workspace-local path:

```yaml
- name: Fetch workflow actions
  uses: actions/checkout@v7
  with:
    repository: ${{ job.workflow_repository }}
    ref: ${{ job.workflow_sha }}
    path: .github-workflows
    sparse-checkout: .github/actions
    persist-credentials: false

- name: Export Terraform variables
  uses: ./.github-workflows/.github/actions/export-terraform-variables
```

`job.workflow_sha` is the commit the running reusable-workflow file was fetched from, so the action is always the *same commit* as the workflow invoking it — `@v1` resolved at run start in production, or a feature branch when one is pinned for testing.
This is GitHub's documented pattern for a reusable workflow that needs files co-located with its own definition, and `job.workflow_repository` keeps the repo name out of the workflow (nothing self-referential to hard-code).

The action is exercised pre-merge two ways — the capability whose absence deferred the extraction:

- **Per-action self-CI.**
  Every composite action ships a colocated `test.sh` covering its behaviour (happy path and rejection cases), run as that action's own isolated job in [`action-tests.yml`](../../.github/workflows/action-tests.yml) together with a static wiring smoke step proving `action.yml` maps its inputs (a `uses:` reference cannot be templated, so each action adds one job following the same pattern; the local `./` reference is valid there, where the checkout *is* this repo).
  A `coverage` job fails when an action directory lacks an executable `test.sh` or a job in that file, so a new action cannot land untested.
  A PR touching an action fails its own CI before it can advance `v1`.
- **Consumer feature-branch runs.**
  Because the checkout follows `job.workflow_sha`, a consumer pinning `@<feature-branch>` exercises that branch's action end-to-end — not `@v1`'s.

One tooling note: actionlint's `job` context model does not yet include the workflow-identity properties, so [`.github/actionlint.yaml`](../../.github/actionlint.yaml) filters exactly that false positive, scoped to the Terraform workflows.

## Consequences

**Positive:**

- The secret-handling shell exists once.
  `terraform.yml` and `terraform-drift.yml` cannot drift apart, and a fix (or a new variable path) lands in one place.
- No ref skew is possible: workflow and action always come from the same commit, on `@v1` today, on a frozen major after a future bump, and on any feature branch under test — which clears ADR-008's deferral rather than working around it.
- The reference names no version, so a major bump needs no edit here.

**Negative / trade-offs:**

- Every Terraform job performs an extra checkout of this repo — shallow and sparse (`.github/actions` only), a few seconds — and a `.github-workflows/` directory appears in the job workspace.
  It sits outside the caller's module path and Terraform does not read it.
- `job.workflow_repository` / `job.workflow_sha` are not available on GitHub Enterprise Server; acceptable — the fleet runs on github.com.
- The actionlint ignore pattern must be kept narrow, and removed if/when actionlint learns these properties.
