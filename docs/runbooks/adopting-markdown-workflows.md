# Adopting the Markdown workflows

How any repo with Markdown calls `markdown-lint.yml` and `markdown-links.yml`, and gets its docs passing them.
Pin `@v2`.
These are **not** Terraform-specific — most `flungo` repos with a `docs/` tree should adopt them.
See [`markdown-validation.md`](../reference/markdown-validation.md) for what they do and [ADR-002](../decisions/002-markdown-validation-tooling.md) for why.

> **Highly recommended:** also adopt [`flungo-workflows`](adopting-flungo-workflows.md) — a one-line opt-in caller that raises an issue in this repo if a future major bump ever leaves it pinning a frozen `@vN`.
> Especially worth it when this is the first `github-workflows` workflow the repo adopts.

## `markdown-lint.yml`

No inputs or secrets.
The caller owns the triggers, path filters, and `.markdownlint-cli2.jsonc`.

```yaml
name: Markdown lint
on:
  pull_request: { paths: ['**/*.md', '.markdownlint-cli2.jsonc', '.github/workflows/markdown-lint.yml'] }
  push: { branches: [main], paths: ['**/*.md', '.markdownlint-cli2.jsonc', '.github/workflows/markdown-lint.yml'] }
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
  pull_request: { paths: ['**/*.md', '.github/workflows/markdown-links.yml', .lycheeignore] }
  push: { branches: [main], paths: ['**/*.md', '.github/workflows/markdown-links.yml', .lycheeignore] }
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

## Per-repo config

Both files are **repo-specific — regenerate them, don't copy another repo's**:

- **`.markdownlint-cli2.jsonc`** — the markdownlint rules, which are the **adopting repo's choice**; the workflow imposes none.
  A few rules interact with how a repo writes prose and are worth deciding deliberately rather than inheriting — see [`markdown-validation.md`](../reference/markdown-validation.md#markdownlint-rules-that-need-a-deliberate-choice).
  Give each override an inline justification.
- **`.lycheeignore`** — URLs that legitimately 403/404 while unauthenticated.
  Seed it with an explanatory header and populate it from that repo's own first `workflow_dispatch` run — never copy another repo's entries.
- **`LYCHEE_GITHUB_TOKEN`** secret — a namespaced PAT (an account/org secret is ideal).
  Provisioning and the `token:`-input-not-`env` gotcha are in [`markdown-validation.md § LYCHEE_GITHUB_TOKEN provisioning`](../reference/markdown-validation.md#lychee_github_token-provisioning).

## Adoption procedure

> **Prefer an automated adoption?**
> Fabrizio's [`markdown-standards` plugin](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) drives everything in this section as a single **`/adopt-markdown-ci`** command, bundled with his Markdown conventions — see [§ Optional — automated adoption with Fabrizio's conventions](#optional--automated-adoption-with-fabrizios-conventions) below.
> The procedure here stands on its own if you would rather not take those opinions.

Introduce the checks **one at a time**, and for each of the two blocking checks confirm it goes red before fixing what it finds — a check you have never seen fail is a check you have not verified.
The external sweep is the exception, for the reason in [§ The external sweep does not need a manufactured failure](#the-external-sweep-does-not-need-a-manufactured-failure) below.
Expect a first-time markdownlint run to produce many findings.

How that work is then split into commits or PRs is the adopting repo's business; the plugin encodes one opinionated discipline for it.

Verify each check as you add it:

1. **Internal links + anchors** (`markdown-links.yml` internal job) — offline and blocking, so it must be green to merge.
   Confirm it goes red on both a genuinely broken relative link and a bad `#anchor`.
