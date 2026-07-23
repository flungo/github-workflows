# The Markdown validation standard

Two reusable workflows that validate Markdown. They are **not Terraform-specific** — any repo with a `docs/` tree (or Markdown anywhere) can adopt them, and most `flungo` repos should. For caller snippets and the step-by-step adoption procedure, see [`adopting-markdown-workflows.md`](../runbooks/adopting-markdown-workflows.md). For *why* these tools were chosen, see [ADR-002](../decisions/002-markdown-validation-tooling.md).

## Workflows

- [`markdown-lint.yml`](../../.github/workflows/markdown-lint.yml) — `markdownlint-cli2` style/structure linting. Rules live in the caller's `.markdownlint-cli2.jsonc`. Does not check cross-file links.
- [`markdown-links.yml`](../../.github/workflows/markdown-links.yml) — link validation in two jobs, each self-selecting on the caller's event:
  - **internal** — an offline check of relative links and heading anchors (`lychee --offline --include-fragments`). Blocking, on every PR/push; deterministic, no network. It scans the whole tree (`'**/*.md'`), so a rename that breaks a link in an untouched file is still caught.
  - **external** — an online sweep of external URLs (`lychee` without `--offline`, which also re-checks internal links + anchors). Scheduled/dispatch only (never on a PR, so a flaky outage can't block a merge); reports breakage via a single auto-updated GitHub issue rather than failing the run.

## Tool selection

lychee (Rust) does all link + anchor resolution — internal and external; markdownlint-cli2 does style. remark-validate-links is the documented fallback if lychee's slugger ever diverges from GitHub's. The full rationale and rejected alternatives are in [ADR-002](../decisions/002-markdown-validation-tooling.md).

## markdownlint rule defaults and their paired conventions

These are the standard adoption for every repo following this workflow, not per-repo decisions — set them from the start in the caller's `.markdownlint-cli2.jsonc`. A repo may add further overrides on top, each with an inline justification. Each rule below is half of a pair: the machine-checkable rule, plus a human convention the tool can't enforce that belongs in the adopting repo's `CLAUDE.md` (the generic block is in the runbook).

- **`MD013` (line-length) — disabled; adopt semantic line breaks.** A character ceiling is the wrong tool for prose consistency: it only caps, it can't reflow, and 80 columns is archaic. The convention is one sentence per source line, which Markdown renders as one paragraph — for sentence-scoped diffs and review comments, and no paragraph-wide reflow churn when a sentence changes. Nothing enforces one-sentence-per-line (Prettier declined it — cross-language sentence detection is too hard — and markdownlint has no reflow rule), so it is a convention, with `MD013` off so nothing fights it. ("Semantic line breaks" / "ventilated prose" — see <https://sembr.org/> — has no universal consensus; adopted for the diff and review benefits.)
- **`MD024` (no-duplicate-heading) — `siblings_only`; adopt the unique-heading convention.** `siblings_only` lets docs repeat subsection names (e.g. `Context` / `Decision` / `Consequences` across ADRs, or `Symptom` / `Root cause` across incidents) under different parents. The paired convention: give any heading you cross-reference a unique name — see "Duplicate headings and anchor ambiguity" below for the gap it closes.
- **`MD028` (no-blanks-blockquote) — kept at its default (enabled); adopt the adjacent-blockquote convention.** Two blockquotes separated by only a blank line are two *separate* blockquotes in CommonMark/GFM (the blank line ends the first), but the split is parser-ambiguous, so `MD028` flags it. The paired convention: fix to match intent — `>` on the blank line to make one blockquote; to keep two distinct ones, prefer a connecting sentence between them where one flows naturally, else an invisible `<!-- -->` separator (never manufacture filler just to avoid the comment); and never collapse distinct notes into one just to silence the rule.

## Duplicate headings and anchor ambiguity (MD024 `siblings_only`)

`MD024` is set to `siblings_only` so docs can repeat subsection names under different parents. That leaves one narrow gap in the "someone adds a duplicate of a heading that was already linked" risk:

| Case | Link outcome | Caught by |
|---|---|---|
| New duplicate is a **sibling** (same parent) | — | **MD024 `siblings_only`** blocks it |
| Non-sibling, added **after** the linked heading | still correct | no breakage |
| Non-sibling, added **before** the linked heading | silently redirects to the new heading | **neither** (anchor still resolves) |
| Heading renamed / removed / typo'd | dangles | **lychee** (`Cannot find fragment`) |

lychee replicates GitHub's stateful suffixing — two `## Symptom` headings resolve as `#symptom` and `#symptom-1`, and `#symptom-2` is flagged — but it is existence-only, so it has **no** way to flag an *ambiguous* base-slug link, and `--include-fragments` has no strict/ambiguity mode. The only built-in lever that removes the ambiguity entirely is `MD024` **without** `siblings_only` (disallow all duplicate headings) — the opposite trade-off, which would force prefixing every repeated subsection.

**Rule to apply proactively:** give any heading you cross-reference a **unique** name; repeat heading text only where it is not a link target. That structurally closes the one residual gap (a non-sibling duplicate inserted before a linked heading).

**Phase 2c (optional, not built):** to close that gap with tooling instead of convention, a custom markdownlint rule (JS) or a small CI script could flag any internal link whose base slug belongs to a heading that appears more than once in the target file. Left as an optional enhancement — the convention above suffices, and it is added maintenance for a narrow case.

## `LYCHEE_GITHUB_TOKEN` provisioning

The external sweep needs a token to resolve links to **all repositories the user can read** (including private ones) and to avoid public-GitHub rate limits.

- **Token:** create a **fine-grained PAT** — resource owner = the account/org, repository access = **All repositories**, permissions = **Contents: Read-only** and **Metadata: Read-only** (Metadata is mandatory). Set an expiry and a rotation reminder. (A classic PAT with `repo` scope also works but is broader than needed.)
- **Store once, reuse everywhere:** if the account is a GitHub **organization**, add it as an **organization Actions secret** named `LYCHEE_GITHUB_TOKEN`, visible to all repositories — set once, inherited by every project. On a **personal account** (no org-level Actions secrets) it must be added as a repo secret per repo.
- **Why the `LYCHEE_` prefix:** it namespaces the secret so a differently-scoped GitHub token needed by another job cannot collide.
- **Pass it via the action's `token` input, not `env` (gotcha):** set `token: ${{ secrets.LYCHEE_GITHUB_TOKEN }}` on the lychee-action step. Do **not** use a step-level `env: GITHUB_TOKEN` — the action's `entrypoint.sh` exports `GITHUB_TOKEN` from its `token` input, which **defaults to `${{ github.token }}`** (the automatic, repo-scoped token), and that export overrides any `GITHUB_TOKEN` set via `env`. An env-var token therefore silently loses to the default, which cannot read *other* private repos — the links 404 exactly as if no token were provided.

## Per-repo config

- **`.markdownlint-cli2.jsonc`** — the caller's markdownlint rules. Start from the defaults above; give each additional override an inline justification. Repo-specific — regenerate, don't copy.
- **`.lycheeignore`** — one regex per line (`#` comments supported); URLs that legitimately **403/404 while unauthenticated** (a 404 can be an existence-hiding response), or repos deliberately not authenticated against. Repo-specific — regenerate per repo from that repo's own findings, never copy another repo's entries.
- **`LYCHEE_GITHUB_TOKEN`** secret — provisioned as above; required for the external job.

## Versioning

Pin `@v1` — a moving **branch**, not a tag ([ADR-003](../decisions/003-version-via-moving-v1-branch.md)); it advances automatically on every merge to `main` (see [`releasing.md`](../runbooks/releasing.md)). See [`adopting-markdown-workflows.md`](../runbooks/adopting-markdown-workflows.md) for the callers and the full adoption procedure.
