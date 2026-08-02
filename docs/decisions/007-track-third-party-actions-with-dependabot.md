# ADR-007: Track third-party actions with Dependabot

- Date: 2026-07-26
- Status: Accepted

## Context

The reusable workflows pin their third-party actions by tag — `actions/checkout`, `hashicorp/setup-terraform`, `actions/github-script`, `actions/upload-artifact`, `DavidAnson/markdownlint-cli2-action`, `lycheeverse/lychee-action`.
Nothing keeps those current, so they silently age onto deprecated runtimes: `setup-terraform@v3` and (until a recent manual bump) `download-artifact@v4` still run on Node 20.
Each lag is noticed and fixed by hand, reactively.

[ADR-001](001-centralised-reusable-workflows.md) noted a "Renovate/Dependabot follow-up", but that was about keeping *consumers* current on **this repo's own** `@vN`, and it was superseded — the moving `@v1` branch ([ADR-003](003-version-via-moving-v1-branch.md)) removed the routine bump, and the opt-in [`version-check.yml`](004-version-check-opt-in.md) surfaces a consumer stuck on a frozen major.
Neither addresses **third-party action freshness**, which is still unmanaged.

## Decision

Enable **Dependabot** (`github-actions` ecosystem) in this repo to bump the reusable workflows' third-party actions.
Because consumers pin the moving `@v1`, every merged bump reaches the whole fleet automatically — one config keeps the fleet's actions current.
Updates are grouped into a single weekly pull request.

A bump changes the reusable workflows' **internals**, not their `@v1` interface, so consumers absorb it transparently and never bump on account of an upstream action — most bumps are invisible downstream.
The one to watch is a bump that changes *behaviour* in a way that would break the `@v1` contract: the preference is then to **fix it forward** — keep the workflow compatible with the existing interface and major — rather than adapt callers or cut a new major.
See [`releasing.md` § A breaking change you didn't foresee](../runbooks/releasing.md#a-breaking-change-you-didnt-foresee).

This is deliberately scoped to *third-party* actions.
This repo's **own** `@vN` versioning stays with the moving branch + `version-check.yml`; Dependabot is not used for it — it cannot track a moving branch, and ADR-003/004 already own that concern.

Consumers that reference actions **directly** (rather than only calling `@v1`) add their own `github-actions` Dependabot config, scoped to ignore `flungo/github-workflows/*`.
That config is per-repo and small — it is **not** centralised here, because Dependabot config cannot be shared and each consumer's direct refs differ.

## Consequences

**Positive:**

- Third-party actions stay current fleet-wide from a single config, propagated by `@v1` — no manual chasing, and runtime deprecations (Node 20 → 24) are caught proactively rather than after a warning.
- The boundary is explicit: Dependabot owns third-party actions; the moving branch + `version-check.yml` own this repo's own major.

**Negative / trade-offs:**

- Recurring Dependabot PRs to review, though grouping keeps it to one weekly PR that flows through the repo's own `actionlint` + Markdown CI.
  Review watches for a bump that shifts behaviour and absorbs it behind `@v1` (fix-forward) rather than letting it break the interface.
- Consumers with direct action refs still need their own tiny config; it can't be centralised, so there is minor per-repo duplication (a ~10-line file).
