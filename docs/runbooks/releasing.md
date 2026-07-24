# Releasing: how `@vN` advances

How a change here reaches the repos that pin `@vN`. The model is [ADR-003](../decisions/003-version-via-moving-v1-branch.md): consumers pin a moving major **branch** (`v1`, later `v2`, …), and [`release.yml`](../../.github/workflows/release.yml) advances it automatically on every merge to `main`. Most of the time there is nothing to do.

## The normal case — a non-breaking change

Nothing beyond the usual PR. When your PR merges to `main`:

1. `release.yml` runs on the push to `main`.
2. It fast-forwards the current major branch (the one named by `MAJOR_BRANCH` in `release.yml`) to the merged commit.
3. Consumers pinning `@v<current>` pick it up on their next run — no bump on their side.

The review gate is the PR into `main`. There is no separate release PR and no tag to move.

## Making a breaking change you foresee: cut the next major

A change is **breaking** when it would fail an existing caller: renaming or removing an input, adding a required secret, or changing a workflow's default behaviour. (Docs, internal refactors, and new *optional* inputs are **not** breaking.)

In the **same PR** as the breaking change:

1. Edit `MAJOR_BRANCH` in `release.yml` — bump it one major, e.g. `v1` → `v2`.
2. **Update the docs that track the latest version.** Search the repo for `v<old>` — broader than `@v<old>`, so it also catches prose and tables that name the version without the `@`, at the cost of more matches to sift — and bump every reference meant to show consumers the current major (the [README](../../README.md) and the adoption runbooks: [Terraform](adopting-terraform-workflows.md), [Markdown](adopting-markdown-workflows.md)) to the new major. Leave version-specific mentions — historical and migration notes — as they are.
3. Land the PR as normal.

On merge, `release.yml` sees the new name, **creates `v2` at `main`**, and never touches `v1` again — so `@v1` consumers **freeze** on their last compatible commit. That one-line edit, visible in the PR diff, is the whole "this is a major" decision; there is nothing else to parse or label.

Then, on each consumer, migrate `@v1` → `@v2` when you're ready and have accommodated the breaking change. Consumers move deliberately — nothing is pushed onto them. Opted-in consumers raise their own migration reminder — see [Tracking consumer migration](#tracking-consumer-migration).

## A breaking change you didn't foresee

When an incompatibility is noticed only *after* it merged — `release.yml` has already fast-forwarded `@v<current>` onto it:

1. **Prefer fixing it forward.** If compatibility can be restored on `main` — re-add the removed input as optional, reinstate the old default — do that. The next merge advances the fix onto `@v<current>` and no new major is needed. Cutting a major forces *every* downstream repo to migrate, so avoid it unless the change genuinely can't be reconciled.
2. **If a new major is truly required:**
   - **Cut the next major:** follow [Making a breaking change you foresee](#making-a-breaking-change-you-foresee-cut-the-next-major), then come back here. The new major branch is created at `main` with the breaking change and becomes the new line.
   - **Then restore the old major:** open a PR targeting `v1` (base `v1`) that reverts the breaking additions. It lands as an ordinary forward commit, so `@v1` consumers get the change and then its revert, ending compatible again. `v1` is then frozen except for such PRs.

## Patching a frozen major

Once a newer major exists, `release.yml` no longer advances the older one. To fix a bug on a frozen `v1`, open a PR **targeting `v1`** (base `v1`) with the patch — written directly or cherry-picked from `main`. It merges straight onto `v1`; nothing auto-advances it.

## Tracking consumer migration

Nothing forces a consumer off a frozen major, so a repo can silently lag on `@v<old>` after a new major is cut. To surface that, consumers **opt in** to the reusable [`version-check.yml`](../../.github/workflows/version-check.yml): on a schedule it compares the majors that consumer pins against the latest published here, and opens — then auto-closes — a tracking issue **in that consumer's own repo** when it's on a frozen major. It needs no credential (the consumer reads this public repo's majors and writes the issue with its own token). See the opt-in caller in the adoption runbooks ([Terraform](adopting-terraform-workflows.md#version-check-opt-in), [Markdown](adopting-markdown-workflows.md#version-check-opt-in)) and [ADR-004](../decisions/004-version-check-opt-in.md).

A single producer-side rollup of *every* consumer's state is intentionally **not** built — it would need a broad cross-owner credential — and is left as a possible future addition.

## Testing the decision without moving anything

`release.yml` has a `workflow_dispatch` with a `dry_run` input (**default `true`**). Run it to print the plan — *create*, *fast-forward*, or *nothing to do* — without touching any branch:

> **🤖 Agent** — trigger it with `mcp__github__actions_run_trigger` (`workflow_id: release.yml`, `ref: main`); the run's log shows the `[dry-run] would …` notice. Set `dry_run: false` only to force a real advance (e.g. bootstrapping or recovery).

If `release.yml` fails with **"not an ancestor of main"**, the major branch has diverged from `main` (history was rewritten, or it was moved by hand). Reconcile the branch before the next merge; the workflow refuses to force a non-fast-forward on its own.

## Branch protection

`v*` and `main` move **only** by the release workflow (fast-forwarding a `v*` branch) or a merged PR — never a direct human or agent push. This is the **standard branch protection managed as code by [`flungo/terraform-github`](https://github.com/flungo/terraform-github)**, not set by hand here:

- **`main`** — require a pull request before merging; block force-pushes; block deletion.
- **`v*`** (pattern `v[0-9]*`) — the same, **plus a bypass for the release workflow's push identity**, so `release.yml`'s fast-forward is allowed while direct human/agent pushes are not. Reverts and backports reach `v*` as ordinary PRs (base `v*`), which the force-push block still permits (a revert is a forward commit).

**Status:** not yet applied — rollout is tracked in [flungo/terraform-github#13](https://github.com/flungo/terraform-github/issues/13). The one open detail is the bypass identity: the default `GITHUB_TOKEN` (`github-actions[bot]`) generally can't be a ruleset bypass actor, so `release.yml`'s push will need a GitHub App token or fine-grained PAT — carried in [github-workflows#6](https://github.com/flungo/github-workflows/issues/6).

> **🤖 Agent** — if that identity moves off `github.token`, update `release.yml`'s checkout + push to use it and record the secret in the repo's inventory.

## Never

- **Never create a `vN` tag.** With both a `vN` tag and a `vN` branch, `@vN` is ambiguous. This repo uses branches only.
- **Never rename or delete the current major branch** without updating `MAJOR_BRANCH` — consumers resolve `@vN` against it.
- **Never force-push a `v*` branch** except as a documented last-resort recovery, and only by a maintainer with bypass — consumers pin these branches, and a rewrite changes history under them.
