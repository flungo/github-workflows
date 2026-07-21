# The Markdown validation standard

Two reusable workflows that validate Markdown. They are **not Terraform-specific** — any repo with a `docs/` tree (or Markdown anywhere) can adopt them, and most `flungo` repos should. For caller snippets, see [`adopting-markdown-workflows.md`](../runbooks/adopting-markdown-workflows.md).

## Workflows

- [`markdown-lint.yml`](../../.github/workflows/markdown-lint.yml) — `markdownlint-cli2` style/structure linting. Rules live in the caller's `.markdownlint-cli2.jsonc`. Does not check cross-file links.
- [`markdown-links.yml`](../../.github/workflows/markdown-links.yml) — link validation in two jobs, each self-selecting on the caller's event:
  - **internal** — an offline check of relative links and heading anchors. Blocking, on every PR/push; deterministic, no network. It scans the whole tree, so a rename that breaks a link in an untouched file is still caught.
  - **external** — an online sweep of external URLs. Scheduled/dispatch only (never on a PR, so a flaky outage can't block a merge); reports breakage via a single auto-updated GitHub issue rather than failing the run.

## Per-repo config

- **`.markdownlint-cli2.jsonc`** — the caller's markdownlint rules. Start from defaults; give each override an inline justification.
- **`.lycheeignore`** — URLs that legitimately 403/404 while unauthenticated. Repo-specific — regenerate per repo, don't copy.
- **`LYCHEE_GITHUB_TOKEN`** secret — a namespaced PAT the external sweep uses to reach other (private) repos; passed via the action's `token` input, not a step-level `env: GITHUB_TOKEN`.

## Versioning

Pin `@v1`; the tag moves forward for fixes. See [`adopting-markdown-workflows.md`](../runbooks/adopting-markdown-workflows.md) for the callers.
