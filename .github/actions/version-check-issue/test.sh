#!/usr/bin/env bash
# Colocated tests for build.sh, run by this action's job in action-tests.yml
# (and runnable locally). Behaviour-level only: the action.yml input wiring is
# exercised by the static `uses:` step in that job.
#
# The point of these is the section span — which upgrade guide sections lie
# between a consumer's oldest pin and the current major. Every case supplies
# both majors as inputs, so none of it depends on a second major actually
# existing. Every value below is fake and exists only for the test.
set -euo pipefail
cd "$(dirname "$0")"

script=./build.sh
guide=https://example.invalid/upgrading.md

out=""

run() {
  local desc=$1; shift
  out="$(mktemp)"
  if ! env GITHUB_OUTPUT="$out" \
      PRODUCER=flungo/github-workflows \
      GUIDE_URL="$guide" \
      MARKER='<!-- marker -->' \
      "$@" "$script" >/dev/null; then
    echo "::error::expected success on: $desc"; exit 1
  fi
}

expect_failure() {
  local desc=$1; shift
  if env GITHUB_OUTPUT=/dev/null \
      PRODUCER=flungo/github-workflows \
      GUIDE_URL="$guide" \
      MARKER='<!-- marker -->' \
      "$@" "$script" >/dev/null 2>&1; then
    echo "::error::expected failure on: $desc"; exit 1
  fi
}

has() {
  local desc=$1 pattern=$2
  grep -qF -- "$pattern" "$out" || { echo "::error::missing ($desc): $pattern"; exit 1; }
}

hasnt() {
  local desc=$1 pattern=$2
  grep -qF -- "$pattern" "$out" && { echo "::error::unexpected ($desc): $pattern"; exit 1; }
  return 0
}

# --- multi-major span: v1 pinned, v3 current -> sections v2 then v3, in order.
run "multi-major span" STALE_JSON='[{"major":1,"files":["terraform.yml"]}]' LATEST=3
has "v2 section link" "- [\`v2\`]($guide#v2)"
has "v3 section link" "- [\`v3\`]($guide#v3)"
hasnt "no section for the pinned major itself" "($guide#v1)"
# Ascending order matters: each section assumes arrival from the one before.
v2_line=$(grep -n "#v2)" "$out" | head -1 | cut -d: -f1)
v3_line=$(grep -n "#v3)" "$out" | head -1 | cut -d: -f1)
[ "$v2_line" -lt "$v3_line" ] || { echo "::error::sections are not in ascending order"; exit 1; }

# --- single hop: v1 pinned, v2 current -> only v2.
run "single hop" STALE_JSON='[{"major":1,"files":["markdown-lint.yml"]}]' LATEST=2
has "v2 section link" "- [\`v2\`]($guide#v2)"
hasnt "no v3 section" "#v3)"
has "names the pinning file" '`markdown-lint.yml`'
has "title" 'Pinned github-workflows major is frozen — v2 available'

# --- the marker is echoed back, so the caller never keeps its own copy. It is
#     also needed on the up-to-date path, where the caller must still find the
#     issue in order to close it.
has "marker echoed alongside a body" '<!-- marker -->'
grep -q '^marker<<' "$out" || { echo "::error::expected a marker output"; exit 1; }

# --- already current: nothing stale -> empty outputs, not an error.
run "already current" STALE_JSON='[]' LATEST=2
grep -q '^marker<<' "$out" || { echo "::error::expected a marker output when up to date"; exit 1; }
[ ! -s "$out" ] || grep -qE '^(title|body)<<' "$out"
grep -A1 '^title<<' "$out" | sed -n '2p' | grep -q '^$' \
  || { echo "::error::expected an empty title when nothing is stale"; exit 1; }
hasnt "no sections when up to date" "$guide#"

# --- several frozen pins: the span starts from the OLDEST, so v2 is included.
run "several frozen pins" \
  STALE_JSON='[{"major":2,"files":["a.yml"]},{"major":1,"files":["b.yml"]}]' LATEST=3
has "v2 section link" "- [\`v2\`]($guide#v2)"
has "v3 section link" "- [\`v3\`]($guide#v3)"
has "lists the v1 pin" '`@v1` (frozen)'
has "lists the v2 pin" '`@v2` (frozen)'

# --- multiple files on one pin are listed together, sorted.
run "multiple files" \
  STALE_JSON='[{"major":1,"files":["z.yml","a.yml"]}]' LATEST=2
has "both files, sorted" '`a.yml`, `z.yml`'

# --- fail loud rather than emitting a nonsense issue into someone's repo.
expect_failure "non-numeric latest"    STALE_JSON='[]' LATEST=v2
expect_failure "malformed stale JSON"  STALE_JSON='not json' LATEST=2
expect_failure "stale not an array"    STALE_JSON='{"major":1}' LATEST=2
expect_failure "entry missing files"   STALE_JSON='[{"major":1}]' LATEST=2
expect_failure "entry with empty files" STALE_JSON='[{"major":1,"files":[]}]' LATEST=2
expect_failure "non-integer major"     STALE_JSON='[{"major":"one","files":["a.yml"]}]' LATEST=2
# Nothing below the latest is not "stale" — the caller should have passed [].
expect_failure "pin not actually behind" STALE_JSON='[{"major":2,"files":["a.yml"]}]' LATEST=2

echo "version-check-issue: all tests passed"
