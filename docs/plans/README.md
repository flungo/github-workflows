# Plans

One-time build or onboarding procedures with status tracking, retired (deleted) when complete. The permanent record lives in ADRs and reference docs, not the plan. Contrast [`../runbooks/`](../runbooks/) (repeatable procedures, kept indefinitely).

| Plan | Status | Summary |
| --- | --- | --- |
| [v3-cut.md](v3-cut.md) | Scoping agreed — pre-cut work not started | Scope and cut the v3 major (originally scoped as v2; deferred behind the ADR-011/012 naming cut): remove `tf-var-name`/`provider_token`, converge input/secret naming, rename `PASSPHRASE`, make `fmt` blocking, restrict dispatch-apply to the default branch; per-consumer migration paths, the mechanical cut checklist, and the frozen-major story. |
