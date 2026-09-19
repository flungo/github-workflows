# Plan: stage and cut the v3 major

Status: **scope agreed, execution model agreed — pre-cut work in progress**.
Tracked to completion, then retired ([plans convention](README.md)); the permanent record of each decision lands in the reference docs and, where architectural, an ADR at cut time.

This plan originally scoped **v2**.
While it was in review, the check-context naming decisions ([ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md), [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md), [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md)) claimed the v2 slot: that cut was small, self-contained, and urgent, where this plan's scope is broad and deliberately unhurried.
The items here therefore ride **v3**, on their own timeline (the reasoning is recorded in ADR-011).
That baseline is now real, not assumed: v2 has been cut **and promoted to stable** ([ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md)), and every active consumer pins `@v2` with filename job IDs and a `flungo-workflows.yml` caller (verified 2026-09-17 against the consumers' live workflow files).

Majors are expensive under the [moving-branch model](../decisions/003-version-via-moving-v1-branch.md): every consumer migrates by hand, and the old major freezes the moment the cut merges ([releasing.md](../runbooks/releasing.md)).
So the scope rule for this cut is strict, in both directions:

- **Anything breaking that is worth doing rides this one cut** — a second near-term major would double the fleet's migration cost.
  (The v2/v3 split was a deliberate, argued exception to this rule, not a precedent — see ADR-011.)
- **Anything additive is excluded** — it ships on the current major (per [ADR-003](../decisions/003-version-via-moving-v1-branch.md) new optional inputs are not breaking) and must not wait for the cut.

This plan records the agreed scope, the pre-cut work, what was deliberately rejected, the migration path per consumer, the staged cut-to-promotion procedure, and what happens to `v2`.
It makes **no contract change itself** and never touches `MAJOR_BRANCH` or `STABLE_MAJOR`: the future cut PR bumps the first, and the promotion at the end of this plan bumps the second.

## Execution model

[ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md) split cutting a major from asking anyone to adopt it, and this plan uses that deliberately (agreed 2026-09-17):

1. **Pre-cut** — finish this plan and land every identified prerequisite and non-breaking improvement on `v2` (see [§ Pre-cut work](#pre-cut-work--gates-the-cut)).
2. **Cut** — bump `MAJOR_BRANCH` to `v3`; the new major is published but *settling*, and `STABLE_MAJOR` stays `v2`, so no consumer is prompted.
3. **Settle** — implement the six scope items as ordinary PRs on `main` during the settling window; anything found wrong lands in place, with no v4 needed.
4. **Adopt** — once the scope is fully implemented, migrate **all** of the fleet's repositories, one PR each, fixing on `v3` whatever the migrations surface.
5. **Promote** — when every repository has adopted and is green, bump `STABLE_MAJOR` to `v3`; only then do the adoption docs move and the version check start holding the fleet to v3.

## What was reviewed

Every product's public contract — inputs, secrets, defaults, filenames, and documented behaviour — across all four families, read as a consumer would:

- **Terraform**: [`terraform.yml`](../../.github/workflows/terraform.yml), [`terraform-drift.yml`](../../.github/workflows/terraform-drift.yml), plus the [`export-terraform-variables`](../../.github/actions/export-terraform-variables/action.yml) composite action behind them ([ADR-009](../decisions/009-composite-action-via-workflow-identity-checkout.md)).
- **Terraform provider**: [`terraform-provider-test.yml`](../../.github/workflows/terraform-provider-test.yml), [`terraform-provider-docs.yml`](../../.github/workflows/terraform-provider-docs.yml), [`terraform-provider-release.yml`](../../.github/workflows/terraform-provider-release.yml).
- **Markdown**: [`markdown-lint.yml`](../../.github/workflows/markdown-lint.yml), [`markdown-links.yml`](../../.github/workflows/markdown-links.yml).
- **Version check**: `version-check.yml`, since become the `version-check` job of [`flungo-workflows.yml`](../../.github/workflows/flungo-workflows.yml) at v2 ([ADR-012](../decisions/012-flungo-workflows-meta-workflow.md)).

[`markdown-sembr.yml`](../../.github/workflows/markdown-sembr.yml) postdates the review ([ADR-015](../decisions/015-semantic-line-break-check.md)): its contract is new and carries no v3 change, so its callers migrate with a pin bump like the rest of the Markdown family.

The review also covered every known consumer's actual caller workflows (originally on `@v1`; re-verified on `@v2`): `terraform-github`, `terraform-grafana-cloud`, `terraform-provider-stalwart`, `terraform-cloudflare` (empty repo — no CI yet), plus the Markdown-only consumers named in the runbooks (`stalwart.flungo.net`, `claude-plugins`).

## The v3 scope — breaking changes riding the cut

Six items, all contract changes on the Terraform and provider families.
The Markdown and `flungo-workflows` families ship **no** breaking change in v3: their consumers migrate with a pin bump only.

### 1. Remove `tf-var-name` + `provider_token` (deprecate-first)

**Class: deprecate-first** — warn on `v2` now, remove in v3.
Seeded from the [#23](https://github.com/flungo/github-workflows/pull/23) review and CLAUDE.md § Deferred follow-ups.

The bespoke provider-token pair on `terraform.yml` / `terraform-drift.yml` predates `tf_secret_vars` ([ADR-008](../decisions/008-secret-terraform-variables.md)) and is strictly worse than the path that superseded it:

- **Redundant** — a provider token is just one more secret variable; a `tf_secret_vars` entry produces the identical masked `TF_VAR_*` export.
- **Inconsistent contract** — `tf-var-name` takes the *full env var name* (`TF_VAR_github_token`) while `tf_secret_vars` keys are *bare variable names* (`github_token`); two shapes for the same concept.
- **Weaker handling** — the `provider_token` path masks the value with a single `::add-mask::`, so a multi-line credential would leak from its second line; the `tf_secret_vars` path masks per line.
  The pair also bypasses `tf_secret_vars`' fail-loud validation (`tf-var-name` is exported unvalidated; an empty `provider_token` exports silently).

**v3 change:** delete the `tf-var-name` input and `provider_token` secret from both workflows and the composite action's corresponding inputs.
**Pre-cut change on `v2` (additive):** `export.sh` emits a `::warning::` pointing at this plan whenever `tf-var-name` is set, so a straggler frozen behind the cut sees the pointer in its own logs.
**Consumer move:** fold the token into the secret-vars map — e.g. `provider_token: ${{ secrets.FLUNGO_GITHUB_TOKEN }}` + `tf-var-name: TF_VAR_github_token` becomes a `"github_token": ${{ toJSON(secrets.FLUNGO_GITHUB_TOKEN) }}` entry.
The reference guidance that the provider token is never Terraform-managed is unchanged — only the transport moves.

### 2. Converge input naming: kebab-case inputs, `UPPER_SNAKE_CASE` secrets

**Class: breaking** (renames).
Seeded from the #23 review and CLAUDE.md § Deferred follow-ups.

The convention this cut adopts, and the reasoning:

- **Inputs: kebab-case.**
  Eleven of the fourteen multi-word input names are already kebab (`working-directory`, `go-version-file`, `plan-artifact-name`, …); only `tf_vars` and `force_run` are snake (plus `tf-var-name`, which item 1 removes).
  Kebab also matches GitHub's own first-party action inputs, and the job-ID convention [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md) settled on.
  Converging the other way would rename eleven inputs instead of two.
- **Secrets: `UPPER_SNAKE_CASE`.**
  Secret names cannot contain hyphens (GitHub restricts them to alphanumerics + underscore), so kebab is not available; four of the five current secrets (`TF_TOKEN_APP_TERRAFORM_IO`, `GPG_PRIVATE_KEY`, `PASSPHRASE`, `LYCHEE_GITHUB_TOKEN`) are already upper-snake, and it matches how the values are stored on the caller side.
  The case split doubles as a visual secret/non-secret marker.

**v3 renames:**

| Old | New | Where |
| --- | --- | --- |
| `tf_vars` (input) | `tf-vars` | `terraform.yml`, `terraform-drift.yml` |
| `force_run` (input) | `force-run` | `terraform-drift.yml` |
| `tf_secret_vars` (secret) | `TF_SECRET_VARS` | `terraform.yml`, `terraform-drift.yml` |

ADR-008's deliberate secret/non-secret pairing survives as `tf-vars` / `TF_SECRET_VARS`.
Single-word names (`operation`, `version`) and all existing kebab inputs are untouched.
The composite action's own input names are internal (consumers never call it directly) and follow along without being contract.

### 3. Rename the `PASSPHRASE` secret to `GPG_PASSPHRASE`

**Class: breaking** (secret rename), found in this review.

`terraform-provider-release.yml` takes `GPG_PRIVATE_KEY` and `PASSPHRASE`.
The bare name is unnamespaced in exactly the way [`LYCHEE_GITHUB_TOKEN`'s prefix exists to prevent](../reference/markdown-validation.md#lychee_github_token-provisioning): stored as an org-level secret, `PASSPHRASE` says nothing about what it unlocks and invites collision with any other job's passphrase.
`GPG_PASSPHRASE` pairs it with `GPG_PRIVATE_KEY`.
One caller line in one consumer (`terraform-provider-stalwart`); rename the stored repo secret in the same change.

### 4. `terraform.yml`: a `fmt` failure fails the run

**Class: breaking** (default-behaviour change), found in this review.
**Decided 2026-09-17: in — bad formatting should block a merge.**

Today `terraform fmt -check` runs with `continue-on-error`: its failure shows as a red cell in the PR comment's table, but the check stays green and an apply still proceeds.
That contradicts the repo's own "validate before it reaches `main`" stance — a formatting regression can merge (and auto-apply) behind a green check, visible only to someone who reads the comment table.
In v3 the run fails after the plan comment is posted (mirroring the existing plan-failure sequencing), so the table still reports all three outcomes but the check goes red.
No current consumer is knowingly fmt-dirty, so the expected migration cost is zero; the change is behavioural, hence a major.
No opt-out input is added — a consumer that wants non-blocking fmt is a consumer whose formatting drifts, and an input can be added additively later if a real case appears.

### 5. `terraform.yml`: `workflow_dispatch` apply only from the default branch

**Class: breaking** (default-behaviour change), found in this review.

The apply gate is *push to the default branch* **or** *`workflow_dispatch` with `operation: apply`* — and the dispatch arm checks the operation but not the ref.
A dispatch against a feature branch therefore **applies unreviewed configuration**, bypassing the plan-review gate every other path enforces.
v3 adds the same default-branch condition the push arm already has to the dispatch arm.
The documented recovery flows (an on-demand apply after drift or token rotation) dispatch on the default branch and are unaffected; what is lost is applying a not-yet-merged change — which is the point: merge it first.
Expected migration cost: zero (no consumer documents an off-default dispatch apply); classified breaking because it tightens default behaviour an operator may have relied on.

### 6. `terraform.yml`: rename the `terraform` job to `plan-apply`

**Class: breaking** (check-context change).
Added 2026-09-19, when an audit of the post-v2 workflows found this to be the one naming inconsistency the v2 cut left behind.

`terraform / terraform` is the same degenerate context [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md) fixed for `version-check / version-check`: the right half repeats the family instead of naming a role, so it carries no information.
[ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md) left it untouched deliberately — it was the only context required anywhere in the fleet, so preserving it spared v2 a coordinated branch-protection change — but that was cost avoidance at v2's boundary, not a ruling that the name is right.
v3 already migrates every Terraform caller, so the residual cost of finishing the normalisation here is one coordinated string change, and the inconsistency is retired rather than carried into a third major (decided 2026-09-19).

`plan-apply` names the job's role — plan on pull request, apply on push or dispatch — the way `drift` names `terraform-drift.yml`'s job.
The caller half stays `terraform` (the filename, [ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md)), so the context becomes **`terraform / plan-apply`**.

This is **v3's one check-context change**, and it is the one context branch protection actually requires (hardcoded by `terraform-github`'s `standard-repository` module for every repository with its `terraform` flag).
Each Terraform consumer therefore migrates in a single PR — pin bump and caller edits together — with the required-check string in `terraform-github` updated immediately before merge, exactly the ordering [`upgrading.md` § v2](../reference/upgrading.md#v2) documents.
Record the decision in an ADR at implementation time: it completes ADR-011's deliberate carve-out.

## Pre-cut work — gates the cut

Non-breaking work that lands on `v2` before the cut, so the v3 diff stays pure contract (agreed 2026-09-17: prerequisites complete before cutting).
None of it has shipped yet:

1. **This plan merges** — [#27](https://github.com/flungo/github-workflows/pull/27).
2. **Deprecation warning for `tf-var-name` / `provider_token`** (scope item 1) — a `::warning::` in `export.sh`.
   Land first: the longer it runs on `v2`, the more runs carry the pointer before `v2` freezes.
3. **Fix: wire the dead `terraform-version` input in the provider family.**
   `terraform-provider-test.yml` and `terraform-provider-docs.yml` both declare and document a `terraform-version` input, but neither passes it to `setup-terraform` — it is accepted and silently ignored (the docs check always renders with latest Terraform).
   Wiring it (`terraform_version: ${{ inputs.terraform-version }}`) makes behaviour match the documented contract, and the default (`latest`) means no consumer sees a change.
   A bug fix, not a v3 item.
4. **`self-` prefix for the internal workflows** (`ci.yml` → `self-ci.yml`, `action-tests.yml` → `self-action-tests.yml`, `release.yml` → `self-release.yml`) — seeded from CLAUDE.md § Deferred follow-ups.
   Internal filenames are not consumer contract, so the renames are non-breaking — with one sequencing exception [ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md) introduced: every consumer's `version-check` reads `STABLE_MAJOR` out of `release.yml` by path from `main`, and a frozen major's consumers run that major's copy of the reader.
   So first ship a reader that tolerates both paths, and only rename once the tolerant reader is on every unfrozen major — both steps before the cut, so `v2` freezes tolerant.
   Includes the self-CI guard: a check asserting every *unprefixed* workflow in `.github/workflows/` is `workflow_call`-only (the dogfooded callers in `self-ci.yml` are prefixed; the callee products are `workflow_call`-only).
   Remember the internal references: `releasing.md` and CLAUDE.md name `release.yml` (including as a `workflow_id` for dispatch), and `action-tests.yml`'s coverage job greps its own filename.
5. **Fail loud on an unrecognised `operation`.**
   Anything other than `apply` silently plans today, so a typo'd dispatch (`aply`) reports success having done something other than what was asked.
   Rejecting values outside `plan`/`apply` applies [ADR-008](../decisions/008-secret-terraform-variables.md)'s fail-at-the-point-of-error principle; only already-invalid input is affected, so it is a fix, not a break.
6. **Done — [#38](https://github.com/flungo/github-workflows/issues/38): extract the marker-based upserts into composite actions** (delegated to its own session 2026-09-18, landed 2026-09-19).
   [ADR-018](../decisions/018-one-upsert-action-per-resource.md) resolved the question this plan left open — one action per resource, `issue-upsert` and `pr-comment-upsert`, not one shared action — and the migration covered everything this item subsumed: the missing pagination in `terraform.yml`'s plan-comment upsert and `markdown-links.yml`'s issue listing, and `terraform-drift.yml`'s two near-identical issue scripts.
   It also aligned the plan-truncation limits (both now 60 000), retiring that half of the sweep below.
7. **Internal consistency sweep** (non-contract; the one pre-cut item that does *not* gate the cut): settle `setup-terraform`'s wrapper — enabled by default in the Terraform family, explicitly `terraform_wrapper: false` in the provider family — on one deliberate choice.

## Additive backlog — explicitly out of scope

Improvements noted during the review that need **no major** and are not prerequisites, so they must not hold the cut open.
Each ships on the current major whenever a consumer needs it:

- **Drift parity with `terraform.yml`**: publish the drift plan as an artifact (the [ADR-005](../decisions/005-extend-terraform-workflow-via-plan-artifact.md) seam exists only on `terraform.yml`), and scope the hard-coded `drift` label / `DRIFT_REMEDIATION_PAUSED` variable / `.drift-paused` file per working directory.
  Both matter only for a multi-owner repo running several drift callers — shape them when `terraform-github`'s matrix-over-owners follow-up makes one real.
- **Caller-supplied runner label** on `terraform.yml` (a `runs-on` input defaulting to `ubuntu-latest`) — the `stalwart.flungo.net` LAN-apply case, tracked in that repo's `docs/plans/terraform-ci.md`.
- **`workflow_call` outputs** on `terraform.yml` (plan outcome, change counts) — the plan artifact covers current consumers; outputs are additive when a lighter-weight signal is wanted.
- **Markdown glob input** on `markdown-lint.yml` / `markdown-links.yml` for repos with vendored trees to exclude — no consumer needs it yet.

## Considered and rejected

- **Renaming the products themselves** (GitHub-docs `reusable-*` style, or any filename change) — revisited as instructed, and re-rejected: a product filename is the pinned contract path, so the rename breaks every caller in every consumer for purely cosmetic gain, and no new evidence emerged.
  The `self-` prefix on internals achieves the visible separation non-breakingly.
  *Since qualified by [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md)*: v2 renamed exactly one file (`version-check.yml` → `flungo-workflows.yml`), forced because the [ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md)/[ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md) naming rules degenerate there (`version-check / version-check`) — not a reversal of the cosmetic sweep, which stays rejected.
  No other product is renamed, by that cut or this one.
- **Normalising job ids/display names across families** — **rejected here, then reversed by [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md); it rode the v2 cut rather than this plan.**
  The inconsistency, concretely: nine of the twelve reusable jobs exposed their bare kebab job ID as the check name, while the three Markdown jobs shadowed theirs with a prose `name:` — `markdown-lint.yml`'s `lint` job reported as `markdownlint`, and `markdown-links.yml`'s `internal`/`external` as `Internal links & anchors` / `External URLs` — so check contexts ranged from `terraform / terraform` to `links / Internal links & anchors`, the latter carrying spaces, capitals and an ampersand into any required-check string.
  What was rejected was the normalisation ADR-011 later carried out: drop the `name:`s so every check name is the job's ID.
  The original rejection reasoned that a job's name is check-context contract (required status checks reference it), so the rename would break every consumer's required-check configuration for a purely cosmetic gain.
  ADR-011 answered both halves: the gain stopped being cosmetic once `terraform-github`'s `standard-repository` module began hardcoding the context strings into branch protection (derivability became functional), and the cost was smaller than assumed — exactly one context was required anywhere in the fleet (`terraform / terraform`, which the change left untouched), so the assumed blast radius did not exist.
  Where the rejection was right is that it *is* contract — which is why it cut a major.
  A 2026-09-19 audit of the post-v2 workflows found one residue of the inconsistency still standing — the degenerate `terraform / terraform` context ADR-011 deliberately spared — and it is now [scope item 6](#6-terraformyml-rename-the-terraform-job-to-plan-apply), so nothing of the original inconsistency outlives v3.
- **Changing the `terraform-version` default (`latest`) to a pin** — the consumer's own `required_version` in `terraform.tf` is the governing pin; a pinned workflow default would go stale and add producer churn for no protection.
- **Making `golangci-lint-version` required (no default)** — a stale default is real but is ordinary current-major maintenance (like the Dependabot action bumps, [ADR-007](../decisions/007-track-third-party-actions-with-dependabot.md)); forcing every consumer to pin it sacrifices zero-config adoption.
- **Making `TF_TOKEN_APP_TERRAFORM_IO` optional** (non-HCP backends) — speculative: no consumer needs it, and loosening required → optional is non-breaking, so it can ship on any major later without a cut.
- **Merging `terraform-drift.yml` into `terraform.yml`** — they need different caller grants (`pull-requests: write` vs `issues: write`), different trigger ownership, and drift is opt-in; a merged workflow forces the union of permissions on every caller.
- **Renaming `terraform-provider-release.yml`'s `version` input (e.g. to `tag`)** — arguably clearer, but single-word, convention-compliant, and unambiguous in practice; churn without evidence of confusion.
- **Deriving the multi-directory defaults from `working-directory`** (`concurrency-group`, `plan-comment-marker`, `plan-artifact-name` auto-scoped, sparing a multi-owner repo three mirrored inputs) — changing a default is breaking, single-directory repos would trade today's clean literals for derived values, and the explicit inputs are self-documenting; revisit alongside the drift multi-owner scoping in the additive backlog when `terraform-github`'s matrix-over-owners makes the shape concrete.

## Migration path per consumer

This plan renames no product filenames and exactly **one job ID**: [scope item 6](#6-terraformyml-rename-the-terraform-job-to-plan-apply) changes `terraform.yml`'s context from `terraform / terraform` to `terraform / plan-apply`.
Every other check context established at v2 ([ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md)/[ADR-012](../decisions/012-flungo-workflows-meta-workflow.md), tabulated in [`upgrading.md § v2`](../reference/upgrading.md#v2)) carries through v3 unchanged.
The changed context is the one branch protection requires, so a Terraform consumer's migration is one PR — pin bump and caller edits together — with `terraform-github`'s required-check string updated immediately before merge; Markdown-only and provider consumers see no context change and need no required-check edits.
Beyond that, every migration is a caller-file edit plus the `@v2` → `@v3` pin bumps.
Under the [execution model](#execution-model), adoption is a deliberate fleet-wide phase after the scope is fully implemented — one PR per repository, fixing anything surfaced in place on the settling `v3`.

Caller lists below were re-verified 2026-09-17:

| Consumer | Callers affected | Migration work |
| --- | --- | --- |
| `terraform-github` | `terraform.yml`, `markdown-lint.yml`, `markdown-links.yml`, `markdown-sembr.yml`, `flungo-workflows.yml` callers | Move `provider_token`/`tf-var-name` into the map as `"github_token"`; rename `tf_secret_vars:` → `TF_SECRET_VARS:`; bump 5 pins. Also owns scope item 6's string: update `standard-repository`'s required context to `terraform / plan-apply` and apply it per repo immediately before each Terraform consumer's migration PR merges. The `surface-classic-protection` follow-on job is artifact-contract only — untouched. |
| `terraform-grafana-cloud` | `terraform.yml`, `terraform-drift.yml`, `flungo-workflows.yml` callers | Same provider-token move in both callers (`"grafana_cloud_access_policy_token"` entry); `force_run:` → `force-run:` in the drift caller (the caller's own `workflow_dispatch` input name is its own business); bump 3 pins; required check flips to `terraform / plan-apply` immediately before merge. |
| `terraform-provider-stalwart` | provider `test`/`docs`/`release`, `markdown-lint.yml`, `markdown-links.yml`, `markdown-sembr.yml`, `flungo-workflows.yml` callers | `PASSPHRASE:` → `GPG_PASSPHRASE:` in the release caller and rename the stored repo secret; bump 7 pins. |
| `stalwart.flungo.net` | Markdown callers (+ `flungo-workflows` if adopted) | Pin bumps only — no Markdown contract change in v3. |
| `claude-plugins` | Markdown callers | Pin bumps only. |
| `terraform-cloudflare` | none yet (empty repo) | Nothing to migrate — adopts the stable major directly when onboarded, per the runbooks. |
| `authentik.flungo.net` | none yet (named in [ADR-001](../decisions/001-centralised-reusable-workflows.md) as a future consumer) | Nothing to migrate — adopts the stable major directly. |

Worked example — the `terraform-grafana-cloud` `terraform.yml` caller after migration:

```yaml
jobs:
  terraform:
    permissions:
      contents: read
      pull-requests: write
    uses: flungo/github-workflows/.github/workflows/terraform.yml@v3
    with:
      operation: ${{ github.event.inputs.operation || 'plan' }}
    secrets:
      TF_TOKEN_APP_TERRAFORM_IO: ${{ secrets.TF_TOKEN_APP_TERRAFORM_IO }}
      TF_SECRET_VARS: >-
        {"grafana_cloud_access_policy_token": ${{ toJSON(secrets.GRAFANA_CLOUD_ACCESS_POLICY_TOKEN) }}}
```

The exported env var (`TF_VAR_grafana_cloud_access_policy_token`) is byte-identical to today's, so no `*.tf` change is needed anywhere in the fleet; declaring the consuming variable `sensitive = true` is already the standing guidance.

At adoption time, re-enumerate consumers rather than trusting this table — search each candidate repo's `.github/workflows/` for `flungo/github-workflows/` refs — and open one migration PR per repo.
Any consumer missed will be caught at promotion, when its `version-check` starts comparing against `STABLE_MAJOR: v3`.

## The staged procedure

Per [releasing.md](../runbooks/releasing.md) and [ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md), after the [pre-cut work](#pre-cut-work--gates-the-cut) has landed:

### Cut

1. One PR, on an ordinarily-named feature branch (never a branch matching `v[0-9]*` — creation is restricted to the release App and the rejection message won't say why), carrying:
   - the first scope item's implementation (item 1 is the natural carrier — the largest and the one already deprecation-warned);
   - `MAJOR_BRANCH: v2` → `v3` in the release workflow — the one-line edit that *is* the cut;
   - a draft **`## v3` section in [`upgrading.md`](../reference/upgrading.md)** ([ADR-013](../decisions/013-per-major-upgrade-guide.md)), carrying a settling note as the v2 section did before its cut, and naming the one context change (`terraform / terraform` → `terraform / plan-apply`) with the required-check ordering it needs;
   - `docs/` index refreshes in the same commit, CI green.
2. Do **not** pre-create `v3`, and do **not** touch `STABLE_MAJOR` — on merge, the release workflow creates `v3` at `main` and never advances `v2` again; nobody is prompted to move, and `ci.yml`'s `release-state` job warns on every PR while the majors differ.
3. Verify: the Release run log shows `create v3 at <sha>`; `v2` still points at the last pre-merge commit; a pin of `@v3` resolves.

### Settle

1. Land the remaining scope items as ordinary PRs on `main`; each merge advances the settling `v3`.
   Keep the `upgrading.md` § v3 draft in step as each lands.
2. Anything found wrong with the new contract — during implementation or the adoption below — lands **in place** on `v3`.
   That is the settling window's purpose: no consumer has been asked to move, so a correction costs nobody a migration and no v4.

### Adopt

1. With the scope fully implemented, migrate **every** repository in the fleet per the table above, one PR each.
   For a repository whose branch protection requires `terraform / terraform`, update the required-check string (via `terraform-github`) immediately before merging that repository's migration PR, per [`upgrading.md` § v2](../reference/upgrading.md#v2)'s ordering.
2. Fix whatever the migrations surface (in place, per [§ Settle](#settle)) until every consumer is green on `@v3`.

### Promote

1. Bump `STABLE_MAJOR: v2` → `v3`.
   In the same PR, per ADR-014's "the adoption docs are bumped by the promotion, not the cut": run the docs version sweep — search for `v2` (broader than `@v2`) and bump every reference meant to show consumers the stable major (the README and the adoption runbooks), leaving historical and migration mentions as they are — and drop the settling note from `upgrading.md` § v3.
2. Verify the fleet: every opted-in consumer's next `version-check` run should find its pins already on `@v3` and open nothing; an issue opening anywhere means a repo was missed during [§ Adopt](#adopt) — migrate it.
3. Retire this plan (delete the file, update the plans index) and prune the corresponding CLAUDE.md § Deferred follow-ups entries.

## What happens to v2

- **Freeze point**: the last commit on `main` before the cut PR merges.
  The release workflow never advances `v2` past it ([ADR-003](../decisions/003-version-via-moving-v1-branch.md)).
- **No premature prompting**: because `STABLE_MAJOR` stays `v2` until promotion, a `v2` consumer's `version-check` stays quiet through the whole settling and adoption window ([ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md)) — the fleet is migrated by this plan, not nagged onto a moving contract.
- **Deprecation warnings**: the `tf-var-name` warning shipped pre-cut keeps firing in every `v2` Terraform run, so a straggler sees the pointer to this migration in its own logs, not just in an issue.
- **After promotion**: any repository still pinning `@v2` gets the `version-check` issue, whose upgrade-guide link is pinned to `v3`'s own branch ([ADR-014](../decisions/014-promote-a-major-to-stable-by-hand.md)).
- **Patches**: `v2` is a maintenance branch once frozen — fixes reach it only via PRs based on `v2` (cherry-picks or reverts), expected to be rare and reserved for breakage, per [releasing.md § Patching a frozen major](../runbooks/releasing.md#patching-a-frozen-major).
  (`v1` froze earlier, at the v2 cut, under the same rules.)

## Completion checklist

Pre-cut (gates the cut):

- [ ] This plan merged (#27)
- [ ] Deprecation warning in `export.sh`
- [ ] `terraform-version` wired in both provider workflows
- [ ] `STABLE_MAJOR` reader tolerates both `release.yml` paths, then the `self-` renames + unprefixed-means-`workflow_call`-only guard
- [ ] Fail-loud `operation` fix
- [x] #38 upsert extraction — `issue-upsert` + `pr-comment-upsert` per [ADR-018](../decisions/018-one-upsert-action-per-resource.md), all four call sites migrated

Cut and settle:

- [ ] Cut PR merged (scope item 1 + `MAJOR_BRANCH` + draft `upgrading.md` § v3); `v3` created by the release workflow, `STABLE_MAJOR` untouched
- [ ] Scope items 2–6 landed on the settling `v3` (item 6 with its ADR completing ADR-011's carve-out)
- [ ] `terraform-github`'s `standard-repository` required context updated to `terraform / plan-apply`, rolled out per repo with the migrations below

Adopt:

- [ ] `terraform-github` migrated
- [ ] `terraform-grafana-cloud` migrated
- [ ] `terraform-provider-stalwart` migrated
- [ ] Markdown-only consumers (`stalwart.flungo.net`, `claude-plugins`) bumped
- [ ] Consumer re-enumeration found no other stale-major refs (or they were migrated)

Promote:

- [ ] `STABLE_MAJOR: v3` + docs version sweep + `upgrading.md` § v3 settling note dropped
- [ ] Version check quiet across the fleet
- [ ] Plan retired; CLAUDE.md deferred follow-ups pruned
