from pathlib import Path

import yaml


def test_action_metadata_declares_inputs_outputs_and_composite_runtime() -> None:
    action = yaml.safe_load(Path("action.yml").read_text(encoding="utf-8"))

    assert action["runs"]["using"] == "composite"
    for input_name in [
        "path",
        "changed-only",
        "fail-on",
        "min-score",
        "upload-sarif",
        "exclude",
        "baseline",
        "llm",
        "artifact-name",
        "image",
    ]:
        assert input_name in action["inputs"]

    for output_name in ["sarif", "json", "markdown", "risk-score", "risk-severity", "findings-count", "scanned-count"]:
        assert output_name in action["outputs"]

    assert action["outputs"]["risk-score"]["value"] == "${{ steps.scan.outputs['risk-score'] }}"
    assert action["outputs"]["risk-severity"]["value"] == "${{ steps.scan.outputs['risk-severity'] }}"
    assert action["outputs"]["findings-count"]["value"] == "${{ steps.scan.outputs['findings-count'] }}"
    assert action["outputs"]["scanned-count"]["value"] == "${{ steps.scan.outputs['scanned-count'] }}"


def test_action_metadata_uploads_artifacts_and_sarif() -> None:
    action_text = Path("action.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@v4" in action_text
    assert "github/codeql-action/upload-sarif@v4" in action_text
    assert "docker://ghcr.io/npjigak/skillspector-action:v1" not in action_text
    assert "scripts/run-action.sh" in action_text


def test_run_action_script_resolves_sha_pinned_image() -> None:
    script = Path("scripts/run-action.sh").read_text(encoding="utf-8")

    assert "sha-${ACTION_REF}" in script
    assert '${workspace}:${workspace}:ro' in script
    assert "INPUT_LLM" in script
    assert "OPENAI_API_KEY" in script
    assert "NVIDIA_API_KEY" in script
