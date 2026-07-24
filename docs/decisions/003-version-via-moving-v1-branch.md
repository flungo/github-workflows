# ADR-003: Version via a moving major branch, advanced automatically

Date: 2026-07-23
Status: Accepted

## Context

[ADR-001](001-centralised-reusable-workflows.md) versioned the reusable workflows with a **moving `v1` tag**: consumers pin `uses: …@v1` and the maintainer moves the tag forward as fixes land. Moving a tag is the awkward part of that model:

- Advancing `v1` means `git tag -f v1 && git push --force origin v1` — force-pushing a ref that is conventionally immutable, with no reviewable diff and no record of what a bump contained.
- Force-moving tags is easy to get wrong, and some tooling and branch-protection setups discourage or block it.
- `uses: …@v1` resolves a branch **or** a tag, so there is nothing to review between "fix merged to `main`" and "consumers pick it up".

A branch is the natural home for a ref that is *meant* to move — and a branch can be advanced automatically, on merge, with the PR into `main` as the review gate.

## Decision

Version the reusable workflows with a **moving major branch** (`v1`, later `v2`, …) that is **advanced automatically on every merge to `main`**.

- **Consumers are unchanged.** They keep `uses: flungo/github-workflows/.github/workflows/<name>@v1`; `@v1` resolves the branch.
- **Advancement is automatic.** [`release.yml`](../../.github/workflows/release.yml) runs on every push to `main` and fast-forwards the current major branch to the merged commit. The review gate is the PR into `main` (already reviewed and CI-green) — there is no separate bump PR, and no tag to force-move.
- **The current major is an explicit marker.** `release.yml` names it in one place — its `MAJOR_BRANCH` env var. The workflow only ever advances *that* branch.
- **A major bump is a human, in-diff edit.** A **breaking** change to a reusable workflow's input/secret contract must edit `MAJOR_BRANCH` (e.g. `v1` → `v2`) **in the same PR**. That reviewed one-line change *is* the "is this a major?" decision — no commit-message parsing or labels to get right. When it merges, `release.yml` creates the new major branch at `main`; the previous major branch is simply never advanced again, so `@v<old>` consumers **freeze** on their last compatible commit until they migrate to `@v<new>`.
- **Fast-forward only.** `release.yml` refuses to move a major branch that is not an ancestor of `main`, so it can never rewrite what consumers already have. (It can't catch a breaking change that landed *without* a `MAJOR_BRANCH` bump — that stays a review responsibility, and is fixed forward or with a revert PR onto the affected branch.)
- **Older majors are maintenance branches.** Once a newer major is cut, the previous branch is advanced only by PRs that target it directly (base `vN`): a revert of a breaking change that was shipped before anyone noticed, or a backported fix. `release.yml` never touches it again.
- **`v*` and `main` move only by workflow or PR.** Branch protection — the standard managed as code by [`terraform-github`](https://github.com/flungo/terraform-github), planned but not yet applied (see [`releasing.md`](../runbooks/releasing.md)) — is to forbid direct human/agent pushes: `main` advances only via merged PRs, and `v*` only via `release.yml`'s fast-forward (whose push identity is bypass-listed) or a merged PR.
- **Never create a `vN` tag.** With both a `vN` tag and a `vN` branch present, `@vN` is ambiguous. The old `v1` tag was deleted when this model was adopted.

### Migration (one-off, completed 2026-07-23)

Done by the maintainer with push access; ordered so `@v1` never fails to resolve:

1. `git push origin <v1-tag-commit>:refs/heads/v1` — create the `v1` branch at the commit the tag pointed to, so pinned `@v1` keeps resolving to the exact workflows consumers already run.
2. `git push origin :refs/tags/v1` — delete the `v1` tag so `@v1` resolves unambiguously to the branch.

`release.yml` took over advancement from there — the merge that added it advanced `v1` to `main` automatically.

## Consequences

**Positive:**

- No force-pushed tags and no manual bump step: every merge that passes review advances `@vN`.
- Consumers pinning `@vN` need no change and follow the branch automatically.
- The major-bump decision is explicit and reviewable — a one-line diff — not an implicit property of commit messages.
- Fast-forward-only advancement means a bad state can't be forced onto consumers; rolling back is an ordinary revert PR into `main` (which the next advance carries).

**Negative / trade-offs:**

- A breaking change with a forgotten `MAJOR_BRANCH` bump *will* be auto-advanced onto `@v<current>`. Catching it is a review responsibility; the fast-forward guard does not detect a semantic break.
- A frozen major (`v1` after `v2` is cut) receives no automatic fixes — reverts and backports to it are manual PRs (base `vN`) and expected to be rare.
- Letting `release.yml` fast-forward a protection-ruled `v*` requires a bypass identity the default `GITHUB_TOKEN` may not provide — a fine-grained PAT or a GitHub App token — which becomes a managed dependency of the release automation.
- Renaming/deleting the current major branch, or reintroducing a `vN` tag, breaks resolution; recorded here and in `CLAUDE.md` as hard "never"s.
- Surfacing a consumer that lags on a frozen major is handled by an opt-in per-consumer version check ([ADR-004](004-version-check-opt-in.md)), not a dependency bot; a fleet-wide rollup remains a possible future addition.
