#!/usr/bin/env bash
# Export the caller-supplied Terraform variables as TF_VAR_* env vars.
#
# Interface (env vars, mapped from action.yml inputs):
#   VAR_NAME             env var name for the provider token (empty = no token)
#   PROVIDER_TOKEN       the provider credential, masked before export
#   TF_SECRET_VARS_JSON  JSON object of extra secret Terraform variables, each
#                        exported as a masked TF_VAR_<name>
#   TF_VARS_JSON         JSON object of extra non-secret Terraform variables,
#                        each exported as an unmasked TF_VAR_<name>
set -eo pipefail

# Guard against the same TF_VAR_* arriving from two sources — last-write-wins
# would silently apply one value while the other source's owner expects theirs.
declare -A exported_by

record() { # $1 = env var name, $2 = source label
  if [ -n "${exported_by[$1]:-}" ]; then
    echo "::error::$1 is set by both ${exported_by[$1]} and $2"; exit 1
  fi
  exported_by[$1]=$2
}

if [ -n "$VAR_NAME" ]; then
  record "$VAR_NAME" tf-var-name
  echo "::add-mask::$PROVIDER_TOKEN"
  echo "$VAR_NAME=$PROVIDER_TOKEN" >> "$GITHUB_ENV"
fi

export_map() { # $1 = JSON map, $2 = input label, $3 = "mask" or "plain"
  local json=$1 label=$2 masking=$3 empty_hint="" name value line delim
  [ -z "$json" ] && return 0
  [ "$masking" = mask ] && empty_hint=" (is the caller's secret set?)"
  # The map is a JSON object { "<var>": "<value>", ... }; export each entry as
  # TF_VAR_<var>. Fail loudly at the point of error (invalid JSON, bad key,
  # empty value) rather than letting it surface as a confusing plan later.
  if ! jq -e . >/dev/null 2>&1 <<<"$json"; then
    echo "::error::$label is not valid JSON"; exit 1
  fi
  while read -r name; do
    if ! [[ "$name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      echo "::error::invalid $label key '$name' (not a Terraform variable name)"; exit 1
    fi
    record "TF_VAR_${name}" "$label"
    value="$(jq -r --arg k "$name" '.[$k]' <<<"$json")"
    if [ -z "$value" ]; then
      echo "::error::$label key '$name' has an empty value$empty_hint"; exit 1
    fi
    if [ "$masking" = mask ]; then
      # ::add-mask:: is line-oriented — mask each line, or a multi-line value
      # would be masked on line 1 and printed in the clear from line 2.
      while IFS= read -r line; do
        [ -n "$line" ] && echo "::add-mask::$line"
      done <<<"$value"
    fi
    # Random heredoc delimiter so a value can't terminate it early and inject
    # arbitrary entries into GITHUB_ENV.
    delim="TFVAR_EOF_$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
    {
      echo "TF_VAR_${name}<<${delim}"
      echo "$value"
      echo "${delim}"
    } >> "$GITHUB_ENV"
  done < <(jq -r 'keys[]' <<<"$json")
}

export_map "$TF_SECRET_VARS_JSON" tf_secret_vars mask
export_map "$TF_VARS_JSON" tf_vars plain
