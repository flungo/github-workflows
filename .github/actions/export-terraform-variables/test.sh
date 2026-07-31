#!/usr/bin/env bash
# Colocated tests for export.sh, run by this action's job in action-tests.yml
# (and runnable locally). Behaviour-level only: the action.yml input wiring is
# exercised by the static `uses:` step in that job, which cannot be generated
# per-action. Every value below is fake and exists only for the test.
set -euo pipefail
cd "$(dirname "$0")"

script=./export.sh

expect_success() {
  local desc=$1; shift
  if ! env "$@" "$script" >/dev/null; then
    echo "::error::expected the export to succeed on: $desc"; exit 1
  fi
}

expect_failure() {
  local desc=$1; shift
  if env GITHUB_ENV=/dev/null VAR_NAME= PROVIDER_TOKEN= "$@" "$script" >/dev/null 2>&1; then
    echo "::error::expected the export to fail on: $desc"; exit 1
  fi
}

# Happy path: all three sources land in GITHUB_ENV, multi-line value intact.
envfile="$(mktemp)"
expect_success "happy path" \
  GITHUB_ENV="$envfile" \
  VAR_NAME=TF_VAR_provider_credential \
  PROVIDER_TOKEN=fake-provider-credential \
  TF_SECRET_VARS_JSON='{"db_password": "fake-password\nwith-a-second-line"}'

assert_line() {
  local desc=$1 pattern=$2
  grep -q "$pattern" "$envfile" || { echo "::error::missing in GITHUB_ENV ($desc)"; exit 1; }
}
assert_line "provider token"    '^TF_VAR_provider_credential=fake-provider-credential$'
assert_line "secret var"        '^TF_VAR_db_password<<'
assert_line "secret var line 1" '^fake-password$'
assert_line "secret var line 2" '^with-a-second-line$'
rm -f "$envfile"

# Nothing provided is a no-op, not an error.
expect_success "no inputs" GITHUB_ENV=/dev/null VAR_NAME= PROVIDER_TOKEN=

# Fail-loud paths.
expect_failure "invalid tf_secret_vars JSON" TF_SECRET_VARS_JSON='not json'
expect_failure "non-variable key"            TF_SECRET_VARS_JSON='{"bad-key": "fake-value"}'
expect_failure "empty secret value"          TF_SECRET_VARS_JSON='{"some_var": ""}'

echo "export-terraform-variables: all tests passed"
