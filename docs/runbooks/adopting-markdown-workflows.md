# Adopting the Markdown workflows

How any repo with Markdown calls `markdown-lint.yml` and `markdown-links.yml`, and brings its docs and `CLAUDE.md` up to the standard. Pin `@v1`. These are **not** Terraform-specific — most `flungo` repos with a `docs/` tree should adopt them. See [`markdown-validation.md`](../reference/markdown-validation.md) for what they do and [ADR-002](../decisions/002-markdown-validation-tooling.md) for why.

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

## `CLAUDE.md` additions

Part of adopting is teaching future agents how to keep links correct and how to fix the failures these checks raise. Add the following `## Cross-references` section to the repo's `CLAUDE.md` — it is deliberately generic; replace the `<Project>` / `<owner>` / `<repo>` placeholders per repo. Also record the two prose conventions paired with the markdownlint rules — semantic line breaks (`MD013`) and adjacent-blockquote handling (`MD028`) — as their own short `CLAUDE.md` sections (see [`markdown-validation.md`](../reference/markdown-validation.md#markdownlint-rule-defaults-and-their-paired-conventions)).

````markdown
## Cross-references

Keep links and references accurate and unambiguous. These rules apply to **any**
cross-reference — between docs, to an ADR, to source code, or to another repo.

The Markdown validation CI enforces the **mechanical** half: the link/anchor
check fails a PR when a relative link doesn't resolve to a file or an anchor
doesn't match a heading; markdownlint flags link *style* (bare URLs, empty
links, same-file fragment validity); and the daily external-URL sweep raises an
issue for dead external links. The rules below cover both how to fix those
failures — always fix the link or its target, never suppress the check — and the
**semantic** hygiene the tools can't verify: that link text is unambiguous and
correctly qualified.

**General rules — apply to every reference:**

- **Never reference a bare identifier.** `002` alone is ambiguous — write
  `ADR 002`. The same holds for any target: name what it is (a section, a file
  like `compose.yml`, a function) so the link text stands on its own. Never use
  "here" or "this" as link text.
- **Keep a prefix label in the link text for a single reference; factor it out
  for a list.** One reference keeps the label inside — `[ADR 002](…)`,
  `[compose.yml](…)`. For a list, where the label can't sit inside each link,
  write it once and link the identifiers: `ADR [002](…), [005](…), and [007](…)`.
- **Same-repo context is implied; cross-repo must be explicit.** A plain
  reference means this repo. Anything elsewhere is qualified with its
  project/repo name and linked to its full URL — e.g.
  `[<Project> ADR 009](https://github.com/<owner>/<repo>/blob/main/docs/decisions/009-….md)`.
- **Anchors:** put enough context in the link text to disambiguate — if the
  heading name alone is ambiguous in the sentence, include the page too (e.g.
  `architecture.md § Naming conventions`).
- **Give any heading you cross-reference a unique name.** Identical heading text
  produces order-dependent GitHub anchors (`#symptom`, `#symptom-1`), so a link
  to a duplicated heading is ambiguous and silently points to the wrong one if a
  same-named heading is later added before it. `MD024: siblings_only` allows
  repeated subsection names under different parents, and lychee resolves the
  `-1`/`-2` suffixes, but the anchor check cannot flag that silent redirect — so
  link targets must be unique.
- **Prefer relative links within the repo; full GitHub URLs for other repos.**
  When linking to source that can move, name the file/symbol (and pin to a tag
  or commit where it matters) so the reference survives churn.
- **When you rename or remove a file, heading/anchor, or symbol, search the repo
  for references and update them** so links don't break — this is what keeps the
  link/anchor check green. Verify links resolve before committing.
- **Fixing a flagged external link (daily sweep issue):** verify each URL. If
  the resource moved, update the link (prefer a stable or pinned URL); if it's
  genuinely gone, remove or replace it. Add a URL to `.lycheeignore` only when it
  legitimately 403/404s while unauthenticated (a 404 can be an existence-hiding
  response) — never to silence a truly dead link.

**ADRs — a concrete example of the general rules:**

- **Local ADR, single:** link the "ADR NNN" text with a path **relative to the
  linking file** — `[ADR 002](002-….md)` from within `docs/decisions/`,
  `[ADR 002](decisions/002-…)` from a doc directly in `docs/`,
  `[ADR 002](../decisions/002-…)` from a doc in a `docs/` subdirectory, and
  `[ADR 002](docs/decisions/002-…)` from a repo-root file (e.g. `CLAUDE.md`).
- **Local ADRs, a list:** `ADR [002](…), [005](…), and [007](…)`.
- **ADR in another repo:** qualify with the repo and link the full text —
  `[<Project> ADR 009](https://github.com/<owner>/<repo>/blob/main/docs/decisions/009-….md)`;
  for a list, `<Project> ADR [001](…), [006](…), and [009](…)`.
````

## Starter prompt for a fresh session

To onboard a repo, start a Claude Code session with that repo (and, if the workflows have moved on, this one as read-only reference), then:

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
- Add the ## Cross-references block and the semantic-line-break / MD028 conventions
  to this repo's CLAUDE.md.

Work on a feature branch, never commit to main, and open a PR. If <owner/target-repo>
has its own CLAUDE.md/CONTRIBUTING guidance, follow it where it differs.
```
