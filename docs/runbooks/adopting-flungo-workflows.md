# Adopting `flungo-workflows`

**Highly recommended for every consumer** — most of all when adopting your *first* `github-workflows` workflow, or in a repo that adopted one before this workflow existed.

`flungo-workflows.yml` collects the jobs that keep your repository's **relationship with `flungo/github-workflows`** healthy, as opposed to anything about your own code.
It is named for this repository because that is the family it describes; see [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md).
Today it holds one job, and it is the reason to adopt it.

## The caller

Add one scheduled caller:

```yaml
name: flungo/github-workflows
on:
  schedule:
    - cron: '0 7 * * 1'   # weekly
  workflow_dispatch:
jobs:
  flungo-workflows:
    permissions:
      contents: read
      issues: write
    uses: flungo/github-workflows/.github/workflows/flungo-workflows.yml@v2
```

**Name the calling job `flungo-workflows`** — the reusable workflow's filename without `.yml`, per [ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md).
That is what makes the reported context `flungo-workflows / version-check`.

**The `permissions:` block is required** — the version check upserts an issue in your repo, so the caller must grant `issues: write` (a reusable workflow's `permissions:` only cap the token).
It reads this public repo's majors with the same repo-scoped token, so no credential is needed.

## The jobs

### `version-check`

Context: `flungo-workflows / version-check`.

Once a repo pins `@vN`, a later major bump (a new `v<N+1>` branch) **freezes** the old major; this job is what stops the repo silently lagging on a release that no longer receives updates.

Running in your repo's context, it reads the majors you pin from your own workflow files, compares them to the latest major published in `flungo/github-workflows`, and opens — then auto-closes — a single migration issue in **your** repo when you're on a now-frozen major.
The issue links every [upgrade guide](../reference/upgrading.md) section between the major you pin and the current one, in order, so it tells you how to catch up and not merely that you are behind ([ADR-013](../decisions/013-per-major-upgrade-guide.md)).

Rationale: [ADR-004](../decisions/004-version-check-opt-in.md); how it fits releases: [`releasing.md` § Tracking consumer migration](releasing.md#tracking-consumer-migration).

## Required checks

Neither job here is a sensible required status check.
`version-check` runs on a schedule, not on a pull request, so requiring it would name a context that never reports on the branch being merged.
It surfaces its finding through an issue precisely so that it does not have to block anything.
