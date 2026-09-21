# Releasing: how `@vN` advances

How a change here reaches the repos that pin `@vN`.
The model is [ADR-003](../decisions/003-version-via-moving-v1-branch.md): consumers pin a moving major **branch** (`v1`, later `v2`, …), and [`self-release.yml`](../../.github/workflows/self-release.yml) advances it automatically on every merge to `main`.
Most of the time there is nothing to do.

## The normal case — a non-breaking change

Nothing beyond the usual PR.
When your PR merges to `main`:

1. `self-release.yml` runs on the push to `main`.
2. It fast-forwards the current major branch (the one named by `MAJOR_BRANCH` in `self-release.yml`) to the merged commit.
3. Consumers pinning `@v<current>` pick it up on their next run — no bump on their side.

The review gate is the PR into `main`.
There is no separate release PR and no tag to move.

## Making a breaking change you foresee: cut the next major

A change is **breaking** when it would fail an existing caller: renaming or removing an input, adding a required secret, or changing a workflow's default behaviour.
(Docs, internal refactors, and new *optional* inputs are **not** breaking.)

**Renaming a check context is breaking too**, and is the case most easily missed because it does not fail a run.
A context is `<caller job id> / <reusable job name>`, so renaming a job here — or giving one a `name:`, or removing it — changes what consumers' branch protection sees.
Their runs still pass; their required checks simply never report again, leaving pull requests stuck behind a permanently pending entry.
See [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md).

In the **same PR** as the breaking change:

1. Edit `MAJOR_BRANCH` in `self-release.yml` — bump it one major, e.g. `v2` → `v3`.
   **Leave `STABLE_MAJOR` alone.**
   The gap between the two is the new major's [settling period](#the-settling-period), and opening it is the point.
2. **Add the new major's section to [`upgrading.md`](../reference/upgrading.md)** — what breaks and what a consumer must do about it, in the same PR as the breaking change while you still hold the context.
   Breaking changes only; see [ADR-013](../decisions/013-per-major-upgrade-guide.md) for what belongs there and what does not.
   It stays editable until the promotion.
