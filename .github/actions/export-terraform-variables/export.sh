#!/usr/bin/env bash
# Export the caller-supplied Terraform variables as TF_VAR_* env vars.
#
# Interface (env vars, mapped from action.yml inputs):
#   VAR_NAME             env var name for the provider token (empty = no token)
#   PROVIDER_TOKEN       the provider credential, masked before export
#   TF_SECRET_VARS_JSON  JSON object of extra secret Terraform variables, each
#                        exported as a masked TF_VAR_<name>
set -eo pipefail

if [ -n "$VAR_NAME" ]; then
  echo "::add-mask::$PROVIDER_TOKEN"
  echo "$VAR_NAME=$PROVIDER_TOKEN" >> "$GITHUB_ENV"
fi

[ -z "$TF_SECRET_VARS_JSON" ] && exit 0
# tf_secret_vars is a JSON object { "<var>": "<value>", ... }; export each as
# a masked TF_VAR_<var>. Fail loudly at the point of error (invalid JSON, bad
# key, empty value) rather than letting it surface as a confusing plan later.
if ! jq -e . >/dev/null 2>&1 <<<"$TF_SECRET_VARS_JSON"; then
  echo "::error::tf_secret_vars is not valid JSON"; exit 1
fi
while read -r name; do
  if ! [[ "$name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "::error::invalid tf_secret_vars key '$name' (not a Terraform variable name)"; exit 1
  fi
  value="$(jq -r --arg k "$name" '.[$k]' <<<"$TF_SECRET_VARS_JSON")"
  if [ -z "$value" ]; then
    echo "::error::tf_secret_vars key '$name' has an empty value (is the caller's secret set?)"; exit 1
  fi
  # ::add-mask:: is line-oriented — mask each line, or a multi-line value
  # would be masked on line 1 and printed in the clear from line 2.
  while IFS= read -r line; do
    [ -n "$line" ] && echo "::add-mask::$line"
  done <<<"$value"
  # Random heredoc delimiter so a value can't terminate it early and inject
  # arbitrary entries into GITHUB_ENV.
  delim="TFVAR_EOF_$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
  {
    echo "TF_VAR_${name}<<${delim}"
    echo "$value"
    echo "${delim}"
  } >> "$GITHUB_ENV"
done < <(jq -r 'keys[]' <<<"$TF_SECRET_VARS_JSON")
