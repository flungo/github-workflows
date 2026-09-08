# Plan: contribute the mdformat-sembr fixes upstream

One-time procedure; retire this file once every item below is done or declined.
The decision it serves is [ADR-017](../decisions/017-keep-home-grown-sembr-tooling-over-mdformat-sembr.md).

## What is being contributed

Three bug fixes against [mdformat-sembr](https://codeberg.org/bugrasan/mdformat-sembr) `v0.2.0`, each with tests, open upstream as pull requests:

| Pull request | Fixes | Notes |
| --- | --- | --- |
| [1](https://codeberg.org/bugrasan/mdformat-sembr/pulls/1) | A sentence that opens with a link, image or code span is never broken, because the text is masked before the boundary regex runs; a non-ASCII capital is never a sentence start | Moves the sentence-start decision out of the regex into a function that reads through the placeholder; 12 tests |
| [2](https://codeberg.org/bugrasan/mdformat-sembr/pulls/2) | `**A bold lead-in.** The rest.` is never broken at the `**`, and an existing break there is joined | Emphasis and strikethrough closers are recognised unconditionally; `closing_punct` now accepts combinations and curly quotes; 8 tests. Depends on 1 |
| [3](https://codeberg.org/bugrasan/mdformat-sembr/pulls/3) | A paragraph with a hard break is collapsed into a backslash followed by a space, which changes the rendered HTML, so mdformat refuses the whole file | Splits on hard breaks and breaks each run independently; 5 tests. Independent of the other two |

With all three applied on top of `v0.2.0` the plugin's own 45 tests and the 25 added ones pass.

Two further changes were identified and raised as issues rather than fixed, because each is a design choice for the maintainer rather than a defect:

- **An insert-only mode.**
  The plugin collapses a paragraph's whitespace before re-breaking it, so every existing break that is not a sentence end is undone — including the clause-level breaks that [sembr.org](https://sembr.org/) recommends.
  An option that inserts a break after each sentence and leaves the rest of the paragraph's line structure alone is what would let the plugin serve as a migration for a repo on semantic line breaks without destroying hand-placed breaks, and is the condition ADR-017 sets for re-evaluating it as the `reflow.py` replacement.
- **A structural initialism guard, and additive abbreviations.**
  `9 a.m. Monday` and `J. R. R. Tolkien` are broken after each dot; a dotted token whose every segment is one letter is never a sentence end, and that rule needs no list.
  Separately, `--sembr-abbreviations` replaces the default list rather than extending it, so adding the months means restating all the defaults.

## Submitting

The plugin's canonical home is [`bugrasan/mdformat-sembr` on Codeberg](https://codeberg.org/bugrasan/mdformat-sembr); issues and contributions are tracked there, and the GitHub repository is a mirror that exists only for PyPI publishing.
Its README names `adel/mdformat-sembr` as the home instead, but no such repository exists — the `adel` account does, without it — so `bugrasan` is the address that works.

The series is submitted, from the Codeberg fork [`flungo/mdformat-sembr`](https://codeberg.org/flungo/mdformat-sembr) (the same branches also sit on the GitHub fork of the same name):

| Fix | Branch | Upstream |
| --- | --- | --- |
| 1 | `fix/sentence-start-detection` | [pull request 1](https://codeberg.org/bugrasan/mdformat-sembr/pulls/1) |
| 2 | `fix/emphasis-closers` (stacked on 1) | [pull request 2](https://codeberg.org/bugrasan/mdformat-sembr/pulls/2) |
| 3 | `fix/hard-breaks` | [pull request 3](https://codeberg.org/bugrasan/mdformat-sembr/pulls/3) |
| Insert-only mode | — | [issue 4](https://codeberg.org/bugrasan/mdformat-sembr/issues/4) |
| Initialism guard, additive abbreviations | — | [issue 5](https://codeberg.org/bugrasan/mdformat-sembr/issues/5) |

The upstream tracker held no issues or pull requests before these, so none duplicates a known report.

Pull request 2 targets `main` and carries the commits of both 1 and 2; it cannot be stacked the way a same-repository branch would be.
A pull request from a fork can only target a branch of the upstream repository, and Forgejo's retargeting on merge applies only when the merged branch lives in that repository too, so the stack is stated in the description instead, and the diff reduces to the second commit once pull request 1 merges.
Marking one pull request dependent on another is a Forgejo feature the repository has enabled, but it needs write access there, which a contributor does not have.

A cloud session reaches Codeberg through the `codeberg` API credential recorded in the `personal-cloud-environment` skill — the proxy attaches the token, so the session sends `git` and `curl` requests with no credential of its own — and Forgejo's API is documented by the spec the instance itself serves at `https://codeberg.org/swagger.v1.json`.

What remains:

1. Watch the three pull requests and two issues for maintainer response; rebase a branch if asked, and re-push it to the fork.
2. When a fix is released, note the version here; when all three are released or declined, retire this plan and record the outcome in ADR-017's status line.

## Status

- [x] Sentence-start fix submitted — pull request 1
- [x] Emphasis-closer fix submitted — pull request 2
- [x] Hard-break fix submitted — pull request 3
- [x] Insert-only mode proposed — issue 4
- [x] Initialism guard proposed — issue 5
- [ ] Re-evaluation trigger in ADR-017 either met or closed
