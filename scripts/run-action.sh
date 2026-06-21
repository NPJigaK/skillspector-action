#!/usr/bin/env bash
set -euo pipefail

image="${INPUT_IMAGE:-}"
if [[ -z "$image" ]]; then
  if [[ "${ACTION_REF:-}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    image="ghcr.io/npjigak/skillspector-action:sha-${ACTION_REF}"
  else
    image="ghcr.io/npjigak/skillspector-action:${ACTION_REF:-v1}"
  fi
fi

workspace="${GITHUB_WORKSPACE:-$PWD}"
output_dir="${workspace}/${INPUT_OUTPUT_DIR:-skillspector-results}"
mkdir -p "$output_dir"

docker_args=(
  run
  --rm
  -v "${workspace}:${workspace}:ro"
  -v "${output_dir}:${output_dir}"
  -w "${workspace}"
  -e GITHUB_WORKSPACE
  -e GITHUB_EVENT_NAME
  -e GITHUB_EVENT_PATH
  -e INPUT_PATH
  -e INPUT_CHANGED_ONLY
  -e INPUT_FAIL_ON
  -e INPUT_MIN_SCORE
  -e INPUT_EXCLUDE
  -e INPUT_BASELINE
  -e INPUT_LLM
  -e INPUT_OUTPUT_DIR
)

if [[ -n "${RUNNER_TEMP:-}" ]]; then
  docker_args+=(-v "${RUNNER_TEMP}:${RUNNER_TEMP}" -e RUNNER_TEMP)
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  docker_args+=(-e GITHUB_OUTPUT)
fi

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  docker_args+=(-e GITHUB_STEP_SUMMARY)
fi

if [[ "${INPUT_LLM:-false}" == "true" ]]; then
  for secret_name in OPENAI_API_KEY NVIDIA_API_KEY NGC_API_KEY; do
    if [[ -n "${!secret_name:-}" ]]; then
      docker_args+=(-e "$secret_name")
    fi
  done
fi

docker "${docker_args[@]}" "$image"
