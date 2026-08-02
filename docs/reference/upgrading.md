# Upgrading between majors

What a consumer must **do** to move from one pinned major to the next.

One section per major, newest first. Scope is deliberately narrow — see [ADR-013](../decisions/013-per-major-upgrade-guide.md):

- **Only breaking changes appear here.** A change is breaking when it would fail an existing caller, or when it changes a check context the caller's branch protection may require ([`releasing.md`](../runbooks/releasing.md)).
- **Non-breaking changes are not recorded.** They reach every consumer automatically on the next merge to the current major, so there is nothing to do about them and nothing to look up. The commit history holds them.

**Each section assumes you are coming from the immediately preceding major.** Moving more than one major means working through each section in turn, oldest first: `v1` to `v3` is the `v2` section and then the `v3` section, in that order, not a jump straight to the last one. Sections are not written to be skipped, and a later one may depend on the earlier one having been completed.

If you are here because the [`version-check`](../runbooks/adopting-flungo-workflows.md) job opened an issue in your repository, that issue links to every section between the major you pin and the current one.

## v2

The decisions behind it: [ADR-011](../decisions/011-reusable-job-ids-are-the-check-name.md) and [ADR-012](../decisions/012-flungo-workflows-meta-workflow.md).

### What breaks

1. **Every check context changes**, except `terraform / terraform`. Reusable jobs no longer set a display `name:`, so the right-hand half of a context is now the job's ID.
2. **`version-check.yml` no longer exists.** It is `flungo-workflows.yml`, with `version-check` as a job inside it.

### What to do

**Do it all in one pull request.** Every step below changes the contexts your repository reports — the pin bump as much as the renames, because `@v2`'s jobs report different names — so there is no ordering of separate pull requests that avoids a window where a required check no longer reports. One pull request collapses that window to nothing.

In that pull request:

1. **Bump the pin** — `@v1` → `@v2` on every `uses:` line.
2. **Rename the version-check caller** — point `uses:` at `flungo-workflows.yml`, and name the calling job `flungo-workflows` ([ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md)).
3. **Rename every other calling job** to the reusable workflow's filename, if not already done.

Then, **immediately before merging**, update any required status checks that name the old contexts — in `terraform-github`'s `standard-repository` call for a managed repository, or in branch protection directly otherwise. Leaving it until then means the branch's own run has already reported the new contexts, so the requirement is satisfiable the moment it lands.

> A repository with **no** required status checks — most of the fleet today — can ignore the last step entirely and merge the pull request like any other.

### Context changes

| Workflow | `v1` context | `v2` context |
| --- | --- | --- |
| `terraform.yml` | `terraform / terraform` | `terraform / terraform` — unchanged |
| `terraform-drift.yml` | `drift / drift` | `terraform-drift / drift` |
| `markdown-lint.yml` | `lint / markdownlint` | `markdown-lint / lint` |
| `markdown-links.yml` | `links / Internal links & anchors` | `markdown-links / internal` |
| `markdown-links.yml` | `links / External URLs` | `markdown-links / external` |
| `terraform-provider-test.yml` | `ci / build`, `ci / lint`, `ci / test`, `ci / docs` | `terraform-provider-test / build`, `… / lint`, `… / test`, `… / docs` |
| `terraform-provider-docs.yml` | `docs / generate` | `terraform-provider-docs / generate` |
| `terraform-provider-release.yml` | `release / goreleaser` | `terraform-provider-release / goreleaser` |
| `version-check.yml` → `flungo-workflows.yml` | `version-check / version-check` | `flungo-workflows / version-check` |

The `v1` column assumes the caller job IDs the runbooks recommended before [ADR-010](../decisions/010-caller-job-ids-match-the-workflow-filename.md); a caller that named its job something else reports something else on the left of the slash.

## v1

The initial major. Nothing to migrate from.
