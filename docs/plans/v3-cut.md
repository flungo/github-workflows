# Plan: scope and cut the v3 major

Status: **scoping agreed — pre-cut work not started**.
Tracked to completion, then retired ([plans convention](README.md)); the permanent record of each decision lands in the reference docs and, where architectural, an ADR at cut time.

This plan originally scoped **v2**.
While it was in review, the check-context naming decisions ([ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md), [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md), [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md)) claimed the v2 slot: that cut is small, self-contained, and urgent (`terraform-github` is hardcoding the context strings now), where this plan's scope is broad and deliberately unhurried.
Folding the two agendas together would have forced these five items to be settled at the naming change's pace — the opposite of what this plan exists for — so **the five items here ride v3, on their own timeline** (the reasoning is recorded in ADR-011).
This plan therefore assumes the v2 baseline: consumers pin `@v2`, caller job IDs match workflow filenames, reusable job IDs are the check names, and `version-check.yml` has become `flungo-workflows.yml`.

Majors are expensive under the [moving-branch model](../decisions/003-version-via-moving-v1-branch.md): every consumer migrates by hand, and the old major freezes the moment the cut merges ([releasing.md](../runbooks/releasing.md)).
So the scope rule for this cut is strict, in both directions:

- **Anything breaking that is worth doing rides this one cut** — a second near-term major would double the fleet's migration cost. (The v2/v3 split was a deliberate, argued exception to this rule, not a precedent — see ADR-011.)
- **Anything additive is excluded** — it ships on the current major (per [ADR-003](../decisions/003-version-via-moving-v1-branch.md) new optional inputs are not breaking) and must not wait for, or bloat, the v3 PR.

This plan records the reviewed scope, what was deliberately rejected, the migration path per consumer, the mechanical cut procedure, and what happens to the frozen major.
It makes **no contract change itself** and never touches `MAJOR_BRANCH`: the v2 cut PR bumps it to `v2`, and this plan's future cut PR bumps it to `v3`.

## What was reviewed

Every product's public contract — inputs, secrets, defaults, filenames, and documented behaviour — across all four families, read as a consumer would:

- **Terraform**: [`terraform.yml`](../../.github/workflows/terraform.yml), [`terraform-drift.yml`](../../.github/workflows/terraform-drift.yml), plus the [`export-terraform-variables`](../../.github/actions/export-terraform-variables/action.yml) composite action behind them ([ADR-009](../decisions/009-composite-action-via-workflow-identity-checkout.md)).
- **Terraform provider**: [`terraform-provider-test.yml`](../../.github/workflows/terraform-provider-test.yml), [`terraform-provider-docs.yml`](../../.github/workflows/terraform-provider-docs.yml), [`terraform-provider-release.yml`](../../.github/workflows/terraform-provider-release.yml).
- **Markdown**: [`markdown-lint.yml`](../../.github/workflows/markdown-lint.yml), [`markdown-links.yml`](../../.github/workflows/markdown-links.yml).
- **Version check**: [`version-check.yml`](../../.github/workflows/version-check.yml) (becoming `flungo-workflows.yml` at v2, [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md)).

And every known consumer's actual caller workflows, as they stood on `@v1` at review time: `terraform-github` (`terraform.yml` + follow-on `inspect` job, the version check), `terraform-grafana-cloud` (`terraform.yml`, `terraform-drift.yml`, the version check), `terraform-provider-stalwart` (all three provider callers + both Markdown callers + the version check), `terraform-cloudflare` (empty repo — no CI yet), plus the Markdown-only consumers named in the runbooks (`stalwart.flungo.net`, `claude-plugins`).

## The v3 scope — breaking changes riding the cut

Five items, all contract changes on the Terraform and provider families.
The Markdown and `flungo-workflows` families ship **no** breaking change in v3: their consumers migrate with a pin bump only.

### 1. Remove `tf-var-name` + `provider_token` (deprecate-first)

