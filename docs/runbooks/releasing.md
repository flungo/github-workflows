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

On merge, `release.yml` sees the new name, **creates `v2` at `main`**, and never touches `v1` again — so `@v1` consumers **freeze** on their last compatible commit. Don't pre-create `v2` by hand: creation is restricted to the release App and the push would be rejected (see [Never](#never)). That one-line edit, visible in the PR diff, is the whole "this is a major" decision; there is nothing else to parse or label.

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

Nothing forces a consumer off a frozen major, so a repo can silently lag on `@v<old>` after a new major is cut. To surface that, consumers **opt in** to the reusable [`version-check.yml`](../../.github/workflows/version-check.yml): on a schedule it compares the majors that consumer pins against the latest published here, and opens — then auto-closes — a tracking issue **in that consumer's own repo** when it's on a frozen major. It needs no credential (the consumer reads this public repo's majors and writes the issue with its own token). See [`adopting-version-check.md`](adopting-version-check.md) for the opt-in caller, and [ADR-004](../decisions/004-version-check-opt-in.md).

A single producer-side rollup of *every* consumer's state is intentionally **not** built — it would need a broad cross-owner credential — and is left as a possible future addition.

## Testing the decision without moving anything

`release.yml` has a `workflow_dispatch` with a `dry_run` input (**default `true`**). Run it to print the plan — *create*, *fast-forward*, or *nothing to do* — without touching any branch:

> **🤖 Agent** — trigger it with `mcp__github__actions_run_trigger` (`workflow_id: release.yml`, `ref: main`); the run's log shows the `[dry-run] would …` notice. Set `dry_run: false` only to force a real advance (e.g. bootstrapping or recovery).

If `release.yml` fails with **"not an ancestor of main"**, the major branch has diverged from `main` (history was rewritten, or it was moved by hand). Reconcile the branch before the next merge; the workflow refuses to force a non-fast-forward on its own.

## Branch protection

`v*` and `main` move **only** by the release workflow (fast-forwarding a `v*` branch) or a merged PR — never a direct human or agent push. This is the **standard branch protection managed as code by [`flungo/terraform-github`](https://github.com/flungo/terraform-github)**, not set by hand here — `owners/flungo/github-workflows.tf` declares the `v*` pattern and the release App's bypass through the composite's `release_branches` input:

- **`main`** — require a pull request before merging; block force-pushes; block deletion. Repository admins keep a deliberate **pull-request-scoped** bypass — they may merge a PR that doesn't meet the rules — but cannot push straight to the branch.
- **`v*`** (pattern `v[0-9]*`) — the same, **plus an `always` bypass for the release App** ([below](#release-push-identity)), so `release.yml`'s fast-forward is allowed while direct human/agent pushes are not. It also **restricts creation** to that App: only `release.yml` can cut a new major, and no one can create an unrelated branch under the pattern. Reverts and backports reach `v*` as ordinary PRs (base `v*`), which the force-push block still permits (a revert is a forward commit) — advancing a release branch by PR stays open by design.

### Release-push identity

The default `GITHUB_TOKEN` (`github-actions[bot]`) generally cannot be a ruleset bypass actor, so `release.yml` pushes as a **GitHub App**: it mints a short-lived installation token in-run with [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token) and uses it for checkout and push, so there is no long-lived push credential to rotate.

Inventory — everything this identity adds to the repo:

| Item | Kind | Purpose |
|---|---|---|
| Release App | GitHub App owned by `flungo`, installed on **this repo only**, repository permission **Contents: read & write** and nothing else | The push identity; the **bypass actor** on the `v*` ruleset |
| `RELEASE_APP_ID` | Actions **variable** on this repo | The App's ID (not sensitive). Required — `release.yml` fails without it |
| `RELEASE_APP_PRIVATE_KEY` | Actions **secret** on this repo | A private key generated for the App (PEM), used only to mint the in-run token |

To provision (once) — all under the `flungo` account:

1. **Create the App** — [Settings → Developer settings → GitHub Apps → New GitHub App](https://github.com/settings/apps/new):
   - **GitHub App name** — globally unique across GitHub: `flungo-release` (pushes then appear as `flungo-release[bot]`).
   - **Homepage URL** — required but cosmetic; this repo's URL.
   - **Webhook** — untick **Active** (which also drops the webhook-URL requirement). The App never receives events; it exists only to mint tokens.
   - **Repository permissions** — **Contents: Read and write**; leave everything else at "No access" (the mandatory read-only Metadata permission is added automatically).
   - **Where can this GitHub App be installed?** — **Only on this account**.
2. **Record the App ID and generate the key** — on the App's **General** page after creation: copy the **App ID** (the `RELEASE_APP_ID` value), then **Private keys → Generate a private key**, which downloads a `.pem` (the `RELEASE_APP_PRIVATE_KEY` value).
3. **Install it** — App page → **Install App** → the `flungo` account → **Only select repositories** → this repository only.
4. **Configure this repo** — Settings → Secrets and variables → Actions: add the **variable** `RELEASE_APP_ID` (the numeric App ID) and the **secret** `RELEASE_APP_PRIVATE_KEY` (the *entire* `.pem` contents, including the `-----BEGIN/END RSA PRIVATE KEY-----` lines). Then delete the downloaded `.pem` — the key stays registered on the App, and the secret is the only copy needed.
5. **Add the bypass actor** — in the `v[0-9]*` ruleset managed by `terraform-github`. For this repo it is already declared, in `owners/flungo/github-workflows.tf`, via the composite's `release_branches` input ([#13](https://github.com/flungo/terraform-github/issues/13)); the ruleset it produces carries:

   ```hcl
   bypass_actors {
     actor_type  = "Integration"
     actor_id    = <App ID>    # same number as RELEASE_APP_ID
     bypass_mode = "always"
   }
   ```

   and, in the same ruleset's `rules` block, `creation = true` — set by the composite as `restrict_creation` — limiting *creation* of a matching branch to that same App ([terraform-github#29](https://github.com/flungo/terraform-github/pull/29)). Grep the caller for `restrict_creation`, not `creation`.

   The App must be installed on the repo (step 3) for the bypass to take effect. `main`'s ruleset gets **no App bypass** — only the standard pull-request-scoped admin one, which cannot push directly.
6. **Verify** — on the next merge to `main`, the Release run's log shows the *Mint release App token* step succeeding and the usual `Released: …` notice. A [dry-run dispatch](#testing-the-decision-without-moving-anything) gives the same confirmation without moving anything.

To rotate: generate a new private key on the App, update `RELEASE_APP_PRIVATE_KEY`, then delete the old key. Exposure of the key is bounded by the App's single permission and single-repo installation.

## Never

- **Never create a `vN` tag.** With both a `vN` tag and a `vN` branch, `@vN` is ambiguous. This repo uses branches only.
- **Never rename or delete the current major branch.** Consumers resolve `@vN` against it. The ruleset blocks deletion outright — no human can, the admin bypass being pull-request-scoped — and a rename needs a create, which is restricted to the release App. Doing either deliberately means updating `MAJOR_BRANCH` *and* temporarily relaxing the ruleset in `terraform-github`.
- **Never create a `v[0-9]*` branch by hand** — you can't: creation of any matching ref is restricted to the release App, so the attempt is rejected, admins included (the admin bypass is pull-request-scoped and covers neither creation nor deletion). The pattern is fnmatch rather than a regex, so it catches `v9`, `v1x` and `v2-test` too. The cost it guards against is worst for an *exact* name: a hand-made `v2` would make [`version-check.yml`](../../.github/workflows/version-check.yml) read `v2` as the latest published major and raise migration issues in every opted-in consumer, for a major nobody cut. The rejection message explains none of this, so give scratch branches a name outside the pattern and let `release.yml` cut the real ones. Bootstrapping or restoring a `v*` branch by hand means temporarily relaxing the ruleset in `terraform-github`.
- **Never force-push a `v*` branch** — consumers pin these branches, and a rewrite changes history under them. The ruleset now enforces this: the admin bypass is pull-request-scoped, so **no human can force-push `v*`**. Only the release App holds an `always` bypass, and `release.yml` refuses any non-fast-forward move itself. A genuine last-resort recovery therefore means deliberately and temporarily relaxing the ruleset in `terraform-github` — never a quiet local `--force`.
