# The Markdown validation standard

Three reusable workflows that validate Markdown.
They are **not Terraform-specific** — any repo with a `docs/` tree (or Markdown anywhere) can adopt them, and most `flungo` repos should.
For caller snippets and the step-by-step adoption procedure, see [`adopting-markdown-workflows.md`](../runbooks/adopting-markdown-workflows.md).
For *why* these tools were chosen, see [ADR-002](../decisions/002-markdown-validation-tooling.md) and [ADR-015](../decisions/015-semantic-line-break-check.md).

Two of the three are style-neutral and every repo should take them.
The third, `markdown-sembr.yml`, enforces a prose convention, so it is adopted only by repos that write that way — see [§ Semantic line breaks](#semantic-line-breaks-markdown-sembryml).

## Workflows

- [`markdown-lint.yml`](../../.github/workflows/markdown-lint.yml) — `markdownlint-cli2` style/structure linting.
  Rules live in the caller's `.markdownlint-cli2.jsonc`.
  Does not check cross-file links.
- [`markdown-links.yml`](../../.github/workflows/markdown-links.yml) — link validation in two jobs, each self-selecting on the caller's event:
  - **internal** — an offline check of relative links and heading anchors (`lychee --offline --include-fragments`).
    Blocking, on every PR/push; deterministic, no network.
    It scans the whole tree (`'**/*.md'`), so a rename that breaks a link in an untouched file is still caught.
  - **external** — an online sweep of external URLs (`lychee` without `--offline`, which also re-checks internal links + anchors).
    Scheduled/dispatch only (never on a PR, so a flaky outage can't block a merge); reports breakage via a single auto-updated GitHub issue rather than failing the run.
- [`markdown-sembr.yml`](../../.github/workflows/markdown-sembr.yml) — the one hard [semantic line break](https://sembr.org/) rule: two sentences must not share a source line.
  Blocking, on every PR/push.
  **Opt-in by adoption** — it is the only Markdown workflow that imposes a prose style.
  Inputs `globs` and `ignore`; no secrets or permissions.

## Semantic line breaks (`markdown-sembr.yml`)

The pairing that turns `MD013` off (see [§ markdownlint rules that need a deliberate choice](#markdownlint-rules-that-need-a-deliberate-choice)) replaces a character ceiling with a convention: one sentence per source line.
`markdown-sembr.yml` is the half of that pairing a tool can hold up.
The `markdown-standards` plugin's [`reflow.py`](https://github.com/flungo/claude-plugins/blob/main/plugins/markdown-standards/scripts/reflow.py) migrates a repo's existing prose in one pass; this keeps it there.

### What it checks — and only this

Of the sembr rules, one is a MUST that can be decided from the source alone:

> A semantic line break MUST occur after a sentence, as punctuated by a period (.), exclamation mark (!), or question mark (?).

So the check reports exactly one thing: **a sentence that ends part-way through a line, with more prose after it**.
It never reports a line that could have been broken *further* (those rules are SHOULD/MAY — a judgement call), never suggests joining lines, never enforces a line length, and never rewrites a file.
Rules 1 and 2 (a break must not change the rendered output or the meaning) are properties of an edit, not of a file, so nothing static can check them.

Only prose is scanned.
Frontmatter, fenced and indented code, HTML blocks, tables, ATX and setext headings, thematic breaks and link reference definitions are skipped wholesale; within a prose line, code spans, autolinks and link destinations are skipped too.
Blockquote and list-item text **is** prose and is checked, with the structural prefix stripped — so a `1.` list marker is never read as a sentence end.

### Where it deliberately stays quiet

A false positive in a blocking check costs more than a missed break, so the checker under-reports by design.
It says nothing when:

| Case | Example | Why |
| --- | --- | --- |
| A known abbreviation precedes the `.` | `…, etc. Then the next point.` | Unknowable without parsing the sentence; the list is kept to terms implausible as a sentence's last word |
| An initialism or initial precedes it | `the U.S. Government`, `at 9 a.m. Monday`, `J. R. R. Tolkien` | Recognised structurally — a dotted token whose every segment is one letter |
| What follows is lowercase | `It needs approx. five minutes.` | The safety net for abbreviations nobody listed |
| The `.` is escaped or an ellipsis | `1\. not a list`, `trails off… And on` | Deliberately ambiguous as a sentence end |

The first two rows are permanent blind spots: a sentence genuinely ending in "etc." is not reported.
That is the intended direction of the trade — see [ADR-015](../decisions/015-semantic-line-break-check.md).

It is stricter than `reflow.py` in one place, which matters when migrating a repo: a sentence ending inside markup (`**A bold lead-in.** The rest.`) is a break `reflow.py` cannot see, because the period is followed by `*` rather than a space.
See [§ Adopt it only alongside the reflow](../runbooks/adopting-markdown-workflows.md#adopt-it-only-alongside-the-reflow).

### Suppressing a finding

For the cases it still gets wrong, four HTML comments, mirroring markdownlint's inline configuration:

```markdown
<!-- sembr-disable-file -->        skip the whole file
<!-- sembr-disable-next-line -->   skip the next line
<!-- sembr-disable -->             skip until re-enabled
<!-- sembr-enable -->
```

Prefer a suppression comment over widening `ignore`, and prefer fixing the prose over either.

### Inputs

| Input | Default | Notes |
| --- | --- | --- |
| `globs` | `**/*.md` | Newline-separated. Unlike most Markdown tooling this **does** reach into dot directories, so a repo's `.github/*.md` is checked |
| `ignore` | *(empty)* | Newline-separated. A pattern naming a directory covers everything beneath it, and an unanchored pattern matches at any depth |

The check itself is the [`check-semantic-line-breaks`](../../.github/actions/check-semantic-line-breaks/) composite action — a dependency-free Python script run on the runner's system Python, fetched at the workflow file's own commit ([ADR-009](../decisions/009-composite-action-via-workflow-identity-checkout.md)) rather than a pinned ref.
Its colocated `test_sembr_check.py` is where the confidence lives: the larger half of it asserts silence on every construct a naive "break after every `.`" would have flagged.

## Tool selection

lychee (Rust) does all link + anchor resolution — internal and external; markdownlint-cli2 does style.
remark-validate-links is the documented fallback if lychee's slugger ever diverges from GitHub's.
The full rationale and rejected alternatives are in [ADR-002](../decisions/002-markdown-validation-tooling.md).

## markdownlint rules that need a deliberate choice

This workflow imposes **no** rules — the caller's `.markdownlint-cli2.jsonc` is entirely the adopting repo's.
Four rules are worth deciding deliberately rather than leaving to a default, because each is half of a pair: the machine-checkable rule, plus a human convention the tool can't enforce.
The trade-offs are below so a repo can make its own call; Fabrizio's choices, and the conventions that pair with them, ship in the [`markdown-standards` plugin](https://github.com/flungo/claude-plugins/tree/main/plugins/markdown-standards) for repos that want them.

- **`MD013` (line-length) — turn it off if you adopt semantic line breaks.**
  A character ceiling is the wrong tool for prose consistency: it only caps, it can't reflow, and 80 columns is archaic.
  The convention is one sentence per source line, which Markdown renders as one paragraph — for sentence-scoped diffs and review comments, and no paragraph-wide reflow churn when a sentence changes.
  No general-purpose formatter enforces one-sentence-per-line (Prettier declined it — cross-language sentence detection is too hard — and markdownlint has no reflow rule), so the bulk of it stays a convention, with `MD013` off so nothing fights it.
  Its one MUST rule *is* enforceable, and [`markdown-sembr.yml`](#semantic-line-breaks-markdown-sembryml) enforces that much; the rest still rests on the author.
  ("Semantic line breaks" / "ventilated prose" — see <https://sembr.org/> — has no universal consensus; adopted for the diff and review benefits.)
- **`MD024` (no-duplicate-heading) — `siblings_only` trades strictness for repeatable subsection names.**
  `siblings_only` lets docs repeat subsection names (e.g. `Context` / `Decision` / `Consequences` across ADRs, or `Symptom` / `Root cause` across incidents) under different parents.
  The paired convention: give any heading you cross-reference a unique name — see "Duplicate headings and anchor ambiguity" below for the gap it closes.
- **`MD060` (table-column-style) — pin a style; the default is ambiguous.**
  `"consistent"` infers the style per table, so a table where no row disambiguates — cells all different widths — infers `"aligned"` (every cell padded out to its column's widest) while the rest of the repo is `"compact"` (one space each side of every pipe).
  Pin one.
  The argument for `"compact"` is the same as the one for turning `MD013` off: a diff should be the size of the change.
  Under `"aligned"` cell width is shared state, so editing one cell reflows the whitespace of every row and a one-word change arrives as a whole-table diff — and a single long cell taxes every other row with padding for as long as it stays.
  Compact has no such coupling: a cell's source is its own content, so the diff names the row that changed.
  Two lesser points fall out the same way — `markdownlint-cli2 --fix` produces compact but will not pad to alignment, so an inferred-aligned table becomes hand editing; and aligned tables stop being readable in source as soon as one cell is long.
- **`MD028` (no-blanks-blockquote) — left enabled, the fix is a judgement call.**
  Two blockquotes separated by only a blank line are two *separate* blockquotes in CommonMark/GFM (the blank line ends the first), but the split is parser-ambiguous, so `MD028` flags it.
  The paired convention: fix to match intent — `>` on the blank line to make one blockquote; to keep two distinct ones, prefer a connecting sentence between them where one flows naturally, else an invisible `<!-- -->` separator (never manufacture filler just to avoid the comment); and never collapse distinct notes into one just to silence the rule.

## Duplicate headings and anchor ambiguity (MD024 `siblings_only`)

`MD024` is set to `siblings_only` so docs can repeat subsection names under different parents.
That leaves one narrow gap in the "someone adds a duplicate of a heading that was already linked" risk:

| Case | Link outcome | Caught by |
| --- | --- | --- |
| New duplicate is a **sibling** (same parent) | — | **MD024 `siblings_only`** blocks it |
| Non-sibling, added **after** the linked heading | still correct | no breakage |
| Non-sibling, added **before** the linked heading | silently redirects to the new heading | **neither** (anchor still resolves) |
| Heading renamed / removed / typo'd | dangles | **lychee** (`Cannot find fragment`) |

lychee replicates GitHub's stateful suffixing — two `## Symptom` headings resolve as `#symptom` and `#symptom-1`, and `#symptom-2` is flagged — but it is existence-only, so it has **no** way to flag an *ambiguous* base-slug link, and `--include-fragments` has no strict/ambiguity mode.
The only built-in lever that removes the ambiguity entirely is `MD024` **without** `siblings_only` (disallow all duplicate headings) — the opposite trade-off, which would force prefixing every repeated subsection.

**The convention that closes it:** give any heading you cross-reference a **unique** name; repeat heading text only where it is not a link target.
(This is one of the conventions the `markdown-standards` plugin encodes.)
That structurally closes the one residual gap (a non-sibling duplicate inserted before a linked heading).

**Phase 2c (optional, not built):** to close that gap with tooling instead of convention, a custom markdownlint rule (JS) or a small CI script could flag any internal link whose base slug belongs to a heading that appears more than once in the target file.
Left as an optional enhancement — the convention above suffices, and it is added maintenance for a narrow case.

## `LYCHEE_GITHUB_TOKEN` provisioning

The external sweep needs a token to resolve links to **all repositories the user can read** (including private ones) and to avoid public-GitHub rate limits.

- **Token:** create a **fine-grained PAT** — resource owner = the account/org, repository access = **All repositories**, permissions = **Contents: Read-only** and **Metadata: Read-only** (Metadata is mandatory).
  Set an expiry and a rotation reminder.
  (A classic PAT with `repo` scope also works but is broader than needed.)
- **Store once, reuse everywhere:** if the account is a GitHub **organization**, add it as an **organization Actions secret** named `LYCHEE_GITHUB_TOKEN`, visible to all repositories — set once, inherited by every project.
  On a **personal account** (no org-level Actions secrets) it must be added as a repo secret per repo.
- **Why the `LYCHEE_` prefix:** it namespaces the secret so a differently-scoped GitHub token needed by another job cannot collide.
- **Pass it via the action's `token` input, not `env` (gotcha):** set `token: ${{ secrets.LYCHEE_GITHUB_TOKEN }}` on the lychee-action step.
  Do **not** use a step-level `env: GITHUB_TOKEN` — the action's `entrypoint.sh` exports `GITHUB_TOKEN` from its `token` input, which **defaults to `${{ github.token }}`** (the automatic, repo-scoped token), and that export overrides any `GITHUB_TOKEN` set via `env`.
  An env-var token therefore silently loses to the default, which cannot read *other* private repos — the links 404 exactly as if no token were provided.

## Per-repo config

- **`.markdownlint-cli2.jsonc`** — the caller's markdownlint rules.
  Start from the defaults above; give each additional override an inline justification.
  Repo-specific — regenerate, don't copy.
- **`.lycheeignore`** — one regex per line (`#` comments supported); URLs that legitimately **403/404 while unauthenticated** (a 404 can be an existence-hiding response), or repos deliberately not authenticated against.
  Repo-specific — regenerate per repo from that repo's own findings, never copy another repo's entries.
- **`LYCHEE_GITHUB_TOKEN`** secret — provisioned as above; required for the external job.

## Versioning

Pin `@v2` — a moving **branch**, not a tag ([ADR-003](../decisions/003-version-via-moving-v1-branch.md)); it advances automatically on every merge to `main` (see [`releasing.md`](../runbooks/releasing.md)).
See [`adopting-markdown-workflows.md`](../runbooks/adopting-markdown-workflows.md) for the callers and the full adoption procedure.