**Class: deprecate-first** — warn on the current major now, remove in v3.
Seeded from the [#23](https://github.com/flungo/github-workflows/pull/23) review and CLAUDE.md § Deferred follow-ups.

The bespoke provider-token pair on `terraform.yml` / `terraform-drift.yml` predates `tf_secret_vars` ([ADR-008](../decisions/008-secret-terraform-variables.md)) and is strictly worse than the path that superseded it:

- **Redundant** — a provider token is just one more secret variable; a `tf_secret_vars` entry produces the identical masked `TF_VAR_*` export.
- **Inconsistent contract** — `tf-var-name` takes the *full env var name* (`TF_VAR_github_token`) while `tf_secret_vars` keys are *bare variable names* (`github_token`); two shapes for the same concept.
- **Weaker handling** — the `provider_token` path masks the value with a single `::add-mask::`, so a multi-line credential would leak from its second line; the `tf_secret_vars` path masks per line. The pair also bypasses `tf_secret_vars`' fail-loud validation (`tf-var-name` is exported unvalidated; an empty `provider_token` exports silently).

**v3 change:** delete the `tf-var-name` input and `provider_token` secret from both workflows and the composite action's corresponding inputs.
**Current-major change (pre-cut, additive):** `export.sh` emits a `::warning::` pointing at this plan whenever `tf-var-name` is set — it fires for current callers immediately and keeps firing on every major that advances after it lands, so a straggler frozen behind the cut sees it in its own logs.
**Consumer move:** fold the token into the secret-vars map — e.g. `provider_token: ${{ secrets.FLUNGO_GITHUB_TOKEN }}` + `tf-var-name: TF_VAR_github_token` becomes a `"github_token": ${{ toJSON(secrets.FLUNGO_GITHUB_TOKEN) }}` entry.
The reference guidance that the provider token is never Terraform-managed is unchanged — only the transport moves.

### 2. Converge input naming: kebab-case inputs, `UPPER_SNAKE_CASE` secrets

**Class: breaking** (renames).
Seeded from the #23 review and CLAUDE.md § Deferred follow-ups.

The convention this cut adopts, and the reasoning:

- **Inputs: kebab-case.** Eleven of the fourteen multi-word input names are already kebab (`working-directory`, `go-version-file`, `plan-artifact-name`, …); only `tf_vars` and `force_run` are snake (plus `tf-var-name`, which item 1 removes). Kebab also matches GitHub's own first-party action inputs, and the job-ID convention [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md) settled on. Converging the other way would rename eleven inputs instead of two.
- **Secrets: `UPPER_SNAKE_CASE`.** Secret names cannot contain hyphens (GitHub restricts them to alphanumerics + underscore), so kebab is not available; four of the five current secrets (`TF_TOKEN_APP_TERRAFORM_IO`, `GPG_PRIVATE_KEY`, `PASSPHRASE`, `LYCHEE_GITHUB_TOKEN`) are already upper-snake, and it matches how the values are stored on the caller side. The case split doubles as a visual secret/non-secret marker.

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

**Class: breaking** (default-behaviour change), found in this review. *The most debatable item — strike it in review if the current behaviour is preferred.*

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

## Ships on the current major — related work excluded from the cut

Non-breaking work that this review surfaced or the seed items require, landing as ordinary PRs on `main` (mostly *before* the cut, so the v3 diff stays pure contract).
Each rides whatever major branch is current when it merges — `v1` today, `v2` once that cut lands:

1. **Deprecation warning for `tf-var-name` / `provider_token`** (item 1 above) — a `::warning::` in `export.sh`. Land as soon as this plan merges, so it reaches as many majors as possible before they freeze.
2. **Fix: wire the dead `terraform-version` input in the provider family.** `terraform-provider-test.yml` and `terraform-provider-docs.yml` both declare and document a `terraform-version` input, but neither passes it to `setup-terraform` — it is accepted and silently ignored (the docs check always renders with latest Terraform). Wiring it (`terraform_version: ${{ inputs.terraform-version }}`) makes behaviour match the documented contract, and the default (`latest`) means no consumer sees a change. A bug fix, not a v3 item.
3. **`self-` prefix for the internal workflows** (`ci.yml` → `self-ci.yml`, `action-tests.yml` → `self-action-tests.yml`, `release.yml` → `self-release.yml`) — seeded from CLAUDE.md § Deferred follow-ups. Internal filenames are not consumer contract (consumers pin product paths only), so this is non-breaking and **lands ahead of v3, not inside it**: it shortens the file list the cut PR touches and makes the products-vs-self split legible before the docs sweep re-links everything. Includes the self-CI guard: a check asserting every *unprefixed* workflow in `.github/workflows/` is `workflow_call`-only (the dogfooded Markdown calls in `self-ci.yml` still satisfy this — the callee files are `workflow_call`-only; the caller is prefixed). Remember the internal references: `releasing.md` and CLAUDE.md name `release.yml` (including as a `workflow_id` for dispatch), and `action-tests.yml`'s coverage job greps its own filename.
4. **Fix: paginate the plan-comment upsert.** `terraform.yml`'s *Post plan to PR* step lists comments without pagination (the API default of 30), so on a long PR the marker comment can fall past page 1 and a duplicate gets created — the exact comment stack the upsert exists to prevent. `version-check.yml` already uses `github.paginate`; align the other upserts (`terraform.yml`, and `markdown-links.yml`'s single-page-of-100 issue listing) with it.
5. **Fail loud on an unrecognised `operation`.** Anything other than `apply` silently plans today, so a typo'd dispatch (`aply`) reports success having done something other than what was asked. Rejecting values outside `plan`/`apply` applies [ADR-008](../decisions/008-secret-terraform-variables.md)'s fail-at-the-point-of-error principle; only already-invalid input is affected, so it is a fix, not a break.
6. **Internal consistency sweep** (non-contract, whenever convenient): dedupe `terraform-drift.yml`'s two near-identical issue-creation scripts; align the plan-truncation limits (65 000 in `terraform.yml` vs 60 000 in drift); settle `setup-terraform`'s wrapper — enabled by default in the Terraform family, explicitly `terraform_wrapper: false` in the provider family — on one deliberate choice.

