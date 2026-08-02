# ADR-014: A grace period before consumers are prompted onto a new major

Date: 2026-08-02
Status: Accepted

## Context

Cutting a major is a single reviewed edit — `MAJOR_BRANCH` in `release.yml`, `v1` → `v2` ([ADR-003](003-version-via-moving-v1-branch.md)) — and the moment it merges, two things happen at once. The old major freezes, and every opted-in consumer's next scheduled [`version-check`](004-version-check-opt-in.md) run opens an issue telling that repository to migrate.

The second is premature, because the first thing anyone learns about a new major's contract is learned by adopting it.

The `v2` cut ([ADR-011](011-reusable-job-ids-are-the-check-name.md), [ADR-012](012-flungo-workflows-meta-workflow.md)) makes the shape of the problem concrete: it renames every check context and moves a workflow file, and whether those names are right is not settled by review — it is settled by migrating a repository, seeing what the contexts actually read as in a checks list, and finding out which required-check strings in `terraform-github` needed changing in what order. That knowledge arrives *after* the cut, one consumer at a time.

Today the release model offers two ways to handle a mistake found on day two, and both are bad:

- **Get the whole major right before cutting it** — one pull request carrying every breaking change and, in effect, the whole fleet migration, held open until the last repository proves the contract. That is the mega-PR the incremental model exists to avoid, and it is reviewed at the worst possible size.
- **Cut the next major for the correction** — `v3` because `v2` got a check name slightly wrong. That is a real cost paid by every consumer: a migration each, for a fix that concerns the handful of repositories that had already moved. It also teaches the wrong lesson, which is to batch and delay.

Nothing in between exists, because the moment of cutting is simultaneously the moment the contract is declared final *and* the moment consumers are told to come along.

Those are two separate events, and only the first has to happen at the cut.

## Decision

**A newly cut major has a 7-day grace period. During it, opted-in consumers are not prompted onto it, and its contract is not yet final — a further breaking change may land on it in place rather than cutting the next major.**

Both halves come from the same premise: the major is not yet being asked of anyone, so changing it costs nobody a migration.

### What the version check does

[`version-check.yml`](../../.github/workflows/version-check.yml) prompts against the newest major **whose grace period has passed**, rather than the newest that exists. A consumer pinning `@v1` on day two of `v2` is told nothing; on day eight it gets the issue it would have got immediately before.

Nothing records when a branch was created — the branches API has no such field, and the Events API keeps 90 days of public events at best — so the cut is dated from the **oldest commit `v<latest>` has that `v<latest-1>` does not**. That is the merge which bumped `MAJOR_BRANCH`, since `release.yml` creates the new branch at exactly that commit. Comparing against the previous major, rather than reading the new one's tip, keeps the date fixed as the new major advances and survives a backport landing on the old one ([`releasing.md` § Patching a frozen major](../runbooks/releasing.md#patching-a-frozen-major)) — the compare is against the merge base either way.

When the cut cannot be dated — no previous major, no commits between them, an API failure — the grace period counts as **spent**, and the check behaves exactly as it did before. Failing towards the prompt is deliberate: an early prompt costs a consumer a week of premature attention, while a suppressed one recreates the silent drift ADR-004 exists to catch.

If a consumer *is* stale against an older major while a newer one is in grace — pinning `@v1` when `v2` is settled and `v3` was cut yesterday — the issue prompts for `@v2` and says that `v3` exists and is still settling. Migration advice never points at a contract that may still move.

### 7 days, and not an input

Seven days is a week of ordinary working time: long enough to migrate a few repositories and discover what the new contract actually requires, short enough that a consumer's notification is late rather than lost. There is no evidence for a more precise number, and the cost of being wrong is small in both directions.

It is **not** a workflow input. The grace period is a property of the release, not of the consumer: it exists because *this repository* does not yet know whether the contract is right, and a consumer cannot know that better. Making it an input would also let two consumers disagree about whether a major is current, which is exactly the kind of per-repo drift the moving-major model removes. Its one legitimate use — an eager adopter wanting the prompt immediately — is served better by just migrating, which is what the grace period assumes that adopter is doing anyway.

### It ships on `v1`, before the `v2` cut

A frozen consumer runs the *frozen* major's copy of the check: a repository pinning `@v1` after `v2` is cut evaluates `version-check.yml@v1`. So grace-period logic that shipped only in `v2` would have no effect on the `v2` cut — the consumers it is meant to spare are all running `v1`'s code. It has to land on the current major before the next one is cut, or it first applies a whole major later.

This is a change to a reusable workflow's default behaviour, which [`releasing.md`](../runbooks/releasing.md) lists as breaking. It is judged **not** breaking here, and the distinction matters: that clause is about a change that would fail an existing caller or silently break its branch protection. Delaying an advisory issue by seven days does neither — no caller fails, no check context changes, and the only observable difference is when an issue appears in the consumer's own repository. It rides `v1` as an ordinary merge.

### What it does not change

**The old major freezes at the cut, not at the end of grace.** `release.yml` stops advancing it the moment `MAJOR_BRANCH` changes, so a consumer on the old major stops receiving fixes seven days before anything tells it so. Grace delays the prompt, not the freeze — and this is the trade being made, stated plainly.

Closing it — by having `release.yml` keep advancing the old major through the grace window — would mean two branches tracking `main` while the breaking change is on both, which defeats the point of the cut. The exposure is bounded: seven days of no non-breaking fixes, on a repository that has not yet been asked to move.

**Adopting during the grace period means accepting in-place changes.** Whoever migrates in the window is, by construction, the person settling the contract; a correction landing on them is the mechanism working, not a failure of it. Anyone else should wait for the prompt, which is what waiting for the prompt now means.

**After 7 days the contract is final.** Normal rules resume: the next breaking change cuts the next major. The window is for corrections to the major just cut, not a standing licence.

## Consequences

**Positive:**

- A major can be cut incrementally and corrected in place while it is being adopted, so neither the mega-PR nor the punitive extra major is required to get one right.
- A consumer's migration prompt arrives only for a contract that has stopped moving — the prompt is worth acting on when it comes.
- No new configuration, credential, or per-consumer state: one constant, and a date derived from history that already exists.
- The cut date is computed rather than recorded, so nothing can be forgotten at cut time or drift out of date afterwards.

**Negative / trade-offs:**

- **The old major freezes seven days before its consumers are told.** The one genuine cost, accepted for the reasons above.
- **`GRACE_DAYS` is frozen into each major's copy of the check.** Changing it in `v2` leaves `v1` consumers — the ones the next cut actually affects — on the old value. In practice a change to the number takes a full major cycle to take effect.
- **The cut date is inferred, not recorded.** It relies on `release.yml` creating the branch at the bumping merge. A major branch created some other way (hand-bootstrapped, restored after an incident) dates from whatever its first divergent commit is, and the compare can only reach 250 commits per page — the first page is the oldest, so the date is read from the right end, but the inference is still an inference.
- **A settling change is a breaking change with no version to distinguish it.** Two repositories can adopt `v2` a week apart and get materially different contracts, both called `v2`. Bounded by the window's length and by who is adopting inside it, but it is real, and it is why the window is short.
- **One more thing to remember when cutting a major**: that the upgrade guide's new section ([ADR-013](013-per-major-upgrade-guide.md)) stays editable for a week, and must be updated by any settling change that lands.
