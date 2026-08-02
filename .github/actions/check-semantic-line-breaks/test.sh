#!/usr/bin/env bash
# Colocated tests for this action, run by its job in action-tests.yml (and
# runnable locally). Two layers:
#
#   1. test_sembr_check.py — the unit tests for the checker itself: what it
#      must flag, and the much longer list of constructs it must stay quiet
#      about. That is where the confidence in the rule lives.
#   2. run.sh — the shell that maps the action's inputs onto the checker,
#      including the exclusion of this repo's own sparse checkout (ADR-009),
#      which the unit tests cannot see. The action.yml input wiring itself is
#      exercised by the static `uses:` steps in that job.
set -euo pipefail
cd "$(dirname "$0")"

script=$PWD/run.sh
fixtures=fixtures
clean="$fixtures/clean/**/*.md"
violating="$fixtures/violations/**/*.md"

echo "--- unit tests ---"
python3 -m unittest test_sembr_check -v

echo "--- run.sh ---"

expect_success() {
  local desc=$1; shift
  if ! env "$@" "$script" >/dev/null 2>&1; then
    echo "::error::expected the check to pass on: $desc"; exit 1
  fi
}

expect_failure() {
  local desc=$1; shift
  if env "$@" "$script" >/dev/null 2>&1; then
    echo "::error::expected the check to fail on: $desc"; exit 1
  fi
}

expect_success "the conformant fixtures" GLOBS="$clean"
expect_failure "the non-conformant fixtures" GLOBS="$violating"
expect_success "an ignore covering the non-conformant fixtures" \
  GLOBS="$fixtures/**/*.md" IGNORE="$fixtures/violations"
expect_success "multiple globs and multiple ignores" \
  GLOBS="$clean
$violating" \
  IGNORE="$fixtures/violations
never-matches-anything"

# The remaining cases need a workspace of their own: an empty GLOBS must reach
# the checker as '**/*.md' rather than as "check nothing", which would pass
# vacuously — and asserting that against this repo's own tree would only hold
# until the tree is reflowed.
workspace=$(mktemp -d)
trap 'rm -rf "$workspace"' EXIT
printf 'A consumer document.\nOne sentence per line.\n' > "$workspace/README.md"
mkdir -p "$workspace/docs"
printf 'A consumer document. With two sentences on a line.\n' > "$workspace/docs/bad.md"
(
  cd "$workspace"
  expect_failure "the default glob, over a tree with a violation" GLOBS= IGNORE=
  expect_success "the default glob, once the violation is ignored" GLOBS= IGNORE=docs
)

# The sparse checkout this repo lands in a consumer's workspace must never be
# scanned as if it were the consumer's own docs (ADR-009) — and since the
# default glob reaches into dot directories, nothing else would keep it out.
checkout=$workspace/.github-workflows/.github/actions/check-semantic-line-breaks
mkdir -p "$checkout"
cp -r . "$checkout/"
rm -rf "${workspace:?}/docs"
(
  cd "$workspace"
  script=$checkout/run.sh
  expect_success "a consumer workspace containing this repo's checkout" \
    GITHUB_WORKSPACE="$workspace" GITHUB_ACTION_PATH="$checkout" GLOBS= IGNORE=
  # …and that the exclusion is what makes it pass, not an empty scan: point the
  # action somewhere else and the checkout's own violating fixtures show up.
  expect_failure "the same workspace with the exclusion suppressed" \
    GITHUB_WORKSPACE=/nonexistent GITHUB_ACTION_PATH="$checkout" GLOBS= IGNORE=
)

echo "check-semantic-line-breaks: all tests passed"