## Additive backlog — explicitly out of scope

Improvements noted during the review that need **no major** and therefore must not ride (or wait for) the cut.
Recorded here so the cut isn't held open for them; each ships on the current major whenever a consumer needs it:

- **Drift parity with `terraform.yml`**: publish the drift plan as an artifact (the [ADR-005](../decisions/005-extend-terraform-workflow-via-plan-artifact.md) seam exists only on `terraform.yml`), and scope the hard-coded `drift` label / `DRIFT_REMEDIATION_PAUSED` variable / `.drift-paused` file per working directory. Both matter only for a multi-owner repo running several drift callers — shape them when `terraform-github`'s matrix-over-owners follow-up makes one real.
- **Caller-supplied runner label** on `terraform.yml` (a `runs-on` input defaulting to `ubuntu-latest`) — the `stalwart.flungo.net` LAN-apply case, tracked in that repo's `docs/plans/terraform-ci.md`.
- **`workflow_call` outputs** on `terraform.yml` (plan outcome, change counts) — the plan artifact covers current consumers; outputs are additive when a lighter-weight signal is wanted.
- **Markdown glob input** on `markdown-lint.yml` / `markdown-links.yml` for repos with vendored trees to exclude — no consumer needs it yet.

## Considered and rejected

- **Renaming the products themselves** (GitHub-docs `reusable-*` style, or any filename change) — revisited as instructed, and re-rejected: a product filename is the pinned contract path, so the rename breaks every caller in every consumer for purely cosmetic gain, and no new evidence emerged. The `self-` prefix on internals achieves the visible separation non-breakingly. *Since qualified by [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md)*: v2 renames exactly one file (`version-check.yml` → `flungo-workflows.yml`), forced because the [ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md)/[ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md) naming rules degenerate there (`version-check / version-check`) — not a reversal of the cosmetic sweep, which stays rejected. No other product is renamed, by that cut or this one.
- **Normalising job ids/display names across families** — **rejected here, then reversed by [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md); it rides the v2 cut rather than this plan.** The original rejection reasoned that a job's name is check-context contract (required status checks reference it), so the rename would break every consumer's required-check configuration for a purely cosmetic gain. ADR-011 answered both halves: the gain stopped being cosmetic once `terraform-github`'s `standard-repository` module began hardcoding the context strings into branch protection (derivability became functional), and the cost was smaller than assumed — exactly one context is required anywhere in the fleet (`terraform / terraform`, which the change leaves untouched), so the assumed blast radius did not exist. Where the rejection was right is that it *is* contract — which is why it cuts a major.
- **Changing the `terraform-version` default (`latest`) to a pin** — the consumer's own `required_version` in `terraform.tf` is the governing pin; a pinned workflow default would go stale and add producer churn for no protection.
- **Making `golangci-lint-version` required (no default)** — a stale default is real but is ordinary current-major maintenance (like the Dependabot action bumps, [ADR-007](../decisions/007-track-third-party-actions-with-dependabot.md)); forcing every consumer to pin it sacrifices zero-config adoption.
- **Making `TF_TOKEN_APP_TERRAFORM_IO` optional** (non-HCP backends) — speculative: no consumer needs it, and loosening required → optional is non-breaking, so it can ship on any major later without a cut.
- **Merging `terraform-drift.yml` into `terraform.yml`** — they need different caller grants (`pull-requests: write` vs `issues: write`), different trigger ownership, and drift is opt-in; a merged workflow forces the union of permissions on every caller.
- **Renaming `terraform-provider-release.yml`'s `version` input (e.g. to `tag`)** — arguably clearer, but single-word, convention-compliant, and unambiguous in practice; churn without evidence of confusion.
- **Deriving the multi-directory defaults from `working-directory`** (`concurrency-group`, `plan-comment-marker`, `plan-artifact-name` auto-scoped, sparing a multi-owner repo three mirrored inputs) — changing a default is breaking, single-directory repos would trade today's clean literals for derived values, and the explicit inputs are self-documenting; revisit alongside the drift multi-owner scoping in the additive backlog when `terraform-github`'s matrix-over-owners makes the shape concrete.

