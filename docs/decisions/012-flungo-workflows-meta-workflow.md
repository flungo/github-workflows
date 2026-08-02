# ADR-012: `version-check.yml` becomes `flungo-workflows.yml`, a workflow every adopter runs

Date: 2026-08-02 Status: Accepted

## Context

[ADR-010](010-caller-job-ids-match-the-workflow-filename.md) makes a caller's job ID the reusable workflow's filename, and [ADR-011](011-reusable-job-ids-are-the-check-name.md) makes a reusable job's ID its check name.
Applying both to `version-check.yml` gives the context `version-check / version-check`, which is where the naming rules stop helping.

The problem is the filename.
Every other workflow here is named for a **family** — `terraform`, `terraform-provider`, `markdown` — and the job names the role within it.
`version` is not a family, and `version-check` is not a role within one; it is the entire concern, so the two halves collapse into the same word.

It is also ambiguous in the namespace ADR-010 cares about.
A caller job called `version-check` says nothing about *whose* version, in a repository that may well check versions of other things — a provider, a Go toolchain, a container base image.
`terraform-drift` reads as "this repo's Terraform drift"; `version-check` does not identify what it belongs to.

Underneath the naming there is a scope question.
[ADR-004](004-version-check-opt-in.md) built this workflow for one job: tell a consumer when the major it pins has frozen.
That is the first of a class — things every repository consuming this one should run to keep its *relationship with this repository* healthy — not a category of one.
There is currently nowhere for the second such job to go except a new top-level workflow with the same naming problem.

## Decision

**Rename `version-check.yml` to `flungo-workflows.yml`, keeping `version-check` as a job inside it.**

The context becomes **`flungo-workflows / version-check`**: the workflow names the family — this repository, and a consumer's relationship to it — and the job names the role, exactly as `markdown-links / internal` does.

```yaml
jobs:
  flungo-workflows:                                                  # ADR-010
    uses: flungo/github-workflows/.github/workflows/flungo-workflows.yml@v2
```

Naming a workflow after the producer repository is unusual, and is the right description here.
These jobs are not about the consumer's own code — they are about whether the consumer is still correctly wired to `flungo/github-workflows`.
That is a coherent family with an obvious name, and it is the only family whose name is a proper noun for good reason.

The [`v2` plan](https://github.com/flungo/github-workflows/pull/27) rejected renaming products, and this is not a reversal of that: it re-rejected the *cosmetic* rename — a `reusable-*` prefix applied across the board for visible separation — on the grounds that a filename is the pinned contract path and the gain was presentational.
This rename is not presentational.
It is forced by [ADR-010](010-caller-job-ids-match-the-workflow-filename.md) and [ADR-011](011-reusable-job-ids-are-the-check-name.md) producing a degenerate context here, and it applies to one file rather than all of them.
The plan's own point stands for the rest: no other product is renamed.

The alternatives are worse in ways worth recording.
`workflows-version-check` still does not say whose.
`flungo-workflows-version-check` says it, but restates the family in every job and leaves a second job with an even longer name.
Both also keep the file single-purpose, which is the thing that needed fixing.

### The scope broadens, and the documentation follows

`version-check` stops being the workflow and becomes *a* job in it.
ADR-004's mechanism is untouched — still opt-in, still per-consumer, still opening and closing an issue in the consumer's own repository — but its packaging changes, and so does what the docs are about:

- `docs/runbooks/adopting-version-check.md` becomes `adopting-flungo-workflows.md`, describing the caller and the jobs it runs, with the version check as the first of them.
- The other runbooks' "also adopt the version check" recommendation becomes "also adopt `flungo-workflows`".
- [ADR-004](004-version-check-opt-in.md) gains a pointer here, since its title and body describe a workflow that will no longer exist under that name.
  That pointer is added in the pull request carrying this ADR rather than at the cut: it costs nothing to be early, and an ADR describing a renamed thing with no forward reference is exactly the stale-doc problem the index is meant to prevent.

A future job in this file — anything every adopter should run — is then an addition to an existing workflow and runbook rather than a new top-level concern needing its own name.

### It rides `v2`

A workflow filename is part of a caller's `uses:` line, so renaming it breaks every existing caller outright — a harder break than ADR-011's, which only breaks branch protection.
Both land in the same major, so a consumer migrates once: bump `@v1` to `@v2`, rename the caller job IDs, and point the `uses:` at the new filename.

Doing this in a different major from ADR-011 would mean two migrations for the six repositories that call this workflow, for no benefit.

`v1` keeps `version-check.yml` under its old name, unchanged and frozen, so nothing breaks until a consumer chooses to move.

## Consequences

**Positive:**

- The naming rules produce a sensible context here rather than the degenerate `version-check / version-check`.
- A caller job ID that identifies what it belongs to, in the repository-wide namespace ADR-010 is about.
- There is now a home for the next "every adopter should run this" job, so adding one is not another naming decision.
- Consumers migrate once for both this and ADR-011.

**Negative / trade-offs:**

- **A workflow named after a repository** is unconventional, and will read oddly to anyone who meets it before reading this.
  Mitigated by the runbook, and accepted because it is accurate.
- **Every one of the six consumers must edit its `uses:` line**, not merely its job ID — the largest per-consumer change in this major.
- **ADR-004's title now describes something renamed.**
  The ADR is not superseded — its decision stands — so it keeps its file and gets a pointer here rather than a status change.
- **The file could accumulate unrelated jobs** on the strength of "every adopter runs it".
  The bar is that a job belongs here only if it concerns the consumer's relationship *with this repository*; anything about the consumer's own code belongs to a family of its own.
