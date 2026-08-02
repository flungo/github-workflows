# ADR-010: A caller's job ID matches the reusable workflow's filename

Date: 2026-08-02 Status: Accepted

## Context

Every check a reusable workflow produces is reported under the context `<caller job id> / <reusable job name>`.
The right-hand half is ours, fixed in this repository.
The left-hand half belongs to whoever writes the caller — so the string a consumer's branch protection has to name is only half determined by us, and the other half is whatever the adopter typed.

The caller snippets in the adoption runbooks are what most adopters copy, so in practice they *are* the convention, and they were inconsistent:

| Reusable workflow | Job ID the runbook showed | Context it produced |
| --- | --- | --- |
| `terraform.yml` | `terraform` | `terraform / terraform` |
| `version-check.yml` | `version-check` | `version-check / version-check` |
| `markdown-lint.yml` | `lint` | `lint / markdownlint` |
| `markdown-links.yml` | `links` | `links / Internal links & anchors` |
| `terraform-drift.yml` | `drift` | `drift / terraform` |
| `terraform-provider-test.yml` | `ci` | `ci / …` |
| `terraform-provider-docs.yml` | `docs` | `docs / …` |
| `terraform-provider-release.yml` | `release` | `release / …` |

Two of the eight name the workflow they call; the rest use a short generic word.

Those short words are the problem.
A caller job ID is a **repository-wide namespace** — every job in every workflow file shares it — and `lint`, `ci`, `docs`, `release` and `drift` are exactly the names a repository is most likely to want for something else.
A repository with a Go linter, a Markdown linter and an `actionlint` run has three candidates for `lint` and can give it to only one.
`links` is worse than ambiguous: it does not say what it does, and reads as a noun with no verb.

This came to a head when [`terraform-github`](https://github.com/flungo/terraform-github) began *requiring* these contexts.
Its `markdown` flag hardcodes the strings a conforming repository must report, which promotes the caller job ID from a local style choice to part of a cross-repository contract.
The first consequence was immediate: this repository dogfoods both Markdown workflows from `./` inside a combined `ci.yml`, where the caller jobs sit beside `actionlint` and could not sensibly be called `lint` and `links`, so they were named `markdown-lint` and `markdown-links` — and the repository that *defines* the standard therefore did not match the standard's own example.

The initial answer was to let it not match and reconcile with an exclusion list on the `terraform-github` side.
That treats the symptom.
The names in `ci.yml` were not an exception; they were right, and the runbook's examples were wrong.

## Decision

**A caller's job ID is the reusable workflow's filename, without the `.yml` extension.**

```yaml
jobs:
  markdown-lint:                                                    # markdown-lint.yml
    uses: flungo/github-workflows/.github/workflows/markdown-lint.yml@v1
```

The rule is mechanical, so there is nothing to remember and nothing to decide per adoption: read the filename, use it.
It also makes the context predictable in the other direction — given a workflow, you know the context it will report before anyone has written the caller, which is what lets `terraform-github` hardcode the strings at all.

It satisfies the two properties the short names lacked:

- **Namespaced by family.**
  Every ID starts with the product or family (`markdown-`, `terraform-`), so a repository can adopt several families and any number of its own jobs without collision.
  `markdown-lint` and a Go `lint` coexist; `lint` alone cannot.
- **Unique and self-describing.**
  The ID names the thing it calls.
  `markdown-links` says what `links` did not.

Two of the existing examples (`terraform`, `version-check`) already comply, which is a mild check that the rule is the one that was being reached for anyway.

`version-check` complies with the letter and not the spirit, and it is worth naming rather than glossing: the rule produces a conforming ID there, but "Namespaced by family" is not satisfied, because `version` is not a family — the workflow is a single concern whose name is the whole of it, so the context degenerates to `version-check / version-check`.
That is a defect in the *workflow's* name rather than in this rule, and [ADR-012](012-flungo-workflows-meta-workflow.md) fixes it by renaming the workflow so the rule has a family to work with.

The rule governs **jobs that call a reusable workflow from this repository**.
A caller's own local jobs are its own business — `adopting-terraform-provider-workflows.md`'s `testacc`, which runs in the consumer rather than calling anything here, keeps its name.

### The reusable job's name is a display name, and is not derivable

The right-hand half of a context is the reusable job's `name:` where it has one, and its job ID only where it does not.
`markdown-lint.yml`'s job is `lint` but `name: markdownlint`; `markdown-links.yml`'s is `internal` but `name: Internal links & anchors`.
So it is readable from the workflow file — but only by opening a second file, in another repository, at the ref the caller pinned, knowing the name-or-ID fallback, and then transcribing prose exactly, ampersand included.
Taking it from a real check run is the reliable way.

This ADR does not change those names, because the left-hand half — the one adopters control and collide on — is where the ambiguity lived, and fixing that first is what makes the caller half predictable at all.
[ADR-011](011-reusable-job-ids-are-the-check-name.md) takes the other half, and has to be a major cut rather than a convention, which is why the two are separate decisions.

### This ADR changes nothing this repository publishes

A caller's job ID lives in the *consumer's* workflow file.
Nothing here — no input, no secret, no default, and no check this repository reports — changes because of this decision, so it is not a breaking change and does not call for a version bump.
What it changes is the runbooks' examples and the advice an adopter follows, both of which take effect the moment this merges, on whichever major the adopter is pinned to.

That is the practical difference between this and [ADR-011](011-reusable-job-ids-are-the-check-name.md), which alters strings this repository emits and therefore has to ride a major.

### Existing adopters realign, and only some realignments are coordinated

Changing a caller's job ID changes the context it reports, so an adopter is not free to do it whenever a check is required somewhere.

- **Where nothing requires the context** — the drift and provider families today — realignment is a local rename an adopter makes whenever it next touches the file.
  Nothing observes the old string.
- **Where a context is required** — the Markdown checks, via `terraform-github`'s `markdown` flag — the rename and the requiring side must be sequenced: rename the caller first, let it report the new context, then require it.
  Reversed, the repository blocks its own merges behind a context nothing produces.

Four repositories carry the old Markdown names (`authentik.flungo.net`, `stalwart.flungo.net`, `terraform-provider-stalwart`, `claude-plugins`).
They are renamed before `terraform-github` requires the new strings.

## Consequences

**Positive:**

- The context a workflow reports is now derivable from its filename, which is what makes it safe for another repository to hardcode.
- A caller job ID can no longer collide with an adopter's own jobs, so adopting a second family — or having a `lint` of one's own — needs no renaming.
- The exclusion mechanism on the `terraform-github` side stops being needed for a naming mismatch.
  It remains for its real case: a repository that genuinely cannot *run* a check.
- This repository's own `ci.yml` becomes conformant rather than an exception, so the standard is dogfooded rather than merely published.

**Negative / trade-offs:**

- **Job IDs get longer**, and in a single-purpose workflow file the family prefix is redundant with the filename around it.
  Accepted: the ID is a repository-wide name, so it has to be unique in a scope wider than the file it sits in.
- **Existing adopters must be updated** — four for Markdown, plus the drift and provider callers whenever they are next touched.
  The Markdown renames need cross-repository sequencing against `terraform-github`'s required checks.
- **A required context breaks the moment a caller job is renamed**, which is a sharper edge than before.
  That is inherent to GitHub naming contexts individually rather than a cost of this rule, but the rule makes renames more likely in the short term.
- **The rule is a convention, not an enforced constraint.**
  Nothing validates that a caller followed it; a mismatch shows up as a required check that never reports.