## Migration path per consumer

This plan's items rename **no filenames and no job ids**, so the check contexts established at v2 ([ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md)/[ADR-012](../decisions/012-flungo-workflows-meta-workflow.md), tabulated in [`upgrading.md § v2`](../reference/upgrading.md#v2)) — including `terraform / terraform` — carry through v3 unchanged, and **required-status-check configuration needs no edits at all**.
Every migration is a caller-file edit plus the `@v2` → `@v3` pin bumps.
Consumers move deliberately, one PR each, after the cut.

The table assumes the v2 baseline (post-naming migration); caller filenames below are each repo's own.

| Consumer | Callers affected | Migration work |
| --- | --- | --- |
| `terraform-github` | `terraform.yml` caller, `flungo-workflows` caller | Move `provider_token`/`tf-var-name` into the map as `"github_token"`; rename `tf_secret_vars:` → `TF_SECRET_VARS:`; bump 2 pins. The `surface-classic-protection` follow-on job is artifact-contract only — untouched. ~6-line diff. |
| `terraform-grafana-cloud` | `terraform.yml`, `terraform-drift.yml`, `flungo-workflows` callers | Same provider-token move in both callers (`"grafana_cloud_access_policy_token"` entry); `force_run:` → `force-run:` in the drift caller (the caller's own `workflow_dispatch` input name is its own business); bump 3 pins. ~8-line diff. |
| `terraform-provider-stalwart` | provider `test`/`docs`/`release` callers, both Markdown callers, `flungo-workflows` caller | `PASSPHRASE:` → `GPG_PASSPHRASE:` in the release caller and rename the stored repo secret; bump 6 pins. ~7-line diff. |
| `stalwart.flungo.net` | Markdown callers (+ `flungo-workflows` if adopted) | Pin bumps only — no Markdown contract change in v3. |
| `claude-plugins` | Markdown callers | Pin bumps only. |
| `terraform-cloudflare` | none yet (empty repo) | Nothing to migrate — adopts the current major directly when onboarded, per the runbooks. |
| `authentik.flungo.net` | none yet (named in [ADR-001](../decisions/001-centralised-reusable-workflows.md) as a future consumer) | Nothing to migrate — adopts the current major directly. |

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

At execution time, re-enumerate consumers rather than trusting this table — search each candidate repo's `.github/workflows/` for `flungo/github-workflows/` refs — and open one migration PR per repo.
Any consumer missed here that has adopted the [version check](../runbooks/adopting-version-check.md) self-reports within a week of the cut.

## The mechanical cut checklist

Per [releasing.md § Making a breaking change you foresee](../runbooks/releasing.md#making-a-breaking-change-you-foresee-cut-the-next-major), after the v2 cut has landed and the pre-cut current-major items above have shipped:

1. **One PR, on an ordinarily-named feature branch** (never a branch matching `v[0-9]*` — creation is restricted to the release App and the rejection message won't say why), containing:
   - the five scope items' workflow/action edits;
   - `MAJOR_BRANCH: v2` → `v3` in the release workflow — the one-line edit that *is* the major decision;
   - the **`## v3` section in [`upgrading.md`](../reference/upgrading.md)** ([ADR-013](../decisions/013-per-major-upgrade-guide.md)): what breaks and the consumer moves, distilled from this plan's scope items and migration table — noting explicitly that no check context changes in this major;
   - the docs version sweep: search the repo for `v2` (broader than `@v2`) and bump every reference meant to show the current major — the README and the adoption runbooks — plus the reference docs and runbooks that name the renamed/removed inputs and secrets. Historical and migration mentions (ADRs, `upgrading.md`'s per-major sections, this plan) stay as written;
   - an ADR if review deems the naming convention worth a durable record (the removal rationale lives in ADR-008's lineage and this plan);
   - `docs/` index refreshes in the same commit, CI green (actionlint, action tests, Markdown checks).
2. **Do not pre-create `v3`** — on merge, the release workflow sees the new `MAJOR_BRANCH`, creates `v3` at `main`, and never advances `v2` again.
3. **Verify**: the Release run log shows `create v3 at <sha>`; `v2` still points at the last pre-merge commit; a consumer pinning `@v3` resolves.
4. **Migrate consumers** per the table above, one PR each.
5. **Confirm the fleet**: each opted-in consumer's version-check issue (if one opened) auto-closes as its migration lands.
6. **Retire this plan** (delete the file, update the plans index) and prune the corresponding CLAUDE.md § Deferred follow-ups entries.

## What happens to v2

- **Freeze point**: the last commit on `main` before the v3 cut PR merges. The release workflow never advances `v2` past it ([ADR-003](../decisions/003-version-via-moving-v1-branch.md)).
- **Deprecation warnings**: the `tf-var-name` warning shipped pre-cut keeps firing in every frozen-major Terraform run it reached, so a straggler sees the pointer to this migration in its own logs, not just in an issue.
- **Version check**: on each opted-in consumer's next scheduled run after `v3` exists, the version-check job opens its migration issue naming the frozen pins, and closes it once every ref is on `@v3`; per [ADR-013](../decisions/013-per-major-upgrade-guide.md) the issue leads to [`upgrading.md`](../reference/upgrading.md), where a `v1`-pinned straggler works the `v2` section and then the `v3` one, in order. Nothing is pushed onto consumers; the issue is the nudge.
- **Patches**: `v2` is thereafter a maintenance branch — fixes reach it only via PRs based on `v2` (cherry-picks or reverts), expected to be rare and reserved for breakage, per [releasing.md § Patching a frozen major](../runbooks/releasing.md#patching-a-frozen-major). (`v1` froze earlier, at the v2 cut, under the same rules.)

## Completion checklist

- [ ] Pre-cut on the current major: deprecation warning in `export.sh`
- [ ] Pre-cut on the current major: `terraform-version` wired in both provider workflows
- [ ] Pre-cut on the current major: `self-` renames + unprefixed-means-`workflow_call`-only guard
- [ ] Pre-cut on the current major: plan-comment pagination + fail-loud `operation` fixes
- [ ] The v2 cut ([ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md)/[ADR-012](../decisions/012-flungo-workflows-meta-workflow.md)) has landed and consumers have migrated to `@v2`
- [ ] The cut PR (scope items 1–5 + `MAJOR_BRANCH` + `upgrading.md` § v3 + docs sweep) merged; `v3` created by the release workflow
- [ ] `terraform-github` migrated
- [ ] `terraform-grafana-cloud` migrated
- [ ] `terraform-provider-stalwart` migrated
- [ ] Markdown-only consumers (`stalwart.flungo.net`, `claude-plugins`) bumped
- [ ] Consumer re-enumeration found no other stale-major refs (or they were migrated)
- [ ] Plan retired; CLAUDE.md deferred follow-ups pruned
