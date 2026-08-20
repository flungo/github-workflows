# ADR-016: The semantic-line-break check inherits markdownlint's `ignores`

- Date: 2026-08-19
- Status: Accepted

## Context

[ADR-015](015-semantic-line-break-check.md) added `markdown-sembr.yml` alongside `markdown-lint.yml`.
Both scan a repo's Markdown, and both need to skip the same thing: pre-canned data.
A fixture, a sample input, a recorded response is reproduced to look like the thing it stands in for, so imposing a prose style on it changes what it exists to preserve.

`markdown-lint.yml` already learns that from the caller's `.markdownlint-cli2.jsonc` `ignores`.
`markdown-sembr.yml` had no idea, so a repo had to state the same exclusion twice, in two files, in two glob dialects — and keep them in step by hand.

The first consumer proved that does not hold.
[flungo/claude-plugins](https://github.com/flungo/claude-plugins) adopted the check with its linter already excluding `plugins/*/evals/fixtures/**`, and the check reached those files.
Nothing went red, because the fixtures happened to be conformant — which is the worst version of the failure, since the divergence was invisible until someone wrote a deliberately messy fixture.
The fix landed there as a second exclusion, written by hand, in the second dialect.
That is the convention this ADR replaces: a rule maintained in two places diverges, and here it diverges silently, as a green build.

## Decision

The checker reads `ignores` from the repo's markdownlint-cli2 config and applies them on top of its own `--ignore`.
**On by default**, since a repo that excludes a tree from one Markdown check almost always means both, and the exception is rarer than the rule.
`inherit-markdownlint-ignores: false` turns it off; `--no-markdownlint-config` does the same for a direct or local run.

Only `.markdownlint-cli2.jsonc` and `.markdownlint-cli2.yaml` are read, in markdownlint's own precedence.
The `.cjs` and `.mjs` forms are JavaScript and cannot be evaluated from a dependency-free Python script, so they are **reported rather than skipped quietly** — silence there would recreate exactly the invisible divergence this removes.
The `.markdownlint.*` family carries only the `config` object, so there is nothing in it to read.

Patterns are translated, not copied.
globby reads `**/` as *zero or more* directories, so `**/fixtures/**` covers a top-level `fixtures/` as well as a nested one; this checker spells "at any depth" as a bare name, and its `**/…` requires at least one leading directory.
Importing verbatim would therefore leave the top-level copy in scope — under-excluding relative to the linter, which is the same silent divergence in a new place.
Stripping the wildcard prefix and the "everything beneath" suffix makes the two agree.

A `*` inside a path segment is passed through and **flagged**: globby confines it to one segment where this checker lets it span separators, so such a pattern can exclude more here than there, and that direction costs coverage of the gate.
A negated (`!`) entry is skipped and flagged rather than guessed at.

## Consequences

A repo states an exclusion once, in the file that already had it, and both checks honour it.
Adopting `markdown-sembr.yml` no longer means auditing the linter config and restating it, and the two cannot drift apart on the next edit.

The check now depends on a file it does not own.
That is the point, but it means a malformed or unreadable config degrades the gate rather than the linter — so every such case prints why, and a config that simply does not exist stays silent, because most repos have none and a per-run note about it would be noise.

Consumers pinning `@v2` get this without acting.
It only ever *adds* exclusions, so the failure mode of the change is a check that scans less than before, never one that starts failing on prose that used to pass — no consumer's build breaks on the bump.
A repo that wants the prose gate over a tree its linter skips sets the input to `false`.

YAML support needs PyYAML, which is not a hard dependency: without it the checker says so and carries on, rather than pretending the config was empty.
