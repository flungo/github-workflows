# ADR-002: Markdown validation tooling

Date: 2026-07-21
Status: Accepted

## Context

The Markdown family (`markdown-lint.yml`, `markdown-links.yml`) has to mechanically verify three things so documentation rot is caught at review time: every relative link resolves to a real file, every heading anchor resolves to a real heading (same-file **and** cross-file), external URLs stay live, and prose follows a consistent structure. This decision records which tools do that and why, so the choice is not silently re-litigated when adopting the workflows elsewhere. It was reached during the original rollout in `stalwart.flungo.net` (the repo where these workflows were first built) and is carried here unchanged as the fleet standard.

The choice was made on **merits**, not toolchain footprint: a Node-based GitHub Action runs entirely inside the workflow runner and adds nothing to the repo tree, so "avoids Node" is not a real advantage.

## Decision

**Link + anchor resolution → [lychee](https://github.com/lycheeverse/lychee) (Rust) via [`lycheeverse/lychee-action`](https://github.com/lycheeverse/lychee-action).**

- It is the strongest option for **external URL checking** — async, caching, retry/accept controls, `.lycheeignore`, GitHub-token auth — clearly ahead of the remark ecosystem's `remark-lint-no-dead-urls`.
- It also checks **relative links and cross-file heading anchors** offline (`--offline --include-fragments`), so a **single tool** covers both the offline PR-blocking job (internal) and the online scheduled job (external).
- lychee targets **GitHub-compatible anchor slugs**. Exact parity with GitHub's slugger was verified empirically during the original rollout (the `#upgrade--stalwart-v0165--v0168` case). If it ever diverges on a real heading, the internal job switches to remark-validate-links (below) — that is the one residual risk, and it is checked, not assumed.

**Style / structure → [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)** via `DavidAnson/markdownlint-cli2-action`. The turnkey standard: sensible defaults, ~60 well-understood rules, first-class editor integration. It does **not** check cross-file links, so it complements lychee rather than replacing it.

**Documented fallback — [remark-validate-links](https://github.com/remarkjs/remark-validate-links) (Node).** Best-in-class for *internal* links/anchors: git-aware, offline, low false-positive, and it computes heading slugs with **github-slugger** (the exact library GitHub uses → guaranteed-accurate anchors). Its limitation is scope — it does **not** check external URLs, so adopting it would not remove the need for lychee; we would run both. Because lychee already covers internal links well and consolidates all link checking into one tool, lychee is the default and remark-validate-links is the fallback **only if** slug parity ever fails.

**Rejected:**

- *markdown-link-check* — older, HTTP-request focused, weak local/anchor validation.
- *remark-lint for style* — more flexible and would let one ecosystem cover style *and* internal links, but since lychee is needed for external URLs regardless, consolidating style on remark would not reduce the tool count, and it carries a heavier config surface.
- *static site generators* (MkDocs `--strict`, Docusaurus broken-link detection) — catch broken internal links, but only after restructuring the docs into a published site — a large, unrelated lift.

## Consequences

**Positive:**

- One tool (lychee) covers internal links, cross-file anchors, and external URLs; one tool (markdownlint-cli2) covers style. Two well-understood dependencies, no overlap.
- The offline internal check is deterministic and never flaky (no network), so it is safe to make PR-blocking.
- The online external check is isolated to a scheduled job that reports via an issue, so a third-party outage can never block a merge.

**Negative / trade-offs:**

- lychee is existence-only: it cannot flag an *ambiguous* base-slug link (a duplicate heading silently redirecting a `#slug` link). That gap is closed by convention — give any cross-referenced heading a unique name — with an optional custom rule left unbuilt. See [`markdown-validation.md`](../reference/markdown-validation.md).
- The GitHub-slugger parity is empirical, not guaranteed; the remark-validate-links fallback exists precisely for the day it breaks.
