#!/usr/bin/env bash
# Turn the action's inputs into a sembr_check.py invocation.
#
# Interface (env vars, mapped from action.yml inputs):
#   GLOBS   newline-separated globs to check (empty = the script's default)
#   IGNORE  newline-separated globs to skip
set -euo pipefail

# Set by the runner for a composite action's steps; fall back to this script's
# own directory so the tests (and a local run) can invoke it directly.
GITHUB_ACTION_PATH=${GITHUB_ACTION_PATH:-$(cd "$(dirname "$0")" && pwd)}

args=(--format github)

# When markdown-sembr.yml fetches this action it sparse-checks-out this repo
# *inside the caller's workspace* (ADR-009), so this repo's own Markdown would
# otherwise be scanned as if it were the caller's. Exclude that checkout, and
# only that checkout: stripping the action's own path suffix yields the
# checkout root, which is the workspace itself — nothing to exclude — when the
# action is used from a repo's own `./.github/actions/…` path.
suffix=/.github/actions/check-semantic-line-breaks
action_root=${GITHUB_ACTION_PATH%"$suffix"}
if [ -n "${GITHUB_WORKSPACE:-}" ] && [ "$action_root" != "$GITHUB_ACTION_PATH" ]; then
  relative=${action_root#"$GITHUB_WORKSPACE"/}
  if [ "$relative" != "$action_root" ]; then
    args+=(--ignore "$relative")
  fi
fi

while IFS= read -r pattern; do
  [ -n "$pattern" ] && args+=(--ignore "$pattern")
done <<< "${IGNORE:-}"

globs=()
while IFS= read -r pattern; do
  [ -n "$pattern" ] && globs+=("$pattern")
done <<< "${GLOBS:-}"
[ ${#globs[@]} -gt 0 ] || globs=('**/*.md')

python3 "$GITHUB_ACTION_PATH/sembr_check.py" "${args[@]}" -- "${globs[@]}"
