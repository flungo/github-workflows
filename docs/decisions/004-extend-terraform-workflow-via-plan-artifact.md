# ADR-004: Extend the Terraform workflow via a published plan artifact

Date: 2026-07-24
Status: Accepted

## Context

Consumers call `terraform.yml` as a reusable workflow. Some need behaviour that runs
*after* the plan — for example `terraform-github` surfaces the settings of any
pre-existing classic branch protection that blocks its ruleset guard, reading them
out of the failed plan.

A job that `uses:` a reusable workflow **cannot add steps to it** — reusable workflows
compose at the *job* level, not the *step* level (and `uses:` cannot be templated with
an input, so a "pass your action in" hook isn't possible natively). The ways to graft
on post-plan behaviour are therefore:

- **Fork / duplicate** the workflow in the consumer — the copy silently drifts from
  the canonical one, which is the exact failure this repo exists to prevent.
- **Decompose** the workflow into composite actions the consumer re-orchestrates —
  powerful (step-level composition) but the consumer re-owns the sequence, so it
  drifts from any step later added here.
- **A command-hook input** (`post-plan-run: <shell>`, run via `run:`) — keeps
  orchestration here, but is stringly-typed and awkward for secrets and real scripts.
- **Expose the plan** so a *separate* consumer job can consume it.

## Decision

The workflow **publishes its plan as an artifact** — `plan.jsonl` (the `-json`
stream, **including the JSON diagnostics from a failed plan**) and `plan.txt` (the
human plan, present only on success) — named by the `plan-artifact-name` input
(default `terraform-plan`), uploaded on success and failure alike.

Consumers extend it with a **separate job** that `needs:` the caller's Terraform job,
gates on its `result` (available even on failure), and downloads the artifact. The
artifact is the entire contract between the workflow and the extension; the workflow
remains the single source of the plan sequence.

## Consequences

**Positive:**

- No duplication of the plan sequence — the workflow stays canonical, and the
  extension consumes its output rather than re-implementing it.
- Low drift: the contract is the artifact's shape, not the orchestration, so steps
  added or reordered here don't ripple into consumers' follow-on jobs.
- Additive and provider-agnostic — no consumer-specific concern leaks into the shared
  workflow, and it ships on `v1` with no major bump (per [ADR-003](003-version-via-moving-v1-branch.md)).
- The artifact doubles as a debugging aid: any run's plan can be downloaded, including
  a failed one.

**Negative / trade-offs:**

- Extensions can only run before/after the *whole* called job, not mid-sequence. Fine
  for post-plan hooks; a consumer that ever needs to interleave a step mid-plan would
  still need the composite-action decomposition.
- Every consumer pays a small per-run artifact upload, and the extension pays a runner
  plus an artifact download.
