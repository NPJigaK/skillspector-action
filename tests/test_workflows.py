from pathlib import Path


PINNED_SKILLSPECTOR_REF = "a5092dd9b9521ff57a9b53612bb129ce78019002"


def test_dockerfile_pins_skillspector_ref() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert f"ARG SKILLSPECTOR_REF={PINNED_SKILLSPECTOR_REF}" in dockerfile
    assert "python:3.12-slim-bookworm" in dockerfile
    assert "scripts/entrypoint.sh" in dockerfile


def test_ci_workflow_runs_tests_and_builds_image() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m pytest -q" in workflow
    assert "docker build" in workflow


def test_publish_workflow_pushes_ghcr_tags() -> None:
    workflow = Path(".github/workflows/publish-image.yml").read_text(encoding="utf-8")

    assert "packages: write" in workflow
    assert "ghcr.io" in workflow
    assert "docker/login-action" in workflow
    assert "docker/build-push-action" in workflow
    assert "type=semver,pattern={{version}}" in workflow
    assert "type=semver,pattern={{major}}" in workflow
    assert "type=semver,pattern=v{{version}}" in workflow
    assert "type=semver,pattern=v{{major}}" in workflow
    assert "type=sha,prefix=sha-" in workflow
