#!/usr/bin/env bash
# Build the title and body of the version-check migration issue.
#
# Split out of version-check.yml so the one piece of real logic here — working
# out which upgrade-guide sections lie between the major a consumer pins and the
# current one — is unit-testable without a second major existing. See ADR-013.
#
# Reads from the environment, writes `title` and `body` to $GITHUB_OUTPUT.
# Empty STALE_JSON is not an error: it is the up-to-date case, and both outputs
# come back empty so the caller can branch on that.
set -euo pipefail

: "${GITHUB_OUTPUT:?GITHUB_OUTPUT must be set}"

STALE_JSON=${STALE_JSON:-'[]'}
LATEST=${LATEST:?LATEST must be set}
PRODUCER=${PRODUCER:?PRODUCER must be set}
GUIDE_URL=${GUIDE_URL:?GUIDE_URL must be set}
MARKER=${MARKER:?MARKER must be set}

fail() { echo "::error::version-check-issue: $1"; exit 1; }

[[ $LATEST =~ ^[0-9]+$ ]] || fail "LATEST must be a whole number, got '$LATEST'"

echo "$STALE_JSON" | jq -e 'type == "array"' >/dev/null 2>&1 \
  || fail "STALE_JSON must be a JSON array, got '$STALE_JSON'"

# Each entry is {"major": <int>, "files": [<string>, ...]}. Validate rather than
# trusting the caller: a malformed entry here would otherwise surface as a
# nonsense issue body in someone else's repository.
echo "$STALE_JSON" | jq -e '
  all(.[];
    (.major | type == "number" and . == floor and . >= 0)
    and (.files | type == "array" and length > 0 and all(.[]; type == "string"))
  )' >/dev/null 2>&1 || fail "each STALE_JSON entry needs an integer .major and a non-empty .files array of strings"

emit() {
  local name=$1
  local value=$2
  local delim="VERSION_CHECK_ISSUE_${name}"
  printf '%s<<%s\n%s\n%s\n' "$name" "$delim" "$value" "$delim" >>"$GITHUB_OUTPUT"
}

# The marker is echoed back on every path, including the up-to-date one: this
# action embeds it in the body, so it is the one place that knows which string
# the caller must search for to find the issue again. Two copies that must agree
# is a silent duplicate-issue bug waiting to happen.
emit marker "$MARKER"

count=$(echo "$STALE_JSON" | jq 'length')
if [ "$count" -eq 0 ]; then
  emit title ''
  emit body ''
  exit 0
fi

lowest=$(echo "$STALE_JSON" | jq 'map(.major) | min')
[ "$lowest" -lt "$LATEST" ] \
  || fail "every pinned major ($lowest) is already at or beyond the latest ($LATEST) — nothing is stale, so STALE_JSON should have been empty"

repo_name=${PRODUCER##*/}

# One bullet per frozen pin, naming the files that carry it.
pins=$(echo "$STALE_JSON" | jq -r --arg latest "$LATEST" '
  sort_by(.major)[]
  | "- `@v\(.major)` (frozen) in " + (.files | sort | map("`\(.)`") | join(", "))
    + " → migrate to `@v\($latest)`"')

# The upgrade guide has one section per major, and each assumes arrival from the
# major before it — so a consumer spanning several needs every section between
# its oldest pin and the current major, in ascending order, not just the last.
sections=""
for (( major = lowest + 1; major <= LATEST; major++ )); do
  sections+="- [\`v${major}\`](${GUIDE_URL}#v${major})"$'\n'
done
sections=${sections%$'\n'}

body=$(cat <<EOF
$MARKER
\`$PRODUCER\` has published **v$LATEST**, but this repo still pins an older, now-frozen major:

$pins

A frozen major receives no further updates.

## What to do

Work through these upgrade guide sections **in order** — each assumes you are coming from the major before it:

$sections

Then bump the caller \`uses: …@vN\` refs to \`@v$LATEST\`.

_Raised by the opt-in \`version-check\` job; it closes this issue automatically once every ref is on the latest major._
EOF
)

emit title "Pinned $repo_name major is frozen — v$LATEST available"
emit body "$body"