3. **Add the settling callout to the [README](../../README.md)**, in the slot its HTML comment marks — [template below](#the-settling-callout).
   `self-ci.yml`'s `release-state` job fails without it, so this is not a step you can forget.
4. Land the PR as normal.

On merge, `self-release.yml` sees the new name, **creates `v<new>` at `main`**, and never touches `v<old>` again — so `@v<old>` consumers **freeze** on their last compatible commit.
Don't pre-create `v<new>` by hand: creation is restricted to the release App and the push would be rejected (see [Never](#never)).
That one-line edit, visible in the PR diff, is the whole "this is a major" decision; there is nothing else to parse or label.

Nobody is told to migrate yet.
The docs that advertise the current version are not bumped here either — that happens at the promotion, so they never point consumers at a major that is still settling.

## The settling period

A cut major is published but not yet stable, and the two are separate events ([ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md)).
Between them:

- **No consumer is prompted onto it.**
  `version-check` compares pins against `STABLE_MAJOR`, so opted-in consumers stay on the previous major and hear nothing.
- **The new major can take a further breaking change in place.**
  Land it on `main` as an ordinary merge and `self-release.yml` advances the new major onto it.
  **No `MAJOR_BRANCH` bump** — nobody has been asked to move yet, so changing it costs nobody a migration.
- **Every pull request carries a reminder.**
  `self-ci.yml`'s `release-state` job annotates each run for as long as the two values differ.
  The annotation is non-blocking: settling is a legitimate state to merge onto, and it lasts as long as adopting the major takes.
- **The README says so**, via the callout below, so someone arriving at the repository is not handed a contract that can still change.

### The settling callout

The upgrade-guide links in a consumer's version-check issue are pinned to the major being migrated to, so an upgrading consumer never reads this branch ([ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md)).
A **new** adopter has no such issue to arrive through: they land on `main`, where the docs describe the major that is settling.
The README's adoption-runbook links are pinned to the stable major for that reason, and while a major is settling the README says outright that one is in progress:

```markdown
<!-- settling:start -->
> **`v3` has been cut and is settling.**
> Its contract can still change, so adopt **`@v2`** — the current stable major — and read [the `v2` documentation](https://github.com/flungo/github-workflows/tree/v2) rather than this branch's, which already describes `v3`.
> Why: [the settling period](docs/runbooks/releasing.md#the-settling-period).
<!-- settling:end -->
```

The first link is absolute because it deliberately points at another ref; the second is relative because the callout lives in the README, where that path resolves.
Neither is checked while it sits in this code block — lychee skips verbatim content unless `--include-verbatim` is passed, which [`markdown-links.yml`](../../.github/workflows/markdown-links.yml) does not — so the template is proved only once it is pasted.

`release-state` fails unless the callout is present **exactly** while `MAJOR_BRANCH` and `STABLE_MAJOR` differ, and unless it names both of them — a callout left over from an earlier cut is worse than none, because it names the wrong majors with full confidence.
It checks the pinned links the same way, so the README cannot advertise a major that is not the stable one.

This is what makes cutting a major incremental.
The contract is proved by adopting it, one repository at a time, and what that turns up — a check name that reads badly in a checks list, a required-check string that had to change in an order nobody predicted — arrives after the cut.
Without the window, the only options are one enormous pull request that gets the whole major right before cutting it, or a `v<new+1>` because `v<new>` got a name slightly wrong.

Use it that way: **cut the major, then migrate your own repositories**, and fix what that finds on the new major directly.

Two things it does *not* change:

- **The old major froze at the cut**, not at the promotion — `self-release.yml` stopped advancing it the moment `MAJOR_BRANCH` changed.
  Settling delays the prompt, not the freeze.
  A fix the frozen major genuinely needs can still be [backported](#patching-a-frozen-major).
- **A settling change is still a breaking change.**
  If it changes what a consumer must do, amend that major's section in [`upgrading.md`](../reference/upgrading.md) in the same PR.

Anyone adopting during the window accepts changes in place.
In practice that is you, migrating the fleet.

## Promoting a major to stable

When adopting the new major across your own repositories has proved the contract, promote it.
In one PR:

1. Edit `STABLE_MAJOR` in `self-release.yml` to match `MAJOR_BRANCH`.
2. **Remove the [settling callout](#the-settling-callout) from the README**, and bump its pinned adoption-runbook links (`blob/v<old>/…` → `blob/v<new>/…`).
   `release-state` fails until both match the new state, so neither can be left behind.
3. **Update the docs that track the current version.**
   Search the repo for `v<old>` — broader than `@v<old>`, so it also catches prose and tables that name the version without the `@`, at the cost of more matches to sift — and bump every reference meant to show consumers the current major (the [README](../../README.md) and the adoption runbooks: [Terraform](adopting-terraform-workflows.md), [Markdown](adopting-markdown-workflows.md)) to the new major.
   Leave version-specific mentions — historical and migration notes — as they are.
4. Settle the new major's [`upgrading.md`](../reference/upgrading.md) section: it stops being editable here and becomes the record consumers migrate against.

On merge, the `release-state` warning clears, and opted-in consumers still on an older major raise their own migration reminder on their next scheduled run — see [Tracking consumer migration](#tracking-consumer-migration).
Consumers move deliberately; nothing is pushed onto them.

Promotion is one-way.
A breaking change after it cuts the next major, as normal.

## A breaking change you didn't foresee

When an incompatibility is noticed only *after* it merged — `self-release.yml` has already fast-forwarded `@v<current>` onto it:

1. **Check whether the current major is still settling.**
   If `MAJOR_BRANCH` and `STABLE_MAJOR` differ — `self-ci.yml`'s `release-state` job says so on every PR — nobody has been prompted onto this major yet.
   Fix it in place on `main`, amend that major's [`upgrading.md`](../reference/upgrading.md) section, and stop.
   No new major; that is what [the settling period](#the-settling-period) is for.
2. **Otherwise prefer fixing it forward.**
   If compatibility can be restored on `main` — re-add the removed input as optional, reinstate the old default — do that.
   The next merge advances the fix onto `@v<current>` and no new major is needed.
   Cutting a major forces *every* downstream repo to migrate, so avoid it unless the change genuinely can't be reconciled.
3. **If a new major is truly required:**
   - **Cut the next major:** follow [Making a breaking change you foresee](#making-a-breaking-change-you-foresee-cut-the-next-major), then come back here.
     The new major branch is created at `main` with the breaking change and becomes the new line.
   - **Then restore the old major:** open a PR targeting `v<old>` (base `v<old>`) that reverts the breaking additions.
     It lands as an ordinary forward commit, so `@v<old>` consumers get the change and then its revert, ending compatible again.
     `v<old>` is then frozen except for such PRs.

## Patching a frozen major

Once a newer major exists, `self-release.yml` no longer advances the older one.
To fix a bug on a frozen major — `v1`, now that `v2` is cut — open a PR **targeting that branch** (e.g. base `v1`) with the patch — written directly or cherry-picked from `main`.
It merges straight onto that branch; nothing auto-advances it.

## Tracking consumer migration

Nothing forces a consumer off a frozen major, so a repo can silently lag on `@v<old>` after a new major is cut.
To surface that, consumers **opt in** to the reusable [`flungo-workflows.yml`](../../.github/workflows/flungo-workflows.yml)'s `version-check` job: on a schedule it compares the majors that consumer pins against the current stable major here, and opens — then auto-closes — a tracking issue **in that consumer's own repo** when it's on a frozen major.
It needs no credential (the consumer reads this public repo's majors and writes the issue with its own token).
See [`adopting-flungo-workflows.md`](adopting-flungo-workflows.md) for the opt-in caller, and [ADR-004](../decisions/004-version-check-opt-in.md).

The comparison is against `STABLE_MAJOR`, read from `self-release.yml` on `main` — so the first issues appear when a major is [promoted](#promoting-a-major-to-stable), not when it is cut, and a repository lagging two majors is pointed at the settled one rather than the one still moving.
If that value can't be read, the job falls back to the newest published major and prompts as it did before the state existed.
The path is read under both `self-release.yml` and `release.yml`, because a consumer frozen on an older major runs *that* major's copy of the reader and can never learn a new path — so renaming this file again means teaching the reader the new name and shipping that first ([ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md)).

A single producer-side rollup of *every* consumer's state is intentionally **not** built — it would need a broad cross-owner credential — and is left as a possible future addition.

## Testing the decision without moving anything

`self-release.yml` has a `workflow_dispatch` with a `dry_run` input (**default `true`**).
Run it to print the plan — *create*, *fast-forward*, or *nothing to do* — without touching any branch:

> **🤖 Agent** — trigger it with `mcp__github__actions_run_trigger` (`workflow_id: self-release.yml`, `ref: main`); the run's log shows the `[dry-run] would …` notice.
> Set `dry_run: false` only to force a real advance (e.g. bootstrapping or recovery).

If `self-release.yml` fails with **"not an ancestor of main"**, the major branch has diverged from `main` (history was rewritten, or it was moved by hand).
Reconcile the branch before the next merge; the workflow refuses to force a non-fast-forward on its own.

## Branch protection

`v*` and `main` move **only** by the release workflow (fast-forwarding a `v*` branch) or a merged PR — never a direct human or agent push.
This is the **standard branch protection managed as code by [`flungo/terraform-github`](https://github.com/flungo/terraform-github)**, not set by hand here — `owners/flungo/github-workflows.tf` declares the `v*` pattern and the release App's bypass through the composite's `release_branches` input:

- **`main`** — require a pull request before merging; block force-pushes; block deletion.
  Repository admins keep a deliberate **pull-request-scoped** bypass — they may merge a PR that doesn't meet the rules — but cannot push straight to the branch.
- **`v*`** (pattern `v[0-9]*`) — the same, **plus an `always` bypass for the release App** ([below](#release-push-identity)), so `self-release.yml`'s fast-forward is allowed while direct human/agent pushes are not.
  It also **restricts creation** to that App: only `self-release.yml` can cut a new major, and no one can create an unrelated branch under the pattern.
  Reverts and backports reach `v*` as ordinary PRs (base `v*`), which the force-push block still permits (a revert is a forward commit) — advancing a release branch by PR stays open by design.

### Release-push identity

The default `GITHUB_TOKEN` (`github-actions[bot]`) generally cannot be a ruleset bypass actor, so `self-release.yml` pushes as a **GitHub App**: it mints a short-lived installation token in-run with [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token) and uses it for checkout and push, so there is no long-lived push credential to rotate.

Inventory — everything this identity adds to the repo:

| Item | Kind | Purpose |
| --- | --- | --- |
| Release App | GitHub App owned by `flungo`, installed on **this repo only**, repository permission **Contents: read & write** and nothing else | The push identity; the **bypass actor** on the `v*` ruleset |
| `RELEASE_APP_ID` | Actions **variable** on this repo | The App's ID (not sensitive). Required — `self-release.yml` fails without it |
| `RELEASE_APP_PRIVATE_KEY` | Actions **secret** on this repo | A private key generated for the App (PEM), used only to mint the in-run token |

To provision (once) — all under the `flungo` account:

1. **Create the App** — [Settings → Developer settings → GitHub Apps → New GitHub App](https://github.com/settings/apps/new):
   - **GitHub App name** — globally unique across GitHub: `flungo-release` (pushes then appear as `flungo-release[bot]`).
   - **Homepage URL** — required but cosmetic; this repo's URL.
   - **Webhook** — untick **Active** (which also drops the webhook-URL requirement).
     The App never receives events; it exists only to mint tokens.
   - **Repository permissions** — **Contents: Read and write**; leave everything else at "No access" (the mandatory read-only Metadata permission is added automatically).
   - **Where can this GitHub App be installed?** — **Only on this account**.
2. **Record the App ID and generate the key** — on the App's **General** page after creation: copy the **App ID** (the `RELEASE_APP_ID` value), then **Private keys → Generate a private key**, which downloads a `.pem` (the `RELEASE_APP_PRIVATE_KEY` value).
3. **Install it** — App page → **Install App** → the `flungo` account → **Only select repositories** → this repository only.
4. **Configure this repo** — Settings → Secrets and variables → Actions: add the **variable** `RELEASE_APP_ID` (the numeric App ID) and the **secret** `RELEASE_APP_PRIVATE_KEY` (the *entire* `.pem` contents, including the `-----BEGIN/END RSA PRIVATE KEY-----` lines).
   Then delete the downloaded `.pem` — the key stays registered on the App, and the secret is the only copy needed.
5. **Add the bypass actor** — in the `v[0-9]*` ruleset managed by `terraform-github`.
   For this repo it is already declared, in `owners/flungo/github-workflows.tf`, via the composite's `release_branches` input ([#13](https://github.com/flungo/terraform-github/issues/13)); the ruleset it produces carries:

   ```hcl
   bypass_actors {
     actor_type  = "Integration"
     actor_id    = <App ID>    # same number as RELEASE_APP_ID
     bypass_mode = "always"
   }
   ```

   and, in the same ruleset's `rules` block, `creation = true` — set by the composite as `restrict_creation` — limiting *creation* of a matching branch to that same App ([terraform-github#29](https://github.com/flungo/terraform-github/pull/29)).
   Grep the caller for `restrict_creation`, not `creation`.

   The App must be installed on the repo (step 3) for the bypass to take effect.
   `main`'s ruleset gets **no App bypass** — only the standard pull-request-scoped admin one, which cannot push directly.
6. **Verify** — on the next merge to `main`, the Release run's log shows the *Mint release App token* step succeeding and the usual `Released: …` notice.
   A [dry-run dispatch](#testing-the-decision-without-moving-anything) gives the same confirmation without moving anything.

To rotate: generate a new private key on the App, update `RELEASE_APP_PRIVATE_KEY`, then delete the old key.
Exposure of the key is bounded by the App's single permission and single-repo installation.

## Never

- **Never create a `vN` tag.**
  With both a `vN` tag and a `vN` branch, `@vN` is ambiguous.
  This repo uses branches only.
- **Never rename or delete the current major branch.**
  Consumers resolve `@vN` against it.
  The ruleset blocks deletion outright — no human can, the admin bypass being pull-request-scoped — and a rename needs a create, which is restricted to the release App.
  Doing either deliberately means updating `MAJOR_BRANCH` *and* temporarily relaxing the ruleset in `terraform-github`.
- **Never create a `v[0-9]*` branch by hand** — you can't: creation of any matching ref is restricted to the release App, so the attempt is rejected, admins included (the admin bypass is pull-request-scoped and covers neither creation nor deletion).
  The pattern is fnmatch rather than a regex, so it catches `v9`, `v1x` and `v2-test` too.
  The cost it guards against is worst for an *exact* name: a hand-made `v3` would appear to every opted-in consumer as a published major nobody cut.
  Since [ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md) that no longer raises migration issues — [`flungo-workflows.yml`](../../.github/workflows/flungo-workflows.yml) prompts against `STABLE_MAJOR`, which such a branch does not touch — but it still reports the phantom major as settling in every consumer's issue, and the ruleset remains the thing that stops it.
  The rejection message explains none of this, so give scratch branches a name outside the pattern and let `self-release.yml` cut the real ones.
  Bootstrapping or restoring a `v*` branch by hand means temporarily relaxing the ruleset in `terraform-github`.
- **Never force-push a `v*` branch** — consumers pin these branches, and a rewrite changes history under them.
  The ruleset now enforces this: the admin bypass is pull-request-scoped, so **no human can force-push `v*`**.
  Only the release App holds an `always` bypass, and `self-release.yml` refuses any non-fast-forward move itself.
  A genuine last-resort recovery therefore means deliberately and temporarily relaxing the ruleset in `terraform-github` — never a quiet local `--force`.
