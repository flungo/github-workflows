# Architecture Decision Records

Decisions are numbered sequentially and never deleted or renumbered. Each file documents the context, decision, and consequences for a key architectural choice. Superseded decisions keep their file and get a note at the top pointing to the newer ADR.

| # | Title | Status | Summary |
|---|---|---|---|
| [001](001-centralised-reusable-workflows.md) | Centralised reusable workflows | Accepted | Extract the fleet's copy-pasted CI into `workflow_call` reusable workflows in this public repo — a Terraform family (plan/apply, drift) and a repo-agnostic Markdown family. Consumers call them and pin a moving `v1` tag; secrets stay with callers; stalwart's bespoke Terraform pipeline is exempt. |
| [002](002-markdown-validation-tooling.md) | Markdown validation tooling | Accepted | lychee (Rust) for all link + anchor resolution (offline internal PR check + online external sweep); markdownlint-cli2 for style; remark-validate-links the documented fallback if lychee's GitHub-slugger parity ever fails. Rejects markdown-link-check, remark-lint-for-style, and SSG strict modes. |

## Adding a new ADR

1. Create `docs/decisions/<NNN>-<kebab-case-title>.md` using the template below.
2. Update this index with a one-sentence summary.
3. If the new decision supersedes an existing one, update the older ADR's status to `Superseded by ADR-NNN`.

### ADR template

```markdown
# ADR-NNN: Title

Date: YYYY-MM-DD
Status: Accepted

## Context

Why does this decision need to be made?

## Decision

What was decided?

## Consequences

**Positive:**
- ...

**Negative / trade-offs:**
- ...
```
