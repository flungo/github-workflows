# ADR-011: A reusable job's ID is its check name

- Date: 2026-08-02
- Status: Accepted

## Context

[ADR-010](010-caller-job-ids-match-the-workflow-filename.md) fixed the left-hand half of a check context — the caller's job ID — by making it the reusable workflow's filename.
It deliberately left the right-hand half alone, and that half is in worse shape.

A context is `<caller job id> / <reusable job name>`, where "name" means the job's `name:` if it sets one and its job ID otherwise.
This repository is inconsistent about which:

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

Nine of twelve are bare job IDs; three are prose.
So the full contexts range from `terraform / terraform` to `markdown-links / Internal links & anchors` — the latter carrying spaces, capitals and an ampersand.

That matters because these strings are no longer only decorative.
`terraform-github` hardcodes them: its `standard-repository` module writes required check contexts into GitHub rulesets from string literals in Terraform.
A context with a `&` in it is a string to be copied exactly and never typed from memory.

It is not *undiscoverable* — it is in the workflow file, as `name:` where a job sets one and the job ID where it does not.
But compare the two halves.
After [ADR-010](010-caller-job-ids-match-the-workflow-filename.md) the caller half is a filename the adopter already typed.
The reusable half requires opening a second file, in another repository, at the ref you pinned, knowing that `name:` shadows the job ID, and then transcribing prose exactly — which is why the values recorded during this work were taken from a real check run rather than read off the YAML.

ADR-010 documents that trap rather than fixing it, on the grounds that renaming the reusable jobs would break every consumer's required checks at once.
That reasoning is sound in isolation and wrong in context: this repository has a mechanism for exactly that, and is not yet using it.

## Decision

**A reusable workflow's jobs do not set `name:`.
The job ID is the identifier: short, kebab-case, and describing the job's role within its own workflow.**

The workflow filename already carries the family ([ADR-010](010-caller-job-ids-match-the-workflow-filename.md) puts it on the left of the slash), so the job ID does not repeat it.
`markdown-links.yml`'s jobs are `internal` and `external`, not `markdown-links-internal`.

With [ADR-010](010-caller-job-ids-match-the-workflow-filename.md), every context in the fleet becomes mechanically derivable from two things an adopter can read without running anything: the workflow's filename, and the job IDs inside it.

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

Every context becomes lowercase, space-free and punctuation-free.
`terraform / terraform` survives untouched, so the one family whose context is already required across the fleet needs no migration at all.

### This is a breaking change, and it cuts `v2`

The check contexts a workflow reports are part of its contract, even though [`releasing.md`](../runbooks/releasing.md) does not currently list them: its definition of breaking is "renaming or removing an input, adding a required secret, or changing a workflow's default behaviour".
A renamed context does not fail a caller's *run* — it fails the caller's *branch protection*, silently, by leaving a required check permanently pending.

That is breaking in every sense that matters, so this lands as a **major cut** ([ADR-003](003-version-via-moving-v1-branch.md)): `MAJOR_BRANCH` moves in the same pull request as the change, `@v1` freezes, and consumers migrate deliberately.

[`releasing.md`](../runbooks/releasing.md)'s definition is corrected **now**, in the pull request carrying this ADR, rather than waiting for the cut.
The gap is in the definition, not in this change — it was already wrong before anyone noticed — and leaving it until implementation would mean the next such change is misclassified in the window between.

**`v2` is this and [ADR-012](012-flungo-workflows-meta-workflow.md), and nothing else.**
The two travel together deliberately: both rename things a consumer has to edit, so pairing them means one migration rather than two.

