# Adopting the Markdown workflows

How any repo with Markdown calls `markdown-lint.yml`, `markdown-links.yml` and (optionally) `markdown-sembr.yml`, and gets its docs passing them.
Pin `@v2`.
These are **not** Terraform-specific — most `flungo` repos with a `docs/` tree should adopt the first two, which impose no house style.
`markdown-sembr.yml` is the exception to that "most repos should": it enforces a prose convention — one sentence per source line — so take it only in a repo that writes that way, or is willing to reflow to it.
See [`markdown-validation.md`](../reference/markdown-validation.md) for what they do, [ADR-002](../decisions/002-markdown-validation-tooling.md) and [ADR-015](../decisions/015-semantic-line-break-check.md) for why.

> **Highly recommended:** also adopt [`flungo-workflows`](adopting-flungo-workflows.md) — a one-line opt-in caller that raises an issue in this repo if a future major bump ever leaves it pinning a frozen `@vN`.
> Especially worth it when this is the first `github-workflows` workflow the repo adopts.

## `markdown-lint.yml`

No inputs or secrets.
The caller owns the triggers, path filters, and `.markdownlint-cli2.jsonc`.

```yaml
name: Markdown lint
on:
  pull_request:
  push: { branches: [main] }
jobs:
  markdown-lint:
    uses: flungo/github-workflows/.github/workflows/markdown-lint.yml@v2
```

## `markdown-links.yml`

The internal (blocking) job runs on `pull_request`/`push`; the external (issue-reporting) job runs on `schedule`/`workflow_dispatch`.
The caller owns all four triggers and supplies `LYCHEE_GITHUB_TOKEN` for the external job, and keeps its own `.lycheeignore`.

```yaml
name: Markdown links
on:
  pull_request:
  push: { branches: [main] }
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:
jobs:
  markdown-links:
    permissions:
      contents: read
      issues: write
    uses: flungo/github-workflows/.github/workflows/markdown-links.yml@v2
    secrets:
      LYCHEE_GITHUB_TOKEN: ${{ secrets.LYCHEE_GITHUB_TOKEN }}
```

**The `permissions:` block on the calling job is required.**
The external sweep upserts a `markdown-links` issue, so the reusable workflow requests `issues: write`; a reusable workflow's own `permissions:` only *caps* the token, so the caller must grant it, or the run fails at startup (`startup_failure`) when the repo's default `GITHUB_TOKEN` is read-only.
(`markdown-lint.yml` needs no extra permissions — the default read access is enough.)

## `markdown-sembr.yml`

