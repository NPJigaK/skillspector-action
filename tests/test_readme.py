from pathlib import Path


def test_readme_documents_core_usage_and_security_notes() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "NPJigaK/skillspector-action@v1" in readme
    assert "permissions:" in readme
    assert "security-events: write" in readme
    assert "fail-on: none" in readme
    assert "changed-only" in readme
    assert "pull_request_target" in readme
    assert "LLM" in readme
    assert "GHCR" in readme
    assert "public packages" in readme
    assert "baseline" in readme


def test_readme_documents_inputs_and_outputs() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    for input_name in ["path", "changed-only", "fail-on", "min-score", "upload-sarif", "exclude", "baseline", "llm"]:
        assert f"`{input_name}`" in readme

    for output_name in ["sarif", "json", "markdown", "risk-score", "risk-severity", "findings-count", "scanned-count"]:
        assert f"`{output_name}`" in readme
