# ADR-018: One marker-upsert action per resource, not one shared by both

- **Date:** 2026-09-18
- **Status:** Accepted

## Context

Four workflows here independently implemented "find the thing carrying a hidden marker, then create it or update it in place".
Three of them do it to an **issue** — `flungo-workflows.yml`'s version check, `markdown-links.yml`'s external sweep, and `terraform-drift.yml` (which carried two near-identical copies of its own) — and one does it to a **pull request comment**: `terraform.yml`'s plan comment.

[#38](https://github.com/flungo/github-workflows/issues/38) called for extracting the pattern to a composite action, on the same argument [ADR-009](009-composite-action-via-workflow-identity-checkout.md) makes for `export-terraform-variables`: the copies had already diverged into bugs that existed in some and not others.
Two of them listed without pagination — `markdown-links.yml` a single page of 100 open issues, `terraform.yml` the API default of 30 comments — so a busy repository would stop finding the marker and stack a duplicate on every run, which is the one thing an upsert exists to prevent.
The question the issue left open is where the shared unit's boundary falls: does the comment upsert join the same action, stay inline, or become an action of its own?

## Decision

Extract the pattern **twice, once per resource**: `issue-upsert` and `pr-comment-upsert`, each a composite action with its own colocated tests and job in `self-action-tests.yml`.

Two separate questions, answered separately.

### Why not one action for both

The two are the same *shape* and not the same *operation*.
What they genuinely share is a listing walked to the end and an entry matched on a marker: one `paginate` call and one `find`.
Everything either side of that differs:

- An issue is a durable record of a condition, so retiring it means closing it, optionally with a comment saying why — and it stays there, closed, as the record that it happened.
  A comment has no state of its own: retiring it means deleting it, because there is nothing to leave behind.
- An issue carries a title and a label (with a colour and description to create when it is missing), and shares its listing with pull requests, which must be filtered out.
  A comment has none of that, and is addressed by its own id on a resource it belongs to.
- The issue callers hand their action a finished title and body, built by a step that exists for that (`version-check-issue`) or was added with this change.
  `terraform.yml` builds its comment from the plan's JSONL output *and* the outcomes of its own `fmt`, `validate` and `plan` steps.

A `resource: issue | comment` switch over two disjoint code paths, sharing six lines, is not one implementation — it is two behind one name, and six of the nine inputs would be dead on each call.

### Why extract the comment at all, rather than fix it where it was

Because the reason for extracting the issue upsert applies unchanged: the bug was in the copy nobody could test, and a pattern with one implementation is one that can be got right once.
The comment upsert is also a generally useful thing to have on the shelf — the next workflow that wants to keep a single marked comment current on a pull request calls the action instead of writing a fifth copy of the search.
Leaving it inline would have fixed today's pagination bug and preserved exactly the conditions that produced it.

The pair is deliberately symmetric where the resources allow: both take a `marker`, a `state` (`present` / `absent`) and a body, both prepend the marker to a body that lacks one so a caller cannot write something its own next run would duplicate, and both report an `outcome`.
They differ only where the resources do — `closed` against `deleted`, an issue's title and label against a comment's pull request number.

`pr-comment-upsert`'s `absent` path has no caller today.
It earns its place twice over: it is what makes the pair symmetric for the next caller, and it is the only path that writes nothing, which is what lets `self-action-tests.yml` exercise the action's wiring against a live token without commenting on the pull request under test.

### What stays duplicated

The paginate-and-find, about six lines, in each action.
Hoisting it would mean a shared directory under `.github/actions/`, where the `coverage` job requires every directory to be an action with an executable `test.sh` and a job of its own — a guard worth more than six deduplicated lines, and an exemption in it worth less.

## Consequences

### Positive

- Pagination, marker matching and the exclusion of pull requests from an issue listing are one implementation's problem per resource, unit-tested against a fake client: create, update in place, retire-when-clear, the past-the-first-page case and the rejections all run in `self-action-tests.yml`, where previously none of them ran anywhere.
  Every path writes into the repository it runs in, so those tests are the only place that coverage could live.
- The four callers keep no copy of any of it, and a fifth has two actions to choose between rather than a pattern to reimplement.
- Every input on each action is live for every caller: neither carries a field that is meaningless for the resource it was given.

### Negative — trade-offs

- Two actions to keep in step.
  A change to the shared idea — matching a marker case-insensitively, say — is now made twice, and the six duplicated lines are a deliberate cost recorded here rather than an oversight.
- `terraform.yml`'s plan comment becomes two steps, one building the body and one placing it, where it used to be one.
  The body is passed between them as a step output.
- `terraform-drift.yml` changed behaviour to adopt the issue action: it opened a fresh dated issue on every drifting run and closed *every* open `drift`-labelled issue on a clean one.
  It now keeps one issue per condition — one for remediated drift, one for a destroy plan awaiting review, deliberately two markers so an unreviewed destroy is never overwritten by a later remediation — and closes those two.
  A drift issue opened by an earlier version carries no marker, so a consumer adopting this has to close its historical ones by hand, once.
