# ADR-011: A reusable job's ID is its check name, and that lands as `v2`

Date: 2026-08-02
Status: Proposed

## Context

[ADR-010](010-caller-job-ids-match-the-workflow-filename.md) fixed the left-hand half of a check context — the caller's job ID — by making it the reusable workflow's filename. It deliberately left the right-hand half alone, and that half is in worse shape.

A context is `<caller job id> / <reusable job name>`, where "name" means the job's `name:` if it sets one and its job ID otherwise. This repository is inconsistent about which:

| Workflow | Job ID | `name:` | Right-hand half |
| --- | --- | --- | --- |
| `terraform.yml` | `terraform` | — | `terraform` |
| `terraform-drift.yml` | `drift` | — | `drift` |
| `version-check.yml` | `version-check` | — | `version-check` |
| `terraform-provider-test.yml` | `build`, `lint`, `test`, `docs` | — | as the IDs |
| `terraform-provider-docs.yml` | `generate` | — | `generate` |
| `terraform-provider-release.yml` | `goreleaser` | — | `goreleaser` |
| `markdown-lint.yml` | `lint` | `markdownlint` | `markdownlint` |
| `markdown-links.yml` | `internal` | `Internal links & anchors` | `Internal links & anchors` |
| `markdown-links.yml` | `external` | `External URLs` | `External URLs` |

Nine of twelve are bare job IDs; three are prose. So the full contexts range from `terraform / terraform` to `markdown-links / Internal links & anchors` — the latter carrying spaces, capitals and an ampersand.

That matters because these strings are no longer only decorative. `terraform-github` hardcodes them: its `standard-repository` module writes required check contexts into GitHub rulesets from string literals in Terraform. A context with a `&` in it is a string to be copied exactly and never typed from memory, and — worse — **it is not derivable**. An adopter can read a workflow's filename and, via ADR-010, know the caller half; the reusable half can only be discovered by running the workflow and reading the check.

ADR-010 documents that trap rather than fixing it, on the grounds that renaming the reusable jobs would break every consumer's required checks at once. That reasoning is sound in isolation and wrong in context: this repository has a mechanism for exactly that, and is not yet using it.

## Decision

**A reusable workflow's jobs do not set `name:`. The job ID is the identifier, and it is short, lowercase and hyphen-separated, describing the job's role within its own workflow.**

The workflow filename already carries the family (ADR-010 puts it on the left of the slash), so the job ID does not repeat it. `markdown-links.yml`'s jobs are `internal` and `external`, not `markdown-links-internal`.

With ADR-010, every context in the fleet becomes mechanically derivable from two things an adopter can read without running anything: the workflow's filename, and the job IDs inside it.

| Workflow | Context before | Context after |
| --- | --- | --- |
| `terraform.yml` | `terraform / terraform` | `terraform / terraform` — **unchanged** |
| `terraform-drift.yml` | `drift / drift` | `terraform-drift / drift` |
| `markdown-lint.yml` | `lint / markdownlint` | `markdown-lint / lint` |
| `markdown-links.yml` | `links / Internal links & anchors` | `markdown-links / internal` |
| `markdown-links.yml` | `links / External URLs` | `markdown-links / external` |
| `terraform-provider-test.yml` | `ci / build` (etc.) | `terraform-provider-test / build` (etc.) |
| `terraform-provider-docs.yml` | `docs / generate` | `terraform-provider-docs / generate` |
| `terraform-provider-release.yml` | `release / goreleaser` | `terraform-provider-release / goreleaser` |
| `version-check.yml` | `version-check / version-check` | `flungo-workflows / version-check` ([ADR-012](012-flungo-workflows-meta-workflow.md)) |

Every context becomes lowercase, space-free and punctuation-free. `terraform / terraform` survives untouched, so the one family whose context is already required across the fleet needs no migration at all.

### This is a breaking change, and it cuts `v2`

The check contexts a workflow reports are part of its contract, even though [`releasing.md`](../runbooks/releasing.md) does not currently list them: its definition of breaking is "renaming or removing an input, adding a required secret, or changing a workflow's default behaviour". A renamed context does not fail a caller's *run* — it fails the caller's *branch protection*, silently, by leaving a required check permanently pending.

That is breaking in every sense that matters, so this lands as the **`v2` cut** ([ADR-003](003-version-via-moving-v1-branch.md)): `MAJOR_BRANCH` moves to `v2` in the same pull request, `@v1` freezes, and consumers migrate deliberately. `releasing.md` gains reported check contexts in its definition of breaking, so the next such change is recognised as one.

**This is the whole of `v2`.** Nothing else breaking is queued — there is no recorded plan for a `v2` in this repository's docs or issues. Any breaking change that was being held for a future major moves to `v3`, which costs nothing now and buys a clean, single-purpose major.

### Why now rather than at some later major

Deferring looks cheaper and is not, because of who else holds these strings.

`terraform-github` is in the middle of hardcoding the Markdown contexts into its `standard-repository` module. If the reusable names change later, that repository writes the strings twice: once now against `@v1`'s names, and again when the fleet migrates. Worse, the second change is entangled with the `@v1` → `@v2` bump, so a routine version migration would additionally have to re-plan and re-apply branch protection across every managed repository, in the right order, or repositories would sit with required checks nothing reports.

Doing it now means the contexts `terraform-github` commits to are the final ones, and the later `@v2` migration is what it should be — a one-line pin bump per consumer.

### The cost: friendlier check names in the UI

`Internal links & anchors` reads better in a checks list than `internal`. That is a real loss and the only argument against.

It is outweighed because the audience differs. The prose name serves someone glancing at a pull request; the machine-readable name serves every adopter's branch protection, every hardcoded string in `terraform-github`, and anyone trying to work out what to require without running the workflow first. And the loss is partly illusory: the *full* context is what the UI shows, and `markdown-links / internal` is perfectly legible.

### Alternatives considered

- **Keep `name:` but require it to be a slug equal to the job ID.** Identical outcome, one more rule, and a second place for the two to drift apart. Rejected as strictly worse than not setting `name:`.
- **Keep `name:` free-form and publish the contexts in the docs instead.** A published list goes stale silently, and would have to be read by an adopter who already has the workflow file in front of them. It also does not help `terraform-github`, which needs the strings to be predictable, not merely documented.
- **Prefix the job ID with the family (`markdown-links-internal`).** Redundant: ADR-010 already puts the family on the left of the slash, so the context would read `markdown-links / markdown-links-internal`.

## Consequences

**Positive:**

- Every check context in the fleet becomes derivable from the workflow filename plus its job IDs — no check run needed to discover a string, and nothing to record in a doc that can go stale.
- Contexts become lowercase and punctuation-free, so they are safe to type, quote in HCL, and compare.
- `terraform-github` hardcodes each string once rather than twice, and the eventual `@v2` migration stays a pin bump instead of a coordinated branch-protection rollout.
- `terraform / terraform` is unaffected, so the only contexts currently required anywhere in the fleet survive the major cut.
- `releasing.md`'s definition of breaking gains a category it was silently missing.

**Negative / trade-offs:**

- **Every consumer must migrate `@v1` → `@v2`**, which is the cost of any major and is exactly what the version-check workflow exists to surface.
- **Prose check names are lost.** Accepted, per the reasoning above.
- **`v1` freezes.** Anything wanted on both lines needs a second pull request targeting `v1`, per `releasing.md`.
- **Any unrecorded plan for `v2` moves to `v3`.** Nothing is recorded, so this is believed to be free — but it is an assumption, and if a breaking change was being held informally it should ride this major or be renumbered deliberately.
