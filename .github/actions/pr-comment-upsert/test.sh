#!/usr/bin/env bash
# Colocated tests for this action, run by its job in action-tests.yml (and
# runnable locally). Two layers:
#
#   1. test_upsert.js — the unit tests for the upsert itself, driven against a
#      fake GitHub client: post, update in place, remove-when-clear, the
#      long-pull-request pagination case and the rejections. That is where the
#      confidence lives, because every one of those paths writes a comment onto
#      a pull request — so the `uses:` smoke step in action-tests.yml can only
#      take the one path that writes nothing.
#   2. A wiring check over action.yml: every declared input is mapped into the
#      step, so an input cannot be documented and then silently ignored.
set -euo pipefail
cd "$(dirname "$0")"

echo "--- unit tests ---"
node test_upsert.js

echo "--- action.yml wiring ---"
node --check upsert.js

# Input names are the two-space-indented keys of the `inputs:` block.
inputs=$(awk '/^inputs:/{in_block=1; next} /^[a-z]/{in_block=0} in_block && /^  [a-z][a-z-]*:/{gsub(/[ :]/, ""); print}' action.yml)
[ -n "$inputs" ] || { echo "::error::no inputs found in action.yml — the parser above stopped matching"; exit 1; }

for input in $inputs; do
  grep -qF "inputs.$input " action.yml || grep -qF "inputs.$input}" action.yml || {
    echo "::error::action.yml declares the '$input' input but never passes it to the step"
    exit 1
  }
done

echo "pr-comment-upsert: all tests passed"
