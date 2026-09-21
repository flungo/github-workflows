# ADR-014: A major is published by the cut and promoted to stable by hand

- **Date:** 2026-09-16
- **Status:** Accepted

## Context

Cutting a major is a single reviewed edit — `MAJOR_BRANCH` in `self-release.yml` ([ADR-003](003-version-via-moving-v1-branch.md)) — and the moment it merges, two things happen at once.
The old major freezes, and every opted-in consumer's next [`version-check`](004-version-check-opt-in.md) run opens an issue telling that repository to migrate.

The second is premature, because the first thing anyone learns about a new major's contract is learned by adopting it.

The `v2` cut made the shape of this concrete.
[ADR-011](011-reusable-job-ids-are-the-check-name.md) renamed every check context and [ADR-012](012-flungo-workflows-meta-workflow.md) moved a workflow file, and whether those names were right was not settled by review — it was settled by migrating a repository, seeing what the contexts read as in a checks list, and finding out which required-check strings in `terraform-github` had to change in what order.
That knowledge arrives *after* the cut, one consumer at a time.

Which left two ways to handle a mistake found on day two, both bad:

- **Get the whole major right before cutting it** — one pull request carrying every breaking change and, in effect, the whole fleet migration, held open until the last repository proves the contract.
  That is the mega-pull-request the incremental model exists to avoid, reviewed at the worst possible size.
- **Cut the next major for the correction** — `v3` because `v2` got a check name slightly wrong.
  Every consumer pays a migration for a fix that concerns only the handful of repositories that had already moved, and the lesson it teaches is to batch and delay.

Nothing in between existed, because the moment of cutting was simultaneously the moment the contract was declared final *and* the moment consumers were told to come along.

Those are two separate events, and only the first has to happen at the cut.

## Decision

**Cutting a major publishes it but leaves it *settling*.
A second, manual edit promotes it to *stable*, and that is what starts prompting consumers.**

`self-release.yml` gains a `STABLE_MAJOR` alongside `MAJOR_BRANCH`.
Cutting bumps the first; promoting bumps the second; the gap between them is the settling state.
While it is open, the new major may take further breaking changes **in place**, without cutting another — nobody has been asked to move onto it yet, so changing it costs nobody a migration.

### What the version check does

The `version-check` job compares a consumer's pins against `STABLE_MAJOR`, not against the newest `v*` branch.

It reads that from **`main`**, which is the only ref that always carries the current state: a consumer frozen on `v2` cannot name `v3`'s branch without first discovering it, and reading the value from the new major's own branch would make a bootstrapping problem out of a lookup.

Unreadable, absent, or ahead of what exists, it falls back to the newest published major — exactly what the job did before this state existed.
Failing towards the prompt is deliberate: an early prompt costs a consumer some premature attention, while a suppressed one recreates the silent drift [ADR-004](004-version-check-opt-in.md) exists to catch.

A consumer stale against an older major while a newer one is settling — pinning `@v1` when `v2` is stable and `v3` was just cut — is sent to `@v2` and told that `v3` exists and is still settling.
Migration advice never points at a contract that may still move, and a consumer that can see the newer branch on GitHub is not left reading the issue as out of date.

### Each guide section is linked on its own major's branch

The issue's [upgrade guide](../reference/upgrading.md) links are `…/blob/v<N>/docs/reference/upgrading.md#v<N>`, not `…/blob/main/…`.

The section itself would survive either way — it is about a hop between two fixed majors, and older sections are not rewritten.
What does not survive is everything around it.
GitHub resolves a rendered file's relative links against the ref it was opened at, so a section read on `main` sends the reader onward to today's runbooks, ADRs and workflow files — a repository that has moved on past the major they are migrating to, and that under a settling major describes behaviour nobody has been prompted onto.
Read at `v<N>`, the same links hand them the repository as it stood for the version they are moving to.

Per-major rather than one ref for the whole span, because a multi-major migration is several hops and each is made against a different repository.
A consumer going `v1` → `v3` reads the `v2` section on `v2`, does that work, then reads the `v3` section on `v3`.
The cost is that a correction made to an older section after its successor was cut does not reach the pinned copy unless it is backported — acceptable, because that section is *about* its own major, so its own branch is the copy that ought to be right.

### A new adopter needs telling too

Pinning the guide links solves this for an *upgrading* consumer, who arrives through an issue that hands them a ref.
A **new** adopter arrives at `main`, where — precisely because settling changes land as they happen — the docs describe a major nobody should be adopting yet.

Two things address that, both in the README:

- **Its adoption-runbook links are pinned to the stable major** (`blob/v<stable>/docs/runbooks/…`), not relative.
  Those pages hand over a caller to copy, and their own onward links resolve against the ref they were opened at, so pinning the four entry points keeps the instructions, the pin they recommend and everything downstream on one coherent version.
- **A callout, present exactly while a major is settling**, naming what is settling and what to adopt instead.

`release-state` enforces both: the callout must exist while `MAJOR_BRANCH` and `STABLE_MAJOR` differ and must be gone once they agree, it must name both majors, and the pinned links must name the stable one.
So the cut cannot ship without the callout and the promotion cannot ship with it — the same "cannot be forgotten" property the warning gives promotion itself.

Changing the repository's **default branch** to the stable major was the alternative, and would fix this for anyone browsing rather than only for readers of the README.
It was rejected on the cost of the defaults it moves: new pull requests would target the stable branch, where a mis-based merge diverges a release branch from `main`; `git clone` — and every agent session — would start on it, so a branch cut from the default while a major settles has the wrong base; Dependabot would raise its bumps there; and `on: schedule` runs only on the default branch, so the daily external-URL sweep would stop covering `main`.
Those are paid every day, to fix a confusion that exists only during settling windows, and it is a `terraform-github` change rather than one this repository can make.

