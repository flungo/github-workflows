# ADR-019: Adopt mdformat as the fleet's Markdown formatter, bridged by mdformat-markdownlint

- **Date:** 2026-09-20
- **Status:** Proposed — accepted when the workflow lands, after `mdformat-markdownlint` publishes

## Context

[ADR-017](017-keep-home-grown-sembr-tooling-over-mdformat-sembr.md) evaluated [mdformat](https://github.com/hukkin/mdformat) together with mdformat-sembr as a replacement for the semantic-line-break check and reflow, kept both home-grown, and left mdformat as a general formatter as a separate question.
This ADR records that question's evaluation, the conclusion it reached, and what follows from it.
Every fact below was established by running the tools rather than from recall: mdformat 1.0.0 with mdformat-gfm 1.0.0 and mdformat-frontmatter 2.1.2, and markdownlint 0.41.1 through markdownlint-cli2 0.23.2, over this repository and [flungo/claude-plugins](https://github.com/flungo/claude-plugins) as they stood on 2026-09-10, and over a probe corpus of one violation per markdownlint rule.

### What mdformat alone adds, and where it diverges

mdformat enforces four things markdownlint does not:

- **Render equivalence.**
  Every change is validated against the CommonMark AST, so a formatting pass cannot alter what a file renders to; markdownlint's fixer has no such check.
- **Loose-list honesty.**
  A list that renders loose because one item holds a blank line is written loose throughout, so the source shows what already renders.
- **Defensive escaping.**
  A prose line that would re-parse as a bullet, heading, blockquote or thematic break is escaped rather than silently re-read.
- **Tidying with no rule behind it.**
  Reference definitions gathered at the end, sorted and de-duplicated, minimal code-span backticks, and hard breaks written as a visible backslash.

Of the 52 markdownlint rules the fleet's configuration enforces, mdformat's output cannot violate 23.
markdownlint's own fixer already repairs 17 of those and 11 more that mdformat does not touch, so mdformat alone adds six rules the fixer cannot repair (MD003, MD035, MD046, MD048, MD055, MD056), none of which either repository had ever tripped.
The 13 rules neither fixes are judgements about content.
Run over both repositories after tuning, mdformat changed 44 table delimiter rows, 31 loose-list blank lines and 2 escapes, and found no mistake.

It also diverges from the fleet's standards in ways no option removes:

- A blank line is inserted after every HTML comment, because a comment is its own block, which detaches `markdownlint-disable-next-line` and `sembr-disable-next-line` from the line they govern.
- A compact table's delimiter row is written as `--` per column, where the prose convention wrote `---`.
- An empty compact cell is written as two spaces between pipes, which MD060's compact style rejects, so a table with an empty cell has no form both tools accept.
- Ordered lists are renumbered `1.` throughout unless `--number` is given, and with it a list of ten or more items is zero-padded.
- File exclusion exists only on Python 3.13 or newer, and `mdformat --check` names the failing file with no line and no diff.

### Why mdformat alone was not worth adopting

Three objections, in order of weight.
First, and structurally, two style authorities that move independently: mdformat's changelog disclaims a stable style across versions and the fleet's markdownlint floats with its action's major tag, so any bump on either side can produce a file the formatter insists on and the linter rejects, and the failure lands on whichever pull request runs next.
Second, the two conflicts above with no file satisfying both tools, the detached directive and the empty cell.
Third, no gain on the day: every rule mdformat makes unviolatable was already enforced in CI, and the changes it made across both repositories were reformatting, not corrections.

The owner's position settled the parts that are preference rather than fact.
The new enforcements and most of the divergences are wanted, since they make the raw Markdown more readable as plain text; mdformat's decisions on delimiter rows and empty cells are accepted as the formatter's to make; and a newer runner image is preferable to working around the exclusion gap.
What remained was the structural objection and the two conflicts.

### What changes the answer

A prototype mdformat plugin removed both conflicts, keeping a comment block flush against the block it precedes and writing an empty compact cell as one space, and then derived mdformat's `compact_tables` and `number` options from the repository's `.markdownlint-cli2.jsonc` and honoured its `ignores`, so a repository declares its style once, to markdownlint, and mdformat follows.
The structural objection is exactly what such a plugin binds when it comes with two more things: a markdownlint preset carrying every setting mdformat's fixed choices satisfy, so the linter is configured to accept the formatter in the shape of eslint-config-prettier, and a corpus that formats and lints one input per rule and option value against pinned versions of both tools, so a bump on either side fails that project's CI rather than a consumer's pull request.
That is a real project to own, with a version matrix against both tools and upkeep for every rule markdownlint adds, and it is larger than adopting mdformat itself; it is built as [flungo/mdformat-markdownlint](https://github.com/flungo/mdformat-markdownlint), whose ADR-001 records the shape, whose ADR-002 records the contract an adopter may rely on, and whose plan tracks the build-out from skeleton to published packages.

## Decision

**mdformat becomes the fleet's Markdown formatter once `mdformat-markdownlint` and its preset `markdownlint-config-mdformat` are published, and not before.**
Alone it is a second style authority and stays out; with the plugin, the preset and the corpus, the markdownlint configuration stays the one style declaration and the agreement between the two tools is tested rather than hoped.

**The vehicle is a reusable workflow in the Markdown family here.**
It runs mdformat in check mode with the `gfm`, `tables`, `frontmatter` and `markdownlint` extensions at pinned versions, and fails showing the diff, since `mdformat --check` names only the file.
The fixer role passes from `markdownlint-cli2 --fix` to mdformat; markdownlint stays the only gate on content.

**It is opt-in by adoption, like `markdown-sembr.yml`, and the argument is made here rather than cited.**
A formatter's check enforces every fixed decision the formatter makes, which is a prose style in the sense [ADR-015](015-semantic-line-break-check.md) means, so a repository that takes `markdown-lint.yml` and `markdown-links.yml` must be able to leave this one.
A repository that adopts it also extends the preset in its own `.markdownlint-cli2.jsonc`, so its markdownlint configuration remains the single declaration and `.mdformat.toml` never needs to exist.
The semantic-line-break check stays its own one-rule workflow, as ADR-017 decided; this ADR does not reopen that.

**Adoption is per repository, each recording it in its own ADR.**
`mdformat-markdownlint`'s adoption of itself comes first, then this repository and `claude-plugins`, then the rest of the fleet.
A required check follows the order the sembr context took: adopt, watch it report green, then require.

**Settled when the workflow is built, not here:** how the pinned versions are expressed and bumped, whether the job runs the sembr check on mdformat's output as well, and the runner image.

## Consequences

### Positive

- One style declaration per repository, read by the linter, the formatter and the semantic-line-break check alike.
- Drift between the two tools is caught by `mdformat-markdownlint`'s corpus before any consumer sees it, which is where a bump on either side belongs.
- The plain-text readability the owner wanted, render-equivalent by construction, replaces a fixer that has no such guarantee.

### Negative — trade-offs

- A package to own, with a version matrix against both tools and upkeep as markdownlint adds rules; if it lapses the fleet is back to two drifting authorities with a gate that notices after the fact.
- Every adopting repository reflows once, mostly delimiter rows and loose lists, and the prose convention's `---` delimiter row gives way to the formatter's.
- A formatter gate is a whole-style gate, the property ADR-017 rejected for the semantic-line-break check; it is accepted here knowingly, for a separate workflow a repository opts into.
