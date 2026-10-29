# ADR-017: Keep the home-grown semantic-line-break tooling rather than adopting mdformat-sembr

- **Date:** 2026-09-08
- **Status:** Accepted (mdformat as a general formatter decided by [ADR-019](019-adopt-mdformat-through-mdformat-markdownlint.md))

## Context

[ADR-015](015-semantic-line-break-check.md) built a dependency-free checker for the one semantic-line-break MUST rule, and the `markdown-standards` plugin in [flungo/claude-plugins](https://github.com/flungo/claude-plugins) ships [`reflow.py`](https://github.com/flungo/claude-plugins/blob/main/plugins/markdown-standards/scripts/reflow.py) as the one-time migration that gets a repo to where the checker accepts it.
Both are home-grown, and a packaged alternative now exists for both roles: [mdformat](https://github.com/hukkin/mdformat), a CommonMark formatter with a plugin system, plus [mdformat-sembr](https://codeberg.org/bugrasan/mdformat-sembr), a plugin that inserts semantic line breaks as soft breaks — a bare newline inside a paragraph, which renders as a space — never as the hard breaks (two trailing spaces, or a backslash) that render as `<br>`.
This ADR records how the pair measures up against the documented intent and against the cases the checker's unit tests pin, and what to do about the difference.

Every fact below was verified against the sources at the versions named — mdformat 1.0.0 (released 2025-10-19), mdformat-sembr 0.2.0 (tagged 2026-07-02), mdformat-gfm 1.0.0, mdformat-frontmatter 2.1.2 — by reading their code and running them, not from recall.
The plugin's canonical home is [`bugrasan/mdformat-sembr` on Codeberg](https://codeberg.org/bugrasan/mdformat-sembr); the GitHub repository its README points to is a mirror that exists only for PyPI publishing.
Its issue tracker held no issues and no pull requests at the time of the evaluation, so nothing below duplicates a known report.

### How the two tools are shaped

The home-grown pair separates two jobs.
The checker reports one thing — a sentence ending part-way through a line with more prose after it — with a file, line and column, never rewrites, never reports a line that could have been broken further, and never suggests joining lines.
The reflow is a one-time pass, gated per block on render-equivalence.

mdformat is a formatter, and mdformat-sembr is a paragraph postprocessor inside it.
The plugin takes each rendered paragraph, **collapses all its whitespace to single spaces**, and re-breaks it after every terminator that is followed by whitespace and a likely sentence start, subject to a `min_chars` threshold (default 15) and an abbreviation list.
That design carries three consequences that no configuration removes:

- **The check is the whole formatter.**
  `mdformat --check` compares a file to its full reformat and exits non-zero on any difference, so it enforces every mdformat style choice — thematic breaks as 70 underscores, every ordered item numbered `1.`, tables padded to column width, setext headings and indented code rewritten — and not only the sentence rule.
  Style ownership moves from the caller's `.markdownlint-cli2.jsonc`, which ADR-015 deliberately left as the adopting repo's, to mdformat's defaults.
  Options narrow the gap: with `--compact-tables`, `--number` and the `mdformat-simple-breaks` plugin, a full reformat of this repo and of `claude-plugins` differs from the committed tree by 50 and 34 lines respectively, almost all of them the table delimiter row (`| -- |` for `| --- |`), and `markdownlint-cli2` 0.23.2 under each repo's own config passes the result.
  The gap is small, but it is a second style authority, and it is the wrong shape for a check whose contract is one rule.
- **A finding has no position.**
  `--check` prints `File "<path>" is not formatted.` and nothing else — no line, no column, no annotation.
  There is no inline suppression comment, and file exclusion (`--exclude`, or `exclude` in `.mdformat.toml`) exists only on Python 3.13 or newer, while the `ubuntu-latest` runner's system Python is 3.12.3.
- **It joins as readily as it breaks.**
  Collapsing first means every existing line break that is not a sentence end is undone — including the clause-level breaks that [sembr.org](https://sembr.org/) recommends as SHOULD and MAY, and that the checker's own conformant fixture carries on purpose.
  Run over the two repos as they stand today, both already conformant, the plugin removed 550 lines and added 318 across 162 hunks.
  Nearly all of it was `**Bold lead-in.** The next sentence.` pairs being joined back onto one line, because the plugin does not see a sentence end inside emphasis.
  A tool that undoes correct breaks cannot serve as a gate, and as a migration it would have to be run once and never again.

Two further facts shape any adoption.
`mdformat-gfm` is required or a table is parsed as a paragraph and protected only by a heuristic, and `mdformat-frontmatter` is required or a frontmatter block is rewritten as a thematic break followed by a setext heading.
And the default `min_chars` of 15 leaves `The first one. The second one.` on one line: enforcing the MUST rule needs `--sembr-min-chars 1`, which is also the setting under which the plugin's abbreviation handling is weakest.

### Against the checker's test cases

The 56 constructs `test_sembr_check.py` pins, plus 13 drawn from the documented intent and from mdformat's own style choices that those tests do not cover, were run through the plugin with the threshold at 1 and the plugin's effect isolated from mdformat's own style changes.
The plugin agreed with the checker on 51 and disagreed on 18:

| Kind | Cases | What happens |
| --- | --- | --- |
| Bug | A paragraph containing a hard line break (`**Date:** …\` or two trailing spaces) | The break is collapsed into a backslash followed by a space, which renders differently; mdformat's validator then refuses to format the **whole file** |
| Bug | The next sentence opens with a link, image or code span | Never broken: the text is masked before the boundary regex runs, so the sentence begins with a placeholder the regex cannot match |
| Bug | The next sentence opens with a non-ASCII capital (`Élément`) | Never broken: the regex accepts `[A-Z0-9]` only |
| Gap | A sentence ending inside emphasis (`**Bold.** Next`, `*Em.* Next`) | Never broken, and an existing break there is joined |
| Gap | A sentence ending inside quotes or brackets (`"no thanks." Then`) | Broken only with the opt-in `--sembr-closing-punct`, which handles `"')]` and nothing else |
| Gap | An initialism or a month (`9 a.m. Monday`, `J. R. R. Tolkien`, `Jan. 2026`) | Broken after each dot: the abbreviation guard is a fixed list with no structural rule, and `--sembr-abbreviations` replaces the list rather than extending it |
| Gap | `<!-- sembr-disable-* -->` | No equivalent; the only exclusion is per file, on Python 3.13+ |
| Gap | A clause-level break already present | Joined, by design (above) |
| Non-issue | An escaped dot `\.`; a malformed reference definition | mdformat drops the needless escape or escapes the brackets; the plugin then acts on ordinary text |

Everything the checker skips structurally — code fences, indented code, headings, tables, frontmatter, HTML blocks, code spans, autolinks, link destinations — the plugin also leaves alone, because mdformat's real CommonMark parser hands it only paragraphs.
That is the plugin's genuine advantage over the hand-rolled block scanner in `sembr_check.py`, and over `reflow.py`'s regex prefix handling for lists and blockquotes.

### With the bugs fixed

The three bugs are small, and each is fixed with tests in a pull request open upstream against the plugin's `v0.2.0`: [pull request 1](https://codeberg.org/bugrasan/mdformat-sembr/pulls/1) for a sentence that opens with a link, code span or non-ASCII capital, [pull request 2](https://codeberg.org/bugrasan/mdformat-sembr/pulls/2) for a sentence ending inside emphasis, and [pull request 3](https://codeberg.org/bugrasan/mdformat-sembr/pulls/3) for hard breaks; [`docs/plans/mdformat-sembr-upstream-fixes.md`](../plans/mdformat-sembr-upstream-fixes.md) tracks them.
Pull request 2 also closes the emphasis-closer gap, since it is the same defect seen from the other side.
With the three applied, the plugin's own 45 tests still pass, agreement with the checker rises to 60 of 69, and the reformat of the two repos shrinks to 41 and 26 changed lines.
What remains is the design: the clause-level breaks it still joins, sentences that open with a lowercase product name, the initialism guard, closing quotes behind an opt-in, and no suppression comment.

## Decision

Do not replace either tool with mdformat-sembr now.

**The check stays home-grown.**
A formatter's `--check` is a whole-style gate, which contradicts the property ADR-015 exists to keep: `markdown-sembr.yml` imposes one rule and leaves style to the caller's linter config.
It also reports no position and offers no suppression, and until the joining behaviour changes upstream ([issue 4](https://codeberg.org/bugrasan/mdformat-sembr/issues/4)) it would fail on prose the convention endorses.
None of that is a bug to fix; it is what a formatter is.

**The reflow stays home-grown for now, and mdformat-sembr is the candidate to replace it.**
Migration is the role a formatter fits, and mdformat's parser handles the structure `reflow.py` hand-rolls.
Re-evaluate once upstream carries the three fixes ([pull requests 1](https://codeberg.org/bugrasan/mdformat-sembr/pulls/1), [2](https://codeberg.org/bugrasan/mdformat-sembr/pulls/2) and [3](https://codeberg.org/bugrasan/mdformat-sembr/pulls/3)) and an insert-only mode that breaks after sentences without collapsing the breaks already there ([issue 4](https://codeberg.org/bugrasan/mdformat-sembr/issues/4)); at that point the remaining differences — a whole-file render gate rather than a per-block one, and a fixed abbreviation list ([issue 5](https://codeberg.org/bugrasan/mdformat-sembr/issues/5)) — are trade-offs to weigh rather than blockers.

**Gaps go upstream, not to a fork or a plugin of our own.**
The plugin is a 260-line module under MIT, six commits old, with a passing test suite and a plugin interface that is the right shape.
Every gap found is a small change to it, and the three bugs are already fixed in [pull requests 1](https://codeberg.org/bugrasan/mdformat-sembr/pulls/1), [2](https://codeberg.org/bugrasan/mdformat-sembr/pulls/2) and [3](https://codeberg.org/bugrasan/mdformat-sembr/pulls/3).
A fork is warranted only if upstream does not respond; a plugin of our own would be that fork under another name, since there is no second design to be had.

**Bugs are reported as pull requests, carried by the plan.**
[Pull requests 1](https://codeberg.org/bugrasan/mdformat-sembr/pulls/1), [2](https://codeberg.org/bugrasan/mdformat-sembr/pulls/2) and [3](https://codeberg.org/bugrasan/mdformat-sembr/pulls/3) are open upstream from a fork under Fabrizio's Codeberg account, together with [issue 4](https://codeberg.org/bugrasan/mdformat-sembr/issues/4) (the insert-only mode) and [issue 5](https://codeberg.org/bugrasan/mdformat-sembr/issues/5) (the initialism guard and additive abbreviations); the plan tracks them to release or refusal.

**mdformat as a general formatter is a separate question, not decided here.**
The measurement above shows it is within a delimiter row of the house style once tuned, which makes it a plausible future addition alongside markdownlint rather than a replacement for anything.
That would need its own ADR and its own argument; [ADR-019](019-adopt-mdformat-through-mdformat-markdownlint.md) makes it.

## Consequences

### Positive

- The check keeps the contract ADR-015 and ADR-016 promise: one rule, a located finding, suppression comments, the linter's ignores, and no runtime dependency.
- The disagreement is recorded case by case, so the question is not re-litigated from recall the next time the plugin comes up; the plan names the conditions under which it is reopened.
- Three upstream fixes, each with tests, are open as pull requests, and the emphasis-closer one alone removes the bulk of the damage the plugin would do to an already-conformant repo.

### Negative — trade-offs

- Two scripts stay maintained here that a packaged tool might one day cover, and `reflow.py` keeps its known limitations until the re-evaluation.
- Whether upstream accepts the patches, and how fast, is outside our control; the plan carries the follow-up.
