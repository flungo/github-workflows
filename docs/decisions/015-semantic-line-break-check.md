# ADR-015: Enforce the semantic line break MUST rule in its own workflow

- Date: 2026-08-02
- Status: Accepted

## Context

[ADR-002](002-markdown-validation-tooling.md) picked the Markdown tooling, and [`markdown-validation.md`](../reference/markdown-validation.md#fabrizios-markdownlint-rule-choices) records the resulting pairing: `MD013` (line-length) is turned **off**, and the convention that replaces it is one sentence per source line — [semantic line breaks](https://sembr.org/).
That page is explicit that nothing enforces the second half: Prettier declined sentence detection as too hard across languages, markdownlint has no reflow rule, so the convention rests on authors remembering it.
The `markdown-standards` plugin ships [`reflow.py`](https://github.com/flungo/claude-plugins/blob/main/plugins/markdown-standards/scripts/reflow.py) to migrate a repo's existing prose in one pass, but that is a one-time tool: a repo that runs it drifts straight back out of shape on the next pull request.

Most of the sembr specification is unenforceable, which is why it stayed a convention.
Its rules are mostly SHOULD and MAY — a break *may* go after a dependent clause, *should* go after an independent one — and deciding whether a line that could have been split further is wrong requires understanding the sentence.
Knowing when to *join* two lines is harder again, because a legitimate optional break looks exactly like an unnecessary one.

Exactly one rule escapes that.
It is a MUST, and it can be decided from the source alone:

> A semantic line break MUST occur after a sentence, as punctuated by a period (.), exclamation mark (!), or question mark (?).

Two sentences sharing a source line is a mechanical, unambiguous violation — precisely the case that produces the paragraph-wide diffs the convention exists to avoid.

## Decision

Check that rule, and only that rule, in CI.

**A checker, not a reformatter.**
[`check-semantic-line-breaks`](../../.github/actions/check-semantic-line-breaks/) is a composite action wrapping a dependency-free Python script (`sembr_check.py`) that reports a sentence ending part-way through a line, as an inline annotation on the offending column.
It never rewrites a file, never reports a line that *could* have been broken further, and never suggests joining anything.
`reflow.py` remains the migration tool; this is the repeatable gate that keeps a migrated repo there.

**Conservative by construction.**
A false positive in a blocking check costs more than a missed break, so where the source is ambiguous the checker stays quiet: it skips a terminator after a known abbreviation or an initialism, and requires what follows to look like a new sentence.
The cost is a handful of documented false negatives.
Confidence comes from the colocated unit tests, whose larger half asserts silence on every construct a naive "break after every `.`" would flag.

**Its own workflow, `markdown-sembr.yml`, rather than a flag on `markdown-lint.yml`.**
Adoption is then the opt-in, so calling `markdown-lint.yml` never starts enforcing a prose style.
An `enabled`-style input on `markdown-lint.yml` was the alternative and fails whichever way its default points:

- **Default on** turns a merge here into a fleet-wide behavioural break.
  Consumers pin the moving `@v2` ([ADR-003](003-version-via-moving-v1-branch.md)), so every repo whose prose is not already reflowed goes red on its next pull request, with no version bump to gate it — the outcome major branches exist to prevent.
- **Default off** is the same opt-in as a separate workflow, but reached by coupling a house-style gate to the deliberately style-neutral linter.
  `markdown-lint.yml` imposes no rules today; the caller's `.markdownlint-cli2.jsonc` is entirely the adopting repo's, and that property is worth keeping.

A separate workflow also gets its own named check in the pull request list, matches how `markdown-links.yml` already sits beside `markdown-lint.yml`, and can carry `globs` / `ignore` inputs without adding surface to a workflow that has none.

**Python with no third-party dependencies.**
`reflow.py`, its ancestor, uses `markdown-it-py` for parsing, which is right for a tool run once by hand.
For a check on every pull request the install is a per-run cost and a pinned supply-chain dependency, so `sembr_check.py` carries just enough CommonMark block structure to know what is not prose.
It runs on the runner's system Python with no setup step.

## Consequences

**Positive:**

- The `MD013`-off half of the pairing stops being enforced by memory.
  A repo that reflows stays reflowed.
- Existing consumers are untouched until they add the caller — no behavioural change rides `@v2`, and the new workflow already follows both naming rules ([ADR-010](010-caller-job-ids-match-the-workflow-filename.md), [ADR-011](011-reusable-job-ids-are-the-check-name.md)): the caller job is `markdown-sembr`, the reusable job sets no `name:`, so the context is `markdown-sembr / sembr`.
- The contract is small (`globs`, `ignore`, plus `<!-- sembr-* -->` suppression comments) and adds no secret or permission.
- The action is exercised pre-merge exactly like `export-terraform-variables`: unit tests plus wiring smoke steps in [`action-tests.yml`](../../.github/workflows/action-tests.yml), and a consumer pinning a feature branch gets that branch's action ([ADR-009](009-composite-action-via-workflow-identity-checkout.md)).
- Opt-in *by adoption* is a property of the product, not a prediction about who adopts.
  Semantic line breaks are the standard for the repos `flungo` owns, so every one of them takes this caller and the context ends up required fleet-wide — while an outside repo can still take `markdown-lint.yml` and `markdown-links.yml` without inheriting a prose style.
  Requiring it everywhere we own is therefore consistent with this ADR rather than a departure from it.

**Negative / trade-offs:**

- One more caller workflow for a repo that wants everything, and a third Markdown check in the pull request list.
- The checker is a hand-rolled Markdown block scanner, so an exotic construct could be misclassified.
  The mitigation is the false-positive half of the test suite plus the suppression comments, and the blast radius is one annotation, not a rewritten file.
- The documented false negatives are permanent: a sentence genuinely ending in "etc." or followed by a lowercase word is not reported.
  Under-reporting is the deliberate direction of the trade.
- **`reflow.py` alone does not produce a tree this check accepts.**
  It splits on a terminator followed by a space, so a sentence ending inside markup — `**A bold lead-in.** The rest.` — is invisible to it, while the checker flags it.
  Reflowing this repo needed a companion pass for 63 such breaks.
  Every repo adopting the check hits the same gap until the plugin's splitter learns the case; [`adopting-markdown-workflows.md`](../runbooks/adopting-markdown-workflows.md) says so at the point it matters.