There *is* a prior scoped `v2` — [`docs/plans/v2-cut.md`](https://github.com/flungo/github-workflows/pull/27), five breaking items on the Terraform and provider families: removing `tf-var-name`/`provider_token`, converging input and secret naming, renaming `PASSPHRASE`, failing the run on `fmt`, and restricting dispatch-apply to the default branch.
**Those move to `v3`.**

That plan's scope rule argues against the split: anything breaking worth doing rides one cut, because a second near-term major doubles the fleet's migration cost.
The rule is right about migration cost and wrong about what is being optimised here.

**Folding these two decisions into that cut would force its five to be settled at this change's pace.**
The plan exists to produce a *considered* major — its strict scope rule, its per-consumer migration analysis, and its long considered-and-rejected list are all artifacts of deliberation, and its own pre-cut `v1` work has not started.
Merging the two agendas does not make one thoughtful cut; it makes the thoughtful one inherit this one's urgency.
A contract decision taken early to save a migration is paid by every consumer for the life of the major, while a second migration is paid once.

So the two cuts are not the same kind of thing.
This one is small, self-contained, and urgent — `terraform-github` is hardcoding these strings now — which are exactly the properties that make a major cheap to cut and cheap to migrate.
The other is broad and deliberately unhurried.
Running them separately lets each be what it is.

### This reverses a rejection recorded in that plan

The `v2` plan considered normalising job names and **rejected** it: a job's name is check-context contract, so the rename would break every consumer's required-check configuration for a purely cosmetic gain.

Both halves of that are worth answering, because the reasoning is sound as far as it goes.

**The gain is not cosmetic.**
When the plan was written, these strings were read by humans glancing at a checks list.
They are now written into `terraform-github`'s `standard-repository` module as string literals that configure branch protection across the fleet, which makes their derivability a functional property rather than a matter of taste.

**The cost is much smaller than "every consumer's required-check configuration".**
Exactly one context is required anywhere in the fleet today — `terraform / terraform`, on two repositories — and it is the one context this ADR leaves unchanged.
Every other context is reported and required by nobody, so renaming it costs nothing but the caller edit that the pin bump already forces.
The rejection assumed a blast radius the fleet does not currently have.

Where the plan is right is that this *is* contract, which is why it cuts a major rather than shipping on `v1`.

### Why now rather than at some later major

Deferring looks cheaper and is not, because of who else holds these strings.

`terraform-github` is in the middle of hardcoding the Markdown contexts into its `standard-repository` module.
If the reusable names change later, that repository writes the strings twice: once now against `@v1`'s names, and again when the fleet migrates.
Worse, the second change is entangled with the `@v1` → `@v2` bump, so a routine version migration would additionally have to re-plan and re-apply branch protection across every managed repository, in the right order, or repositories would sit with required checks nothing reports.

Doing it now means the contexts `terraform-github` commits to are the final ones, and the later `@v2` migration is what it should be — a one-line pin bump per consumer.

### The cost: friendlier check names in the UI

`Internal links & anchors` reads better in a checks list than `internal`.
That is a real loss and the only argument against.

It is outweighed because the audience differs.
The prose name serves someone glancing at a pull request; the machine-readable name serves every adopter's branch protection, every hardcoded string in `terraform-github`, and anyone trying to work out what to require without running the workflow first.
And the loss is partly illusory: the *full* context is what the UI shows, and `markdown-links / internal` is perfectly legible.

### Alternatives considered

- **Keep `name:` but require it to be a slug equal to the job ID.**
  Identical outcome, one more rule, and a second place for the two to drift apart.
  Rejected as strictly worse than not setting `name:`.
- **Keep `name:` free-form and publish the contexts in the docs instead.**
  A published list goes stale silently, and would have to be read by an adopter who already has the workflow file in front of them.
  It also does not help `terraform-github`, which needs the strings to be predictable, not merely documented.
- **Prefix the job ID with the family (`markdown-links-internal`).**
  Redundant: [ADR-010](010-caller-job-ids-match-the-workflow-filename.md) already puts the family on the left of the slash, so the context would read `markdown-links / markdown-links-internal`.

## Consequences

**Positive:**

- Every check context in the fleet becomes derivable from the workflow filename plus its job IDs — no check run needed to discover a string, and nothing to record in a doc that can go stale.
- Contexts become lowercase and punctuation-free, so they are safe to type, quote in HCL, and compare.
- `terraform-github` hardcodes each string once rather than twice, and the eventual `@v2` migration stays a pin bump instead of a coordinated branch-protection rollout.
- `terraform / terraform` is unaffected, so the only contexts currently required anywhere in the fleet survive the major cut.
- `releasing.md`'s definition of breaking gains a category it was silently missing.

**Negative / trade-offs:**

- **Every consumer must migrate `@v1` → `@v2`**, which is the cost of any major and is exactly what the version-check workflow exists to surface.
- **Prose check names are lost.**
  Accepted, per the reasoning above.
- **`v1` freezes.**
  Anything wanted on both lines needs a second pull request targeting `v1`, per `releasing.md`.
- **The previously scoped `v2` becomes `v3`.** [`docs/plans/v2-cut.md`](https://github.com/flungo/github-workflows/pull/27) and its five breaking items are renumbered rather than dropped, per the reasoning above.
  Any breaking change being held informally should likewise ride this major or be renumbered deliberately.
