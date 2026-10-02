#!/usr/bin/env bash
set -euo pipefail

image="${1:-skillspector-action:test}"
workspace="${GITHUB_WORKSPACE:-$PWD}"
smoke_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/skillspector-action-smoke.XXXXXX")"
permissive_output="${smoke_root}/permissive"
strict_output="${smoke_root}/strict"
mkdir -p "$permissive_output" "$strict_output"

run_scan() {
  local fail_on="$1"
  local output_dir="$2"
  docker run --rm \
    -v "${workspace}:/workspace:ro" \
    -v "${output_dir}:/output" \
    -w /workspace \
    -e GITHUB_WORKSPACE=/workspace \
    -e INPUT_PATH=tests/fixtures/unsafe-skill \
    -e INPUT_OUTPUT_DIR=/output \
    -e INPUT_LLM=false \
    -e "INPUT_FAIL_ON=${fail_on}" \
    "$image"
}

run_scan none "$permissive_output"

set +e
run_scan high "$strict_output"
strict_status=$?
set -e
if [[ "$strict_status" -ne 1 ]]; then
  echo "Expected fail-on=high to exit 1, got ${strict_status}" >&2
  exit 1
fi

expected_version="$(sed -n 's/^ARG SKILLSPECTOR_VERSION=//p' "${workspace}/Dockerfile")"
python - "$permissive_output" "$strict_output" "$expected_version" <<'PY'
import json
import sys
from pathlib import Path

permissive_dir, strict_dir, expected_version = sys.argv[1:]
for output_dir in (Path(permissive_dir), Path(strict_dir)):
    report = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    sarif = json.loads((output_dir / "results.sarif").read_text(encoding="utf-8"))
    assert report["findings_count"] >= 1
    assert report["risk_score"] >= 1
    assert report["risk_severity"] in {"high", "critical"}
    assert report["reports"][0]["metadata"]["skillspector_version"] == expected_version
    assert sarif["runs"][0]["results"]
PY
