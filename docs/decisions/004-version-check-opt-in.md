# ADR-004: Notify consumers of a frozen major via an opt-in version-check workflow

Date: 2026-07-24
Status: Accepted

## Context

The moving-major-branch model ([ADR-003](003-version-via-moving-v1-branch.md)) delivers non-breaking fixes to consumers automatically — they pin `@v1` and follow it, with no per-consumer bump. That removes the original reason for the Renovate/Dependabot follow-up recorded in [ADR-001](001-centralised-reusable-workflows.md): there is no routine version bump to make.

One residual risk remains. When a **new major is cut** (a `v2` branch — [`releasing.md`](../runbooks/releasing.md)), the previous major freezes, and a consumer still pinning `@v1` **silently lags on a release that no longer receives updates**. Nothing surfaces that drift.

Options for closing it:

- **Dependabot** — its `github-actions` updater keys off tags/releases only; it never enumerates branches as versions and can't use a custom datasource. With no `v1` tag and `v2` existing only as a branch, it sees nothing. Not viable.
- **Renovate** — viable but per-consumer: it needs a `git-refs` datasource override and a `renovate.json` in *every* consumer, gives no fleet-wide view, and a consumer that never onboarded Renovate is invisible — the exact silent-drift gap. A major bump is also breaking, so its PR can't simply be merged.
- **Producer-side census** — one workflow here that enumerates all consumers and reports who lags. It gives a fleet rollup and catches non-adopters, but requires a credential that can read **private repos across all owners**: fine-grained PATs and GitHub App installations are each scoped to a single owner, so only a broad classic `repo`-scoped PAT spans owners — an all-your-private-repos secret we don't want to centralise. (It also has to enumerate reliably, since code search lags on fresh repos.)

## Decision

Ship a reusable **`version-check.yml`** that each consumer **opts into** on a schedule. Running in the consumer's own context, it:

1. reads the majors the consumer pins from its **own** workflow files;
2. reads the **latest** major published here (the highest `v<N>` branch — this repo is **public**, so plain read needs no credential);
3. opens — and later auto-closes — a single tracking issue **in the consumer's own repo** when it pins a now-frozen major.

**No external credential is involved:** the consumer writes the issue with its own repo-scoped `GITHUB_TOKEN` (the caller grants `issues: write`), and reads this public repo's branches with that same token. Opt-in is one small caller workflow, documented in the adoption runbooks.

**The producer-side rollup census is explicitly out of scope** — its cross-owner credential requirement (and the enumeration complications above) make it undesirable now. It stays a possible future addition for a single fleet-wide "who has migrated?" view, gated on settling a suitable identity (the same identity question as [terraform-github#13](https://github.com/flungo/terraform-github/issues/13)).

This supersedes the Renovate/Dependabot follow-up from ADR-001.

## Consequences

**Positive:**

- No credential to provision or rotate — the mechanism that would have needed a broad cross-owner token is avoided entirely.
- The notification lands **where the migration happens** (the consumer's repo) and tracks progress: the issue opens on the first scheduled run after a major is cut and closes itself once every ref is on the latest major.
- Auto-discovers the consumer's own pins from its workflow files, so it can't drift from a hand-maintained input.

**Negative / trade-offs:**

- **Opt-in means a non-adopting consumer self-reports nothing** — a residual silent-drift gap that only the (out-of-scope) producer census would close.
- **No single fleet-wide rollup** — migration state is spread across each consumer's own issues rather than one dashboard.
- Every opted-in consumer runs its own scheduled check (negligible cost, slight duplication).
