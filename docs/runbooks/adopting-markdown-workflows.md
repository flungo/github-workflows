# Adopting the Markdown workflows

How any repo with Markdown calls `markdown-lint.yml` and `markdown-links.yml`. Pin `@v1`. These are **not** Terraform-specific — most `flungo` repos with a `docs/` tree should adopt them. See [`markdown-validation.md`](../reference/markdown-validation.md) for what they do.

## `markdown-lint.yml`

No inputs or secrets. The caller owns the triggers, path filters, and `.markdownlint-cli2.jsonc`.

```yaml
name: Markdown lint
on:
  pull_request: { paths: ['**/*.md', '.markdownlint-cli2.jsonc', '.github/workflows/markdown-lint.yml'] }
  push: { branches: [main], paths: ['**/*.md', '.markdownlint-cli2.jsonc', '.github/workflows/markdown-lint.yml'] }
jobs:
  lint:
    uses: flungo/github-workflows/.github/workflows/markdown-lint.yml@v1
```

## `markdown-links.yml`

The internal (blocking) job runs on `pull_request`/`push`; the external (issue-reporting) job runs on `schedule`/`workflow_dispatch`. The caller owns all four triggers and supplies `LYCHEE_GITHUB_TOKEN` for the external job, and keeps its own `.lycheeignore`.

```yaml
name: Markdown links
on:
  pull_request: { paths: ['**/*.md', '.github/workflows/markdown-links.yml', .lycheeignore] }
  push: { branches: [main], paths: ['**/*.md', '.github/workflows/markdown-links.yml', .lycheeignore] }
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:
jobs:
  links:
    uses: flungo/github-workflows/.github/workflows/markdown-links.yml@v1
    secrets:
      LYCHEE_GITHUB_TOKEN: ${{ secrets.LYCHEE_GITHUB_TOKEN }}
```

## Per-repo config

- Keep a repo-specific **`.markdownlint-cli2.jsonc`** (markdownlint rules) and **`.lycheeignore`** (URLs that legitimately 403/404 while unauthenticated — regenerate per repo, don't copy).
- Set the **`LYCHEE_GITHUB_TOKEN`** secret (a namespaced PAT, ideally an account/org secret) so the external sweep can reach other private repos.
