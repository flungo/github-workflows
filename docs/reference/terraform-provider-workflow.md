# The Terraform provider CI workflow standard

The contract the `flungo` Terraform provider repositories follow by calling the **Terraform provider** reusable workflows in this repo.
Consumer `CLAUDE.md` files point here rather than restating it.
For the concrete inputs, secrets, and caller snippets, see [`adopting-terraform-provider-workflows.md`](../runbooks/adopting-terraform-provider-workflows.md); for the rationale, [ADR-006](../decisions/006-terraform-provider-ci-family.md).

## What these cover, and what stays in the consumer

A `flungo` provider is the standard HashiCorp scaffold — a Go module on the Plugin Framework, `tfplugindocs`-generated docs committed under `docs/`, and a GoReleaser publish.
That scaffold's CI is boilerplate and lives here; anything provider-specific stays in the consumer.

| Concern | Where it lives |
| --- | --- |
| Build + vet, gofmt + golangci-lint, unit tests, docs-in-sync check | `terraform-provider-test.yml` (this repo) |
| Regenerate + commit Registry docs on a branch | `terraform-provider-docs.yml` (this repo) |
| GoReleaser signed publish on a tag | `terraform-provider-release.yml` (this repo) |
| **Acceptance tests** (live backend, coverage gate, diagnostics) | **the consumer** — a local `testacc` job |
| `.goreleaser.yml`, `examples/` + `templates/`, `go.mod` (with `tfplugindocs` as a tool dependency) | the consumer |

Acceptance testing does not generalise (each provider needs its own backend), so the consumer keeps a `testacc` job in the same workflow file that calls `terraform-provider-test.yml`.
A reusable workflow composes at the **job** level, so the caller mixes the shared jobs with its own without forking — see [`adopting-terraform-provider-workflows.md` § Acceptance tests stay local](../runbooks/adopting-terraform-provider-workflows.md#acceptance-tests-stay-local).

## Workflows & triggers

| Workflow | Trigger (on the caller) | Effect |
| --- | --- | --- |
| [`terraform-provider-test.yml`](../../.github/workflows/terraform-provider-test.yml) | `pull_request`, `push` to the default branch | `build`, `lint`, `test`, and (optional) `docs` sync check |
| [`terraform-provider-docs.yml`](../../.github/workflows/terraform-provider-docs.yml) | `push` to non-default branches | regenerate docs and commit them back to the branch |
| [`terraform-provider-release.yml`](../../.github/workflows/terraform-provider-release.yml) | `push` of a `v*` tag; `workflow_dispatch` (version) | GoReleaser build + publish |

The docs model is split by design: `terraform-provider-docs.yml` regenerates and commits on feature branches (so contributors need no local Terraform), and the `docs` job in `terraform-provider-test.yml` fails the default branch if committed docs ever drift from the schema.
Both run `tfplugindocs generate` directly from the consumer's module — the provider name is derived from the repo name (the `terraform-provider-` prefix stripped; override with the `provider-name` input), and the `tfplugindocs` version is whatever the consumer pins in its `go.mod`, so the consumer needs no `make generate` target for CI.
Set `check-docs: false` on `terraform-provider-test.yml` for a provider without generated docs.

## Release & signing model

`terraform-provider-release.yml` runs GoReleaser (`release --clean`) to build the provider archives and publish them as a GitHub release; the Terraform Registry ingests that release and the OpenTofu Registry polls for it.
Signing is conditional: when the `GPG_PRIVATE_KEY` (and `PASSPHRASE`) secrets are present the checksums are GPG-signed with the key registered on the registries; when they are absent the build still runs but passes `--skip=sign`, producing an **unsigned** release suitable only for early testing — neither registry accepts it.
On `workflow_dispatch` the workflow creates and pushes the tag from the `version` input, then releases exactly that tag (`GORELEASER_CURRENT_TAG`), avoiding `git describe` picking an earlier tag that shares the commit.

## Secret model

- Provider CI needs no shared credential: build, lint, test, and the docs-sync check run on the repo-scoped `GITHUB_TOKEN`.
- `terraform-provider-docs.yml` commits back to the branch, so the caller must grant `contents: write`.
- `terraform-provider-release.yml` publishes a GitHub release (`contents: write`) and takes the optional `GPG_PRIVATE_KEY` / `PASSPHRASE` secrets; `GITHUB_TOKEN` is used for the release itself.
- Acceptance tests' backend credentials, if any, stay with the consumer's `testacc` job.

## Adoption & versioning

Consumers call each workflow with `uses: flungo/github-workflows/.github/workflows/<name>@v1` and pass their inputs/secrets — see [`adopting-terraform-provider-workflows.md`](../runbooks/adopting-terraform-provider-workflows.md).
`@v1` is a moving **branch**, not a tag ([ADR-003](../decisions/003-version-via-moving-v1-branch.md)): it advances automatically on every merge to `main`, and a breaking input/secret change cuts a new major branch (`v2`) — see [`releasing.md`](../runbooks/releasing.md).
Every provider consumer should also adopt the [version check](../runbooks/adopting-version-check.md).
