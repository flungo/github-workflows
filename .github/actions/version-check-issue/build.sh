#!/usr/bin/env bash
# Build the title and body of the version-check migration issue.
#
# Split out of flungo-workflows.yml so the one piece of real logic here — working
# out which upgrade-guide sections lie between the major a consumer pins and the
# one it should move to — is unit-testable without a second major existing. See
# ADR-013.
#
# That destination is TARGET, the producer's current *stable* major, which is
# not always the newest published: a major that is cut but still settling is
# SETTLING, gets no section span, and is named only to explain itself (ADR-014).
#
# Reads from the environment, writes `title` and `body` to $GITHUB_OUTPUT.
# Empty STALE_JSON is not an error: it is the up-to-date case, and both outputs
# come back empty so the caller can branch on that.
set -euo pipefail

: "${GITHUB_OUTPUT:?GITHUB_OUTPUT must be set}"

STALE_JSON=${STALE_JSON:-'[]'}
TARGET=${TARGET:?TARGET must be set}
SETTLING=${SETTLING:-}
PRODUCER=${PRODUCER:?PRODUCER must be set}
GUIDE_PATH=${GUIDE_PATH:?GUIDE_PATH must be set}
MARKER=${MARKER:?MARKER must be set}

fail() { echo "::error::version-check-issue: $1"; exit 1; }

[[ $TARGET =~ ^[0-9]+$ ]] || fail "TARGET must be a whole number, got '$TARGET'"
[[ -z $SETTLING || $SETTLING =~ ^[0-9]+$ ]] || fail "SETTLING must be empty or a whole number, got '$SETTLING'"
[[ -z $SETTLING || $SETTLING -gt $TARGET ]] || fail "SETTLING ($SETTLING) must be newer than TARGET ($TARGET)"

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
[ "$lowest" -lt "$TARGET" ] \
  || fail "every pinned major ($lowest) is already at or beyond the stable one ($TARGET) — nothing is stale, so STALE_JSON should have been empty"

repo_name=${PRODUCER##*/}

# One bullet per frozen pin, naming the files that carry it.
pins=$(echo "$STALE_JSON" | jq -r --arg target "$TARGET" '
  sort_by(.major)[]
  | "- `@v\(.major)` (frozen) in " + (.files | sort | map("`\(.)`") | join(", "))
    + " → migrate to `@v\($target)`"')

# The upgrade guide has one section per major, and each assumes arrival from the
# major before it — so a consumer spanning several needs every section between
# its oldest pin and the target, in ascending order, not just the last. A
# settling major has no section to work through yet: it is not a destination.
#
# Each link is pinned to its OWN major's branch rather than to main. A section
# describes a hop, and the docs it links onward to — runbooks, ADRs, workflow
# files — are resolved by GitHub against the same ref, so pinning hands the
# reader the repository as it stood for the version they are moving to. On main
# those same relative links render whatever is true today, which for a consumer
# several majors behind is a repository they have not reached yet.
sections=""
for (( major = lowest + 1; major <= TARGET; major++ )); do
  sections+="- [\`v${major}\`](https://github.com/${PRODUCER}/blob/v${major}/${GUIDE_PATH}#v${major})"$'\n'
done
sections=${sections%$'\n'}

# A newer major exists but is not yet somewhere to go. Said here rather than
# left out, because the consumer can see that branch on GitHub and would
# otherwise read this issue as out of date.
settling_note=""
if [ -n "$SETTLING" ]; then
  settling_note="
\`v$SETTLING\` has also been published, but it is still settling — its contract can change in place until it is promoted, so \`@v$TARGET\` is where to go for now.
This issue moves on to \`@v$SETTLING\` once that happens.
"
fi

body=$(cat <<EOF
$MARKER
\`$PRODUCER\` has published **v$TARGET**, but this repo still pins an older, now-frozen major:

$pins

A frozen major receives no further updates.
$settling_note
## What to do

Work through these upgrade guide sections **in order** — each assumes you are coming from the major before it:

$sections

Then bump the caller \`uses: …@vN\` refs to \`@v$TARGET\`.

_Raised by the opt-in \`version-check\` job; it closes this issue automatically once no ref is on a frozen major._
EOF
)

emit title "Pinned $repo_name major is frozen — v$TARGET available"
emit body "$body"