2. **markdownlint** (`markdown-lint.yml` + `.markdownlint-cli2.jsonc`) — style and structure only; it does not check cross-file links.
3. **External URLs** (`markdown-links.yml` external job + `.lycheeignore`) — dispatch it **in GitHub via `workflow_dispatch`**, not from a sandbox with limited egress, and only once `LYCHEE_GITHUB_TOKEN` exists (see the pitfalls below).
   Confirm the run reaches the external job and reports on this repo's own URLs, then add genuine 403/404-when-unauthenticated offenders to `.lycheeignore` and re-dispatch until green.
   One clean run is all this step needs.

### The external sweep does not need a manufactured failure

Breaking a link on purpose to watch the sweep open an issue is **not** part of adopting the workflows in a new repo.
The create/update/close lifecycle — one issue opened, updated in place on the next dispatch rather than duplicated, and closed once a later run comes back clean — is behaviour of the pinned reusable workflow, identical in every caller, so it is verified once per major version rather than in each adopting repo.
It was verified for `@v1` in [flungo/claude-plugins#12](https://github.com/flungo/claude-plugins/pull/12).
`v2` renamed the job (`external`, so the context is now `markdown-links / external`) and changed nothing about the lifecycle itself, so that verification carries over.

Nor does a clean run hide a missing `issues: write` grant.
Because the reusable workflow requests that permission, a caller that does not grant it fails at startup — see [§ `markdown-links.yml`](#markdown-linksyml) above — so a dispatch that runs at all has already proved the grant is adequate.
What is genuinely per-repo is the URL set and the token, and one clean dispatch exercises both.

## Optional — automated adoption with Fabrizio's conventions

Everything above is the workflows' contract, and a repo can stop there: it is fully adoptable by hand, without taking on anyone's house style.

Layered on top, the [`markdown-standards` plugin](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) in the `flungo-plugins` marketplace turns this runbook into a **standalone, automated adoption path**, bundled with Fabrizio's Markdown conventions.
**Take it only if you want those opinions.**

### Running it — `/adopt-markdown-ci`

Install the plugin, start a Claude Code session on the target repo, and invoke **`/adopt-markdown-ci`**.
It carries out the adoption end to end:

- both caller workflows pinned to the current major, with the `permissions:` block `markdown-links.yml` needs, plus the recommended version check;
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

Repo-specific facts still belong in the repo's own `CLAUDE.md` — e.g. the pinned local markdownlint-cli2 version (see § Adoption pitfalls and sandbox constraints) and the justification for any per-repo lint override.
A repo that inlined these conventions during an earlier adoption removes the copies in favour of the plugin when next touched.
The extraction is recorded in [claude-plugins ADR 004](https://github.com/flungo/claude-plugins/blob/main/docs/decisions/004-markdown-standards-plugin.md).

## Adoption pitfalls and sandbox constraints

Recorded from real adoptions, several from Claude Code Web sessions.
Reading these first means going straight to implementing the plan instead of re-discovering them.

**Match the CI tool versions locally, or you chase findings CI never reports.**

- `DavidAnson/markdownlint-cli2-action@v29` pins a specific `markdownlint-cli2` (e.g. 0.17.2 / markdownlint 0.37.4).
  A newer `markdownlint-cli2` installed locally carries rules the pinned CI version does **not** have — e.g. `MD060` (table-column-style), which fires on every table and produces dozens of findings CI will never raise.
  Pin the local tool to the CI version: `npm install markdownlint-cli2@<pinned>`.
- Find the action's pinned version by reading its manifest at the tag: `https://raw.githubusercontent.com/DavidAnson/markdownlint-cli2-action/<tag>/package.json` (readable via `WebFetch` even for repos outside the session scope).
- `markdownlint-cli2` only accepts a config file **named** `.markdownlint-cli2.jsonc` (or a `*.markdownlint-cli2.jsonc` prefix); `--config /tmp/arbitrary.json` is rejected.
  Name any throwaway config accordingly (e.g. `check.markdownlint-cli2.jsonc`).
- Record the pinned version in the adopting repo's `CLAUDE.md`, so the next agent matches CI on the first run.

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
