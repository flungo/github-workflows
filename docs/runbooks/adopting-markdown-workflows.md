# Adopting the Markdown workflows

How any repo with Markdown calls `markdown-lint.yml` and `markdown-links.yml`, and brings its docs and `CLAUDE.md` up to the standard. Pin `@v1`. These are **not** Terraform-specific — most `flungo` repos with a `docs/` tree should adopt them. See [`markdown-validation.md`](../reference/markdown-validation.md) for what they do and [ADR-002](../decisions/002-markdown-validation-tooling.md) for why.

> **Highly recommended:** also adopt the [version check](adopting-version-check.md) — a one-line opt-in caller that raises an issue in this repo if a future major bump ever leaves it pinning a frozen `@vN`. Especially worth it when this is the first `github-workflows` workflow the repo adopts.

## `markdown-lint.yml`

No inputs or secrets. The caller owns the triggers, path filters, and `.markdownlint-cli2.jsonc`.

```yaml
name: Markdown lint
on:
  pull_request: { paths: ['**/*.md', '.markdownlint-cli2.jsonc', '.github/workflows/markdown-lint.yml'] }
  push: { branches: [main], paths: ['**/*.md', '.markdownlint-cli2.jsonc', '.github/workflows/markdown-lint.yml'] }
jobs:
  lint:
    uses: flungo/github-workflows/.github/workflows/markdown-lint.yml@v1
```

## `markdown-links.yml`

The internal (blocking) job runs on `pull_request`/`push`; the external (issue-reporting) job runs on `schedule`/`workflow_dispatch`. The caller owns all four triggers and supplies `LYCHEE_GITHUB_TOKEN` for the external job, and keeps its own `.lycheeignore`.

```yaml
name: Markdown links
on:
  pull_request: { paths: ['**/*.md', '.github/workflows/markdown-links.yml', .lycheeignore] }
  push: { branches: [main], paths: ['**/*.md', '.github/workflows/markdown-links.yml', .lycheeignore] }
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:
jobs:
  links:
    permissions:
      contents: read
      issues: write
    uses: flungo/github-workflows/.github/workflows/markdown-links.yml@v1
    secrets:
      LYCHEE_GITHUB_TOKEN: ${{ secrets.LYCHEE_GITHUB_TOKEN }}
```

**The `permissions:` block on the calling job is required.** The external sweep upserts a `markdown-links` issue, so the reusable workflow requests `issues: write`; a reusable workflow's own `permissions:` only *caps* the token, so the caller must grant it, or the run fails at startup (`startup_failure`) when the repo's default `GITHUB_TOKEN` is read-only. (`markdown-lint.yml` needs no extra permissions — the default read access is enough.)

## Per-repo config

Both files are **repo-specific — regenerate them, don't copy another repo's**:

