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
    assert "baseline" in readme
    assert "jq-cli-skill #7" in readme
    assert "unified-adversarial-review-skill #10" in readme
    assert "docs/advanced-usage.md" in readme
    assert "docs/maintainer.md" in readme


def test_readme_documents_inputs_and_outputs() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    for input_name in ["path", "changed-only", "fail-on", "min-score", "upload-sarif", "exclude", "baseline", "llm"]:
        assert f"`{input_name}`" in readme

    for output_name in ["sarif", "json", "markdown", "risk-score", "risk-severity", "findings-count", "scanned-count"]:
        assert f"`{output_name}`" in readme


def test_readme_excludes_maintainer_and_internal_runtime_details() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Release process" not in readme
    assert "ghcr.io/npjigak/skillspector-action" not in readme
    assert "`image`" not in readme
    assert "public packages" not in readme


def test_advanced_usage_doc_contains_power_user_details() -> None:
    doc = Path("docs/advanced-usage.md").read_text(encoding="utf-8")

    for text in ["baseline", "exclude", "LLM", "pin", "message_hash"]:
        assert text in doc


def test_maintainer_doc_contains_release_and_runtime_details() -> None:
    doc = Path("docs/maintainer.md").read_text(encoding="utf-8")

    for text in ["Release process", "GHCR", "ghcr.io/npjigak/skillspector-action", "sha-<commit>", "`image`"]:
        assert text in doc