Optional, and only for a repo on semantic line breaks.
It flags two sentences sharing a source line — the one MUST rule of [sembr](https://sembr.org/) — and nothing else.
No secrets or permissions; every input has a working default.

```yaml
name: Markdown semantic line breaks
on:
  pull_request:
  push: { branches: [main] }
jobs:
  markdown-sembr:
    uses: flungo/github-workflows/.github/workflows/markdown-sembr.yml@v2
```

**`.markdownlint-cli2.jsonc`'s `ignores` apply here too, without being restated.**
The check reads them from the repo's config and skips the same trees, so pre-canned data — fixtures, sample inputs, recorded responses, whatever the repo calls the directory — is excluded once rather than in each config, where the two copies drift apart silently ([ADR-016](../decisions/016-sembr-inherits-markdownlint-ignores.md)).
Set `inherit-markdownlint-ignores: false` to scan what the linter skips.
A `.markdownlint-cli2.cjs`/`.mjs` config cannot be read from the checker, and it says so in the log rather than passing over it.

Pass `globs` (default `**/*.md`, and unlike most Markdown tooling it does reach into dot directories) and `ignore` for anything the linter config does not already cover:

```yaml
    with:
      ignore: |
        vendor
        docs/generated
```

### Adopt it only alongside the reflow

The check is a gate, not a migration, so it arrives with the reflow that satisfies it rather than apart from it.
Pointing it at prose that has never been reflowed produces a finding per sentence pair — a few hundred in a typical `docs/` tree — which the reflow then clears, as that check's fix commit.
Use [`reflow.py`](https://github.com/flungo/claude-plugins/blob/main/plugins/markdown-standards/scripts/reflow.py) from the `markdown-standards` plugin: it is render-gated, so it only rewrites what renders identically.
Turning `MD013` off in the same change keeps the two rules from pulling in opposite directions.

**Fix by hand whatever the check still reports after the reflow.**
`reflow.py` is deliberately conservative — it keeps only what renders identically — so the check, not the script, is what says a repo is done.
Expect little, and expect no particular shape.

Residue specific enough to describe is a defect rather than a fact of adoption, and belongs fixed at its source: in `reflow.py` where the script is blind to something, or in the prose where a better structure would avoid the question.
This section used to name a shape and give a count for it, and both went stale the moment [claude-plugins#50](https://github.com/flungo/claude-plugins/pull/50) taught the script to see a sentence that ends inside markup.
Naming the next one would date this page the same way.

For what the check deliberately does *not* flag, and the `<!-- sembr-* -->` comments that suppress a finding it gets wrong, see [`markdown-validation.md § Semantic line breaks`](../reference/markdown-validation.md#semantic-line-breaks-markdown-sembryml).

## `paths:` filters — optional, and incompatible with required checks

A caller may narrow any of the three workflows above to the paths that matter, and it is a reasonable thing to want: most pull requests touch no Markdown, and the checks would otherwise run for nothing.

```yaml
on:
  pull_request: { paths: ['**/*.md', '.markdownlint-cli2.jsonc'] }
```

**It rules out ever requiring the context, though**, so decide that first.

A workflow skipped by path filtering never creates its check run at all.
GitHub then holds a required context at *Expected* indefinitely — not failed, just never arriving, with nothing able to clear it — so any pull request touching none of the filtered paths is unmergeable.
In a Terraform repo the common case is exactly that: a `.tf`-only change matches no Markdown path.

The distinction that makes this confusing is *workflow* versus *job*.
A job that skips itself on an `if:` **does** report a check run, which is why `markdown-links`' external sweep can self-skip on `pull_request` safely — its workflow still ran.
Only a workflow that never triggers leaves nothing behind.

So the filter is available where a check is advisory, and off the table where it gates merges.
All three take seconds, so running them on everything costs little and keeps the option of requiring them open.

> **The `flungo` fleet does not use them.**
> `terraform-github`'s `markdown` flag makes all three contexts required — and strict, so a branch must also be up to date — which is incompatible with path filtering.
> The snippets above are therefore unfiltered, and a repository managed there should keep them that way.
> See [§ Adopting in a repository managed by `terraform-github`](#adopting-in-a-repository-managed-by-terraform-github).

## Per-repo config

Both files are **repo-specific — regenerate them, don't copy another repo's**:

- **`.markdownlint-cli2.jsonc`** — the markdownlint rules, which are the **adopting repo's choice**; the workflow imposes none.
  A few rules interact with how a repo writes prose and are worth deciding deliberately rather than inheriting — see [`markdown-validation.md § Fabrizio's markdownlint rule choices`](../reference/markdown-validation.md#fabrizios-markdownlint-rule-choices) for the calls he has made and the reasoning behind each.
  Give each override an inline justification.
- **`.lycheeignore`** — URLs that legitimately 403/404 while unauthenticated.
  Seed it with an explanatory header and populate it from that repo's own first `workflow_dispatch` run — never copy another repo's entries.
- **`LYCHEE_GITHUB_TOKEN`** secret — a namespaced PAT (an account/org secret is ideal).
  Provisioning and the `token:`-input-not-`env` gotcha are in [`markdown-validation.md § LYCHEE_GITHUB_TOKEN provisioning`](../reference/markdown-validation.md#lychee_github_token-provisioning).

## Adoption procedure

> **Prefer an automated adoption?**
> Fabrizio's [`markdown-standards` plugin](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) drives everything in this section as a single **`/adopt-markdown-ci`** command, bundled with his Markdown conventions — see [§ Optional — automated adoption with Fabrizio's conventions](#optional--automated-adoption-with-fabrizios-conventions) below.
> The procedure here stands on its own if you would rather not take those opinions.

Introduce the checks **one at a time**, and let each one report before you fix anything it covers — findings you pre-empted are findings you never saw.
A first run that comes back green is a fine outcome, and nothing needs manufacturing to produce one that isn't: a repo that already follows a rule has nothing to fix, and these workflows are pinned and shared, so their behaviour is verified once in this repository rather than re-proven in each adopter (see [§ Verifying the external sweep](#verifying-the-external-sweep) for the same argument made where it is least obvious).
Expect a first-time markdownlint run to produce many findings.

How that work is then split into commits or PRs is the adopting repo's business; the plugin encodes one opinionated discipline for it.

Add the checks in this order:

1. **Internal links + anchors** (`markdown-links.yml` internal job) — offline and blocking, so it must be green to merge.
2. **markdownlint** (`markdown-lint.yml` + `.markdownlint-cli2.jsonc`) — style and structure only; it does not check cross-file links.
3. **External URLs** (`markdown-links.yml` external job + `.lycheeignore`) — dispatch it **in GitHub via `workflow_dispatch`**, not from a sandbox with limited egress, and only once `LYCHEE_GITHUB_TOKEN` exists (see the pitfalls below).
   Confirm the run reaches the external job and reports on this repo's own URLs, then add genuine 403/404-when-unauthenticated offenders to `.lycheeignore` and re-dispatch until green.
   One clean run is all this step needs.
4. **Semantic line breaks** (`markdown-sembr.yml`), only if the repo is taking the convention — the caller first, then the reflow as its fix commit, the same way round as the others.
   A repo that has never been reflowed will show a finding per sentence pair on that first run, and the reflow commit resolves them.
   Verify the reflow itself by rendering, not by the check: the check is blind to a break that changed the output, which is exactly what `reflow.py`'s render gate is for.

### Verifying the external sweep

Breaking a link on purpose to watch the sweep open an issue is **not** part of adopting the workflows in a new repo.
The create/update/close lifecycle — one issue opened, updated in place on the next dispatch rather than duplicated, and closed once a later run comes back clean — is behaviour of the pinned reusable workflow, identical in every caller, so it is verified once per major version rather than in each adopting repo.
It was verified for `@v1` in [flungo/claude-plugins#12](https://github.com/flungo/claude-plugins/pull/12).
`v2` renamed the job (`external`, so the context is now `markdown-links / external`) and changed nothing about the lifecycle itself, so that verification carries over.

Nor does a clean run hide a missing `issues: write` grant.
Because the reusable workflow requests that permission, a caller that does not grant it fails at startup — see [§ `markdown-links.yml`](#markdown-linksyml) above — so a dispatch that runs at all has already proved the grant is adequate.
What is genuinely per-repo is the URL set and the token, and one clean dispatch exercises both.

## Adopting in a repository managed by `terraform-github`

Every `flungo`-owned repository is managed as code in [`terraform-github`](https://github.com/flungo/terraform-github), and its `standard-repository` module has a `markdown` flag meaning **"this repository follows Fabrizio's Markdown standards"** — that is, it calls `markdown-lint.yml`, `markdown-links.yml` and `markdown-sembr.yml` under the conventional names.
The flag provisions the secret the external sweep reads and requires the checks those three report — so what you name your calling jobs is not a local style choice there, it is a cross-repository contract.

**Name the calling jobs after the workflows they call, or the flag does not fit.**

A check's context is `<caller job id> / <reusable job id>`, and `terraform-github` hardcodes three strings:

| Caller | Context it must report |
| --- | --- |
| `markdown-lint.yml`, job `markdown-lint` | `markdown-lint / lint` |
| `markdown-links.yml`, job `markdown-links` | `markdown-links / internal` |
| `markdown-sembr.yml`, job `markdown-sembr` | `markdown-sembr / sembr` |

Both halves follow published conventions rather than being arbitrary: the caller half is the workflow's filename ([ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md)) and the reusable half is the job's ID ([ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md)), so a caller copied from the snippets at the top of this page already fits.

> A consumer still pinned to `@v1` reports the pre-`v2` names — `markdown-lint / markdownlint` and `markdown-links / Internal links & anchors` — and cannot satisfy the flag until it migrates.
> `v1` is frozen, so migrating is the only way forward: see [`upgrading.md` § v2](../reference/upgrading.md#v2).
> Every repository in the fleet has already made that move, so this applies only to a consumer outside it.

The external sweep's `markdown-links / external` is **not** required and must not be added: it self-skips on `pull_request`, which is the whole point of reporting through an issue instead.

**The flag defaults to `true`**, so an established repository needs no edit in `terraform-github` at all — adopting the workflows is enough, and the flag is already asserting that you have.
What it does is attach `LYCHEE_GITHUB_TOKEN` and add the three contexts above to the repository's required status checks.

The exception is a repository being **created**: it has no callers yet, so `terraform-github`'s creation runbook sets `markdown = false` on the create.
The callers belong to the repository's first pull request — the docs scaffolding and CI that land before any other content — and the `terraform-github` follow-up that removes the create's `repository_exists = false` removes `markdown = false` with it, once that first pull request is on the default branch.

### Either order works, and workflows-first is usually kinder

Unlike the [Terraform flag](adopting-terraform-workflows.md#order-the-two-changes-flag-first), which has to land first because its workflow cannot run at all without the secret, neither *blocking* Markdown check reads a secret.
Only the scheduled external sweep needs `LYCHEE_GITHUB_TOKEN`.

So the callers can land here first and the flag follow, which leaves any pull requests already open against the repository unblocked in the meantime.
Flag-first also works — a `pull_request` run uses the workflow file from **the pull request's own head**, so the pull request that adds the callers reports the contexts and satisfies its own requirement — but it queues every other open pull request behind it until they rebase.

One caveat on landing the callers first: verify the external sweep by `workflow_dispatch` only **after** `LYCHEE_GITHUB_TOKEN` exists, whether it was provisioned by the flag or by hand.
A tokenless dispatch floods the auto-issue with cross-repo 404s that are token artifacts rather than dead links — see § Adoption pitfalls below.

### The checks are strict: merging needs an up-to-date branch

For most repositories adopting these workflows, these will be their **first** required checks — which means the flag also brings the up-to-date-branch requirement ([`terraform-github` ADR-011](https://github.com/flungo/terraform-github/blob/main/docs/decisions/011-strict-required-status-checks.md) — not to be confused with this repository's own ADR-011 above) into force for the first time.
It is encoded in the branch-protection module rather than exposed, so it arrives with the required checks and cannot be declined separately.

In practice: every merge to the default branch leaves the other open pull requests out of date, and each must be brought forward and re-run before it can merge in turn.
GitHub's **Update branch** button appears once this is in force; its **Update with rebase** option is the linear-history-preserving one, and the one to use here.

## Optional — automated adoption with Fabrizio's conventions

Everything above is the workflows' contract, and a repo can stop there: it is fully adoptable by hand, without taking on anyone's house style.

Layered on top, the [`markdown-standards` plugin](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) in the `flungo-plugins` marketplace turns this runbook into a **standalone, automated adoption path**, bundled with Fabrizio's Markdown conventions.
**Take it only if you want those opinions.**

### Running it — `/adopt-markdown-ci`

Install the plugin, start a Claude Code session on the target repo, and invoke **`/adopt-markdown-ci`**.
It carries out the adoption end to end:

- the caller workflows pinned to the current major, with the `permissions:` block `markdown-links.yml` needs, plus the recommended version check;
- a repo-specific `.markdownlint-cli2.jsonc` and a seeded `.lycheeignore`, regenerated for that repo rather than copied from another;
- `LYCHEE_GITHUB_TOKEN` provisioned **before** `.lycheeignore` is curated, so token artifacts never reach it;
- each check introduced and confirmed red before its findings are fixed, in the order above, with the external sweep verified by `workflow_dispatch`;
- the semantic-line-break reflow;
- the plugin enabled at project scope, so the conventions travel with the repo rather than being pasted into its `CLAUDE.md`;
- all of it on a feature branch, landed via PR.

It follows this runbook for the mechanics — this page stays the source of truth for the contract, including the pitfalls below — and its own references for everything that is opinion.

### What the conventions add

- cross-reference and link-hygiene rules, and how to fix a failure from any of these checks without suppressing it;
- the prose conventions paired with particular markdownlint rules — semantic line breaks (`MD013`), unique cross-referenced headings (`MD024`), adjacent blockquotes (`MD028`) — and the rule settings that go with them;
- [`reflow.py`](https://github.com/flungo/claude-plugins/blob/main/plugins/markdown-standards/scripts/reflow.py), a render-gated one-time pass that migrates a repo's existing prose to semantic line breaks;
- the check-then-fix commit discipline the command applies when introducing each check.

### Enabling the plugin

Enable it at project scope in the repo's `.claude/settings.json` — never by pasting its text into a `CLAUDE.md`:

```json
{
  "extraKnownMarketplaces": {
    "flungo-plugins": {
      "source": { "source": "github", "repo": "flungo/claude-plugins" }
    }
  },
  "enabledPlugins": {
    "markdown-standards@flungo-plugins": true
  }
}
```

Repo-specific facts still belong in the repo's own `CLAUDE.md` — e.g. which trees the repo excludes from the checks, and the justification for any per-repo lint override.
A repo that inlined these conventions during an earlier adoption removes the copies in favour of the plugin when next touched.
The extraction is recorded in [claude-plugins ADR 004](https://github.com/flungo/claude-plugins/blob/main/docs/decisions/004-markdown-standards-plugin.md).

## Adoption pitfalls and sandbox constraints

Recorded from real adoptions, several from Claude Code Web sessions.
Reading these first means going straight to implementing the plan instead of re-discovering them.

**Match the CI tool versions locally, or you chase findings CI never reports.**

- `markdown-lint.yml` tracks `DavidAnson/markdownlint-cli2-action` by major tag, so the `markdownlint-cli2` version underneath it moves on its own — a Dependabot bump to the action changes it with no commit in any consumer to mark the change.
  A local copy newer than CI's carries rules CI does not have — `MD060` (table-column-style) arrived that way and fires on every table — and an older one passes clean against rules CI does enforce.
- Read the version off the first line of the `markdown-lint` job's log in a recent run of the repo, and match it: `npm install markdownlint-cli2@<that version>`.
  A version written down anywhere is a snapshot of when it was written, so treat one you find as a datestamped observation rather than a pin — the [`markdown-standards`](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) plugin's § Running the Markdown checks locally is the standing procedure.
- `markdownlint-cli2` only accepts a config file **named** `.markdownlint-cli2.jsonc` (or a `*.markdownlint-cli2.jsonc` prefix); `--config /tmp/arbitrary.json` is rejected.
  Name any throwaway config accordingly (e.g. `check.markdownlint-cli2.jsonc`).

**lychee: install via cargo, not the GitHub release, in a locked-down sandbox.**

- lychee has no npm/pip package, and its GitHub release tarballs are blocked by a locked-down egress proxy, so the "download the binary" path fails.
  `cargo install lychee --locked` works (the crates index is reachable) but **compiles for a few minutes** — kick it off in the background at the start of the session.
- The workflow uses `lycheeverse/lychee-action@v2`, which bundles its own lychee, so exact local parity matters less than for markdownlint.
  The local binary's value is proving the offline check (and anchor-slug parity) **before** pushing: run `lychee --offline --include-fragments --no-progress '**/*.md'` and confirm it flags a deliberately broken `#anchor` and a missing file.

**Claude Code Web egress constraints.**

- Package registries (npm, PyPI, the crates index) are allow-listed, so `npm` / `pip` / `cargo` work — but point each tool at the proxy CA bundle or TLS verification fails: `NODE_EXTRA_CA_CERTS`, `PIP_CERT`, and `CARGO_HTTP_CAINFO` all set to `/root/.ccr/ca-bundle.crt`.
- `github.com` release/download URLs for repos outside the session's scope are blocked (the proxy returns an "access not enabled" body instead of the file) — read public files via `raw.githubusercontent.com` through `WebFetch` instead.
- `api.github.com` returns 403 through the proxy; use the GitHub MCP tools for PRs, issues, runs, and dispatch.
- The harness blocks `sleep`; wait on a backgrounded command or a Monitor loop.

**Verify the external sweep pre-merge via `workflow_dispatch` — but provision the token first.**

- `workflow_dispatch` can be triggered against the **feature branch** before the workflow is on the default branch — GitHub accepts a dispatch with an explicit `ref` (GitHub MCP `actions_run_trigger`, `method: run_workflow`, `workflow_id: markdown-links.yml`, `ref: <branch>`).
  This exercises the external job and the auto-issue **create** path straight from the PR.
  (A `workflow_dispatch`-only workflow that has never run is not indexed and 404s on dispatch; the markdown-links caller's `pull_request` trigger indexes it, so this works.)
- **Pitfall — a tokenless dispatch floods the issue with false 404s.** Dispatch before `LYCHEE_GITHUB_TOKEN` exists and the action falls back to the repo-scoped `github.token`, which **cannot read other private repos** — so every cross-repo link into a private repo returns `404` and lands in the auto-issue.
  Those are token artifacts, **not** dead links: do **not** copy them into `.lycheeignore`.
  Provision the token, re-dispatch, and only then curate `.lycheeignore` from what genuinely remains (typically a few real bot-blocked 403s).
  This is the concrete reason `.lycheeignore` must be regenerated per repo from a **token-enabled** run.
