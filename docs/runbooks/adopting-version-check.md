# Adopting the version check

**Highly recommended for every consumer** — most of all when adopting your *first* `github-workflows` workflow, or in a repo that adopted one before this check existed. Once a repo pins `@vN`, a later major bump (a new `v<N+1>` branch) **freezes** the old major; this check is what stops the repo silently lagging on a release that no longer receives updates.

It is opt-in and needs **no credential**. Running in your repo's context, it reads the majors you pin from your own workflow files, compares them to the latest major published in `flungo/github-workflows`, and opens — then auto-closes — a single migration issue in **your** repo when you're on a now-frozen major. Rationale: [ADR-004](../decisions/004-version-check-opt-in.md); how it fits releases: [`releasing.md` § Tracking consumer migration](releasing.md#tracking-consumer-migration).

Add one scheduled caller:

```yaml
name: github-workflows version check
on:
  schedule:
    - cron: '0 7 * * 1'   # weekly
  workflow_dispatch:
jobs:
  version-check:
    permissions:
      contents: read
      issues: write
    uses: flungo/github-workflows/.github/workflows/version-check.yml@v1
```

**The issue arrives about a week after a major is cut, not the same day.** A new major gets a 7-day grace period in which its contract can still change and nobody is prompted onto it, so the check compares your pins against the newest major that has come *out* of grace — see [ADR-014](../decisions/014-grace-period-before-prompting-a-new-major.md) and [`releasing.md` § The grace period](releasing.md#the-grace-period). If you know a major was just cut and no issue has appeared, that is the check working. Note that your old major stops receiving updates at the cut, so migrating during the window is fine — you are then adopting a contract that may still be corrected in place.

**The `permissions:` block is required** — the check upserts an issue in your repo, so the caller must grant `issues: write` (a reusable workflow's `permissions:` only cap the token). It reads this public repo's majors with the same repo-scoped token, so nothing else is needed.

The reusable job is named **github-workflows version check**, so it reads unambiguously in your repo's checks list — it's a check of *this* upstream repo's version, nothing else.