- **`.markdownlint-cli2.jsonc`** — the markdownlint rules. Start from the standard defaults (`MD013: false`, `MD024: { siblings_only: true }`; see [`markdown-validation.md`](../reference/markdown-validation.md#markdownlint-rule-defaults-and-their-paired-conventions)); add further overrides only with an inline justification.
- **`.lycheeignore`** — URLs that legitimately 403/404 while unauthenticated. Seed it with an explanatory header and populate it from that repo's own first `workflow_dispatch` run — never copy another repo's entries.
- **`LYCHEE_GITHUB_TOKEN`** secret — a namespaced PAT (an account/org secret is ideal). Provisioning and the `token:`-input-not-`env` gotcha are in [`markdown-validation.md § LYCHEE_GITHUB_TOKEN provisioning`](../reference/markdown-validation.md#lychee_github_token-provisioning).

## Adoption procedure — check-then-fix commit structure

The rule that matters more than the PR boundary is the **commit** boundary. For each check you introduce:

1. **Introduce the check** (workflow / config) in one commit, with **no fixes**.
2. **Push it and confirm CI shows the expected failure** — this proves the check actually catches what it should. Seeing the red is the point; never fix pre-emptively.
3. **Apply the fixes in a separate, later commit** — always distinct from, and after, the check that surfaced them; never squashed into it. A separate commit per logical fix group aids review (e.g. one per reverted markdownlint override).

Work through the checks in order, each as its own commit pair (check, then fixes):

1. **Internal links + anchors** (`markdown-links.yml` internal job) — offline, blocking. Confirm it goes red on a genuinely broken link/anchor before fixing.
2. **markdownlint** (`markdown-lint.yml` + `.markdownlint-cli2.jsonc`) — style/structure. Expect many findings on a repo adopting it for the first time.
3. **Semantic-line-break reflow** (see below) — a best-effort pass, gated on render-equivalence.
4. **External URLs** (`markdown-links.yml` external job + `.lycheeignore`) — verify **in GitHub via `workflow_dispatch`**, not from a sandbox with limited egress. Confirm: external URLs are checked; a broken link **creates one issue**; a second dispatch **updates the same issue** (no duplicate); a clean run **closes** it. Add genuine 403/404-when-unauthenticated offenders to `.lycheeignore` and re-dispatch until green.

When adopting, this may be a **single PR**, provided it still contains those same distinct commits.

## Semantic-line-break reflow

Applying the semantic line breaks convention (one sentence per source line) to a repo's *existing* docs is a pure source-whitespace change — identical rendered output. Do it with the render-gated script [`reflow.py`](../../scripts/reflow.py) (`pip install markdown-it-py`), never a blind unwrap:

- It reflows only **top-level prose paragraphs** to one sentence per line.
- It **preserves hard-break blocks** (e.g. `**Date:**` / `**Status:**` metadata whose trailing-space `<br>` carries meaning) and **leaves list and blockquote inner paragraphs hard-wrapped** for a later pass (their prefixes need care) — best effort.
- It **gates every file on render-equivalence:** it parses with a CommonMark library and requires the normalised rendered HTML to be **byte-identical** before and after; any file that would change rendering is left untouched. That makes it a pure whitespace change with zero rendered-output risk.

Sentence splitting is heuristic (break on a sentence-ending `.`/`?`/`!` + space, outside inline code, minus a small abbreviation list such as `e.g.`/`i.e.`/`etc.`). Imperfect breaks are style-only — the render gate guarantees correctness — and are tidied in later edits.

## Claude conventions — adopt the `markdown-standards` plugin

Part of adopting is teaching future agents how to keep links correct and how to fix the failures these checks raise.
Those conventions ship as the [`markdown-standards` plugin](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) in the `flungo-plugins` marketplace, so they are **adopted, not copied**: the cross-reference/link-hygiene rules (formerly inlined here as a generic `## Cross-references` block), the prose conventions paired with the markdownlint defaults (semantic line breaks / `MD013`, unique cross-referenced headings / `MD024`, adjacent blockquotes / `MD028`), and the fix-the-link-or-its-target-never-suppress remediation guidance.
The extraction is recorded in [claude-plugins ADR 004](https://github.com/flungo/claude-plugins/blob/main/docs/decisions/004-markdown-standards-plugin.md).

Instead of pasting blocks into the repo's `CLAUDE.md`, enable the plugin at project scope in the repo's `.claude/settings.json`:

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

- **Repo-specific facts stay in `CLAUDE.md`** — e.g. the pinned local markdownlint-cli2 version (see § Adoption pitfalls and sandbox constraints) and any justified per-repo lint overrides.
- **A repo that inlined the old blocks** (a `## Cross-references` section or the paired-convention sections from an earlier adoption) removes them in favour of the plugin when next touched — one source of truth.

## Adoption pitfalls and sandbox constraints

Recorded from real adoptions, several from Claude Code Web sessions. Reading these first means going straight to implementing the plan instead of re-discovering them.

**Match the CI tool versions locally, or you chase findings CI never reports.**

- `DavidAnson/markdownlint-cli2-action@v19` pins a specific `markdownlint-cli2` (e.g. 0.17.2 / markdownlint 0.37.4). A newer `markdownlint-cli2` installed locally carries rules the pinned CI version does **not** have — e.g. `MD060` (table-column-style), which fires on every table and produces dozens of findings CI will never raise. Pin the local tool to the CI version: `npm install markdownlint-cli2@<pinned>`.
- Find the action's pinned version by reading its manifest at the tag: `https://raw.githubusercontent.com/DavidAnson/markdownlint-cli2-action/<tag>/package.json` (readable via `WebFetch` even for repos outside the session scope).
- `markdownlint-cli2` only accepts a config file **named** `.markdownlint-cli2.jsonc` (or a `*.markdownlint-cli2.jsonc` prefix); `--config /tmp/arbitrary.json` is rejected. Name any throwaway config accordingly (e.g. `check.markdownlint-cli2.jsonc`).
- Record the pinned version in the adopting repo's `CLAUDE.md`, so the next agent matches CI on the first run.

**lychee: install via cargo, not the GitHub release, in a locked-down sandbox.**

- lychee has no npm/pip package, and its GitHub release tarballs are blocked by a locked-down egress proxy, so the "download the binary" path fails. `cargo install lychee --locked` works (the crates index is reachable) but **compiles for a few minutes** — kick it off in the background at the start of the session.
- The workflow uses `lycheeverse/lychee-action@v2`, which bundles its own lychee, so exact local parity matters less than for markdownlint. The local binary's value is proving the offline check (and anchor-slug parity) **before** pushing: run `lychee --offline --include-fragments --no-progress '**/*.md'` and confirm it flags a deliberately broken `#anchor` and a missing file.

**Claude Code Web egress constraints.**

- Package registries (npm, PyPI, the crates index) are allow-listed, so `npm` / `pip` / `cargo` work — but point each tool at the proxy CA bundle or TLS verification fails: `NODE_EXTRA_CA_CERTS`, `PIP_CERT`, and `CARGO_HTTP_CAINFO` all set to `/root/.ccr/ca-bundle.crt`.
- `github.com` release/download URLs for repos outside the session's scope are blocked (the proxy returns an "access not enabled" body instead of the file) — read public files via `raw.githubusercontent.com` through `WebFetch` instead.
- `api.github.com` returns 403 through the proxy; use the GitHub MCP tools for PRs, issues, runs, and dispatch.
- The harness blocks `sleep`; wait on a backgrounded command or a Monitor loop.

**Verify the external sweep pre-merge via `workflow_dispatch` — but provision the token first.**

- `workflow_dispatch` can be triggered against the **feature branch** before the workflow is on the default branch — GitHub accepts a dispatch with an explicit `ref` (GitHub MCP `actions_run_trigger`, `method: run_workflow`, `workflow_id: markdown-links.yml`, `ref: <branch>`). This exercises the external job and the auto-issue **create** path straight from the PR. (A `workflow_dispatch`-only workflow that has never run is not indexed and 404s on dispatch; the markdown-links caller's `pull_request` trigger indexes it, so this works.)
- **Pitfall — a tokenless dispatch floods the issue with false 404s.** Dispatch before `LYCHEE_GITHUB_TOKEN` exists and the action falls back to the repo-scoped `github.token`, which **cannot read other private repos** — so every cross-repo link into a private repo returns `404` and lands in the auto-issue. Those are token artifacts, **not** dead links: do **not** copy them into `.lycheeignore`. Provision the token, re-dispatch, and only then curate `.lycheeignore` from what genuinely remains (typically a few real bot-blocked 403s). This is the concrete reason `.lycheeignore` must be regenerated per repo from a **token-enabled** run.

## Starting an adoption session

With the [`markdown-standards` plugin](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) installed (user scope), onboarding is a command: start a session with the target repo and invoke **`/adopt-markdown-ci`** — it carries the checklist (callers, per-repo config, token, check-then-fix order, reflow, plugin adoption) and defers to this runbook as the source of truth.

Without the plugin, the equivalent starter prompt is:

```text
Task: add Markdown-validation CI to <owner/target-repo> by adopting the reusable
workflows from flungo/github-workflows, following
docs/runbooks/adopting-markdown-workflows.md in that repo.

- Add the two caller workflows pinned @v1 (markdown-lint.yml, markdown-links.yml).
- Add a repo-specific .markdownlint-cli2.jsonc (standard defaults) and a seeded
  .lycheeignore (regenerate from this repo's own findings — never copy another
  repo's entries).
- Provision LYCHEE_GITHUB_TOKEN and pass it via the lychee-action token: input,
  not a step-level env: GITHUB_TOKEN (the reference explains why).
- Work through the checks in the check-then-fix commit order; run the render-gated
  reflow (scripts/reflow.py) as a best-effort pass.
- Enable the markdown-standards plugin from the flungo/claude-plugins marketplace
  at project scope in .claude/settings.json (instead of pasting conventions into
  CLAUDE.md), and remove any previously inlined copies of its conventions.

Work on a feature branch, never commit to main, and open a PR. If <owner/target-repo>
has its own CLAUDE.md/CONTRIBUTING guidance, follow it where it differs.
```
