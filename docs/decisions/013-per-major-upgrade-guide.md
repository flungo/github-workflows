# ADR-013: A per-major upgrade guide, scoped to breaking changes only

Date: 2026-08-02
Status: Proposed

## Context

[ADR-003](003-version-via-moving-v1-branch.md) makes consumers pin a moving major branch, and [ADR-004](004-version-check-opt-in.md) tells a consumer when the major it pins has frozen — an issue in its own repository saying, in effect, "you are on `@v1`, the current major is `@v2`".

That issue is where the model stops helping. It identifies the gap and says nothing about how to close it. A consumer reading it has to work out for itself what changed, and the only sources are this repository's commit history since the major branch diverged and whatever the pull requests happened to explain. Both are organised by *when work happened*, not by *what a consumer must do*, and the commits that matter are mixed in with every non-breaking change that shipped alongside them.

[ADR-011](011-reusable-job-ids-are-the-check-name.md) and [ADR-012](012-flungo-workflows-meta-workflow.md) make this concrete rather than theoretical. `v2` will require a consumer to rename its caller job IDs, change a `uses:` path, and — for any repository whose branch protection names a check — update required contexts in `terraform-github` in the right order. That is a genuine migration, and nothing currently exists to write it down in.

## Decision

**Keep a per-major upgrade guide at [`docs/reference/upgrading.md`](../reference/upgrading.md), containing one section per major, recording only what breaks and what a consumer must do about it. Adding that section is a step in cutting a major.**

### It is an upgrade guide, not a changelog

The name is the scope control, so it is chosen deliberately.

"Changelog" carries an expectation — that it lists changes, all of them — and that expectation is what turns a file into a maintenance tax: every pull request grows an entry, the entries are written for nobody in particular, and the signal is buried. "Upgrade guide" states its audience and its contents in its own title: it is for a consumer moving between majors, and it contains what that consumer must do.

Anything named `CHANGELOG.md` here would drift toward the former within a few pull requests, whatever a policy line at the top said.

### Only breaking changes appear, and the reason is not just burden

The load-bearing argument is about what a consumer can act on.

Under the moving-major model, a non-breaking change **arrives automatically** — a consumer pinned `@v1` gets it on the next merge without doing anything, and could not decline it if they wanted to. There is no decision to make and no action to take, so an entry describing it would be a notification about something that already happened, addressed to someone with nothing to do about it.

A breaking change is the opposite: it does *not* arrive, the consumer stays frozen until they act, and what they must do is not derivable from the fact of the version bump. That asymmetry is the whole justification for the file, and it is also its boundary.

So: no entries for additive inputs, new optional secrets, bug fixes, internal refactors, or documentation. The commit history holds those, organised by when they happened, which is the right organisation for that material.

What counts as breaking is [`releasing.md`](../runbooks/releasing.md)'s definition — which [ADR-011](011-reusable-job-ids-are-the-check-name.md) extends to include the check contexts a workflow reports, a category it was silently missing.

### Shape

One `## vN` section per major, newest first, so the section a reader needs is the one at the top and the anchor is predictable (`#v2`) for anything that wants to deep-link.

Each section covers, for that major: what broke, what the consumer must change, and — where it matters — in what order. Ordering is not a detail here: `v2` requires a caller-job rename that must precede `terraform-github` requiring the new contexts, and getting that backwards leaves a repository unable to merge.

`v1` gets a stub noting it was the initial major with nothing to migrate from, so the file is not misread as incomplete.

### The version-check issue links to it

[ADR-004](004-version-check-opt-in.md)'s issue body gains a link to this guide. That closes the loop the issue currently leaves open: the thing that tells a consumer they are behind is also the thing that tells them how to catch up, rather than leaving them to search for it.

That change is additive to an issue body and therefore **not** breaking, so it could ship on `v1` independently. It will land with the `v2` work anyway, since ADR-012 is rewriting that workflow's home.

### Writing it becomes part of cutting a major

`releasing.md`'s "cut the next major" procedure gains a step alongside the `MAJOR_BRANCH` bump: **add the new major's section to the upgrade guide, in the same pull request as the breaking change.**

Same-pull-request is the point. The person who knows what breaks and what to do about it is the person making the change, at the moment they make it; a guide written afterwards is written from the commit history, which is exactly the reconstruction this file exists to avoid. It also means the diff that declares a major and the diff that documents it are reviewed together, so "is this actually breaking?" and "can a consumer act on this?" get asked once.

The "breaking change you didn't foresee" path gets the same step, since it also cuts a major.

## Consequences

**Positive:**

- A consumer told it is on a frozen major now has somewhere to go, linked from the notification itself.
- The migration is written by whoever made the change, while they still hold the context, rather than reconstructed later from commits.
- Scoping to breaking changes keeps the file short enough to stay accurate — a file with one section per major grows at the rate majors are cut, which is rare by design.
- Ordering constraints between this repository and `terraform-github` get written down somewhere a consumer will actually look, instead of living only in the pull requests that discovered them.

**Negative / trade-offs:**

- **One more step when cutting a major**, and one that is easy to skip because nothing enforces it. Mitigated only by its being in the runbook next to the `MAJOR_BRANCH` bump, which is the step nobody forgets.
- **A consumer wanting the full picture of what changed still reads the commit history.** That is the deliberate trade: the guide answers "what must I do", not "what happened".
- **The boundary needs judgement in one case** — a change that is technically non-breaking but that a consumer would want to act on (a new optional input that supersedes an old pattern, say). The rule says leave it out; the honest answer is that such a change belongs in the relevant runbook, where an adopter looks, rather than in a migration record.
- **`v1` has no content**, so the file launches nearly empty and only earns its keep at the `v2` cut.