### The divergence is surfaced, not remembered

A promotion that is forgotten is worse than a clock that expires: consumers sit on a frozen major and are never told, which is the exact failure ADR-004 exists to prevent.

So `self-ci.yml` gains a **`release-state`** job that warns — an annotation, on a passing check — for as long as `MAJOR_BRANCH` and `STABLE_MAJOR` differ.
Every pull request merging onto a settling `main` carries the reminder, so the state has to be noticed rather than probed for.
It is deliberately non-blocking, because settling is a legitimate state to merge onto and lasts as long as adopting the major takes.
It *fails* only on a pair that cannot be right — a malformed value, or a stable major ahead of the cut one — which would misdirect every consumer's version check.

### A fixed grace period was the alternative

The first design was a **7-day grace period**, dated from the cut, after which consumers were prompted automatically.
It has one real advantage: nothing to remember, because the date is derived from history that always exists.

It was rejected because the window should end when the work ends, not on a calendar.
A fleet migration that takes three weeks would see consumers prompted onto a contract still in motion — the precise failure the window exists to prevent — and one that takes two days would hold the prompt back for no reason.
A clock is the wrong kind of parameter for "is this proved yet", and the only person who can answer that is the one doing the adopting.

**No expiry backstop** is combined with the manual promotion, for the same reason.
Attention returning to this repository after a pause is better spent promoting the major, or cutting forward, than on supporting a previous major the clock has just declared everyone's problem.
The `release-state` warning is the mitigation instead: it makes a forgotten promotion visible, without deciding on anyone's behalf.

### Settling before publishing was the other alternative

The other shape considered: keep the breaking work on a long-lived branch outside the create-restricted `v[0-9]*` namespace, adopt *that* across the fleet, and let the cut itself be the promotion.
It needs no code at all, and it avoids freezing the old major during settling.

Rejected on maintenance grounds.
It costs two fleet sweeps rather than one — every consumer pinned at the settling branch and then again at the new major — and a repository left pinned at the settling branch afterwards is **invisible to `version-check`**, which tracks only bare `@vN` refs.
That is a new silent-drift hole in the mechanism built to close one, and it is a worse risk than a pin left one major behind.
A long-lived branch also rots across exactly the multi-week pauses this repository's work actually takes.

## Consequences

### Positive

- A major can be cut incrementally and corrected in place while it is being adopted, so neither the mega-pull-request nor the punitive extra major is needed to get one right.
- A consumer's migration prompt arrives only for a contract that has stopped moving, so the prompt is worth acting on when it comes.
- The major consumers are pointed at is **declared rather than inferred** — no date arithmetic, and no assumption that major numbers are contiguous.
- The cut stops rewriting the adoption docs: they are bumped by the promotion, so they never advertise a version nobody should be adopting yet.
- A consumer following the issue reads each hop's documentation as it stood for that major, so docs that have since moved on cannot mislead someone several majors behind.
- **`main` is freed from carrying a migration-accurate copy of the docs.**
  While a major is settling, the one consumers are sent to is the major before it, frozen at the cut — so every link a migrating consumer follows resolves on content that has stopped moving.
  The pull requests that settle the new major can therefore rewrite the runbooks as they go, rather than each having to leave `main` readable by someone mid-upgrade.
- No new credential or per-consumer configuration — one more line in `self-release.yml`, read from a public repository.

### Negative — trade-offs

- **The old major freezes at the cut, not at the promotion.**
  `self-release.yml` stops advancing it the moment `MAJOR_BRANCH` changes, so a consumer stops receiving fixes before anything tells it so, for as long as settling lasts.
  Keeping the old major advancing through the window would mean two branches tracking `main` with the breaking change on both, which defeats the cut.
  A fix that matters to the frozen major can still be backported ([`releasing.md` § Patching a frozen major](../runbooks/releasing.md#patching-a-frozen-major)); the accepted position is that promoting or cutting forward is usually the better use of the attention.
- **A promotion can be forgotten, and the consequence is silence.**
  Bounded only by the `release-state` warning, which nobody is forced to act on.
  This is the cost of refusing an expiry, taken deliberately.
- **A settling change is a breaking change with no version to distinguish it.**
  Two repositories can adopt the same major weeks apart and get materially different contracts, both called `vN`.
  Bounded by who adopts during settling — in practice the person settling it.
- **The release workflow's path is now part of the consumer contract**, since a frozen consumer's check reads that file from `main` by name.
  The deferred `self-` prefix rename in `CLAUDE.md` would break every frozen consumer's read, which now falls back to treating the newest major as stable — so that rename needs the reader to tolerate both paths first.

  **Amended 2026-09-21:** both halves have landed, in that order.
  `version-check` now tries `self-release.yml` and then `release.yml`, and the file is renamed, so every unfrozen major reads the value as it did before.
  A copy of the reader on a frozen major still reads the old path alone and finds nothing, so it falls back as described — harmlessly while the newest published major *is* the stable one, and by sending its repository at a settling major once one is cut.
  That is the accepted degradation rather than a new one, it reaches nothing today (no repository pins `@v1`), and the old path stays in the reader's list so that no future rename repeats it.
- **A new adopter who arrives at a runbook directly never sees the callout.**
  The README is the only place that says a major is settling, so a search result or a deep link bypasses the warning entirely — the pinned links help only someone who comes through the front page.
  Closing that gap would need the default-branch switch this rejects.
- **One more step when cutting a major**, and the upgrade guide's new section stays editable until the promotion rather than being finished at the cut.
