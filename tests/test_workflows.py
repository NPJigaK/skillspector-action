from pathlib import Path


PINNED_SKILLSPECTOR_VERSION = "2.12.0"
PINNED_SKILLSPECTOR_REF = "c7958a3268d9498644b22edb75d0f051bbc8cbfc"


def test_dockerfile_pins_skillspector_ref() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert f"ARG SKILLSPECTOR_VERSION={PINNED_SKILLSPECTOR_VERSION}" in dockerfile
    assert f"ARG SKILLSPECTOR_REF={PINNED_SKILLSPECTOR_REF}" in dockerfile
    assert "version('skillspector') == '${SKILLSPECTOR_VERSION}'" in dockerfile
    assert "python:3.12-slim-bookworm" in dockerfile
    assert "scripts/entrypoint.sh" in dockerfile


def test_ci_workflow_runs_tests_and_builds_image() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m pytest -q" in workflow
    assert "docker build" in workflow
    assert "scripts/smoke-test-image.sh" in workflow


def test_image_smoke_test_checks_real_scanner_policy() -> None:
    script = Path("scripts/smoke-test-image.sh").read_text(encoding="utf-8")

    assert "tests/fixtures/unsafe-skill" in script
    assert "run_scan none" in script
    assert "run_scan high" in script
    assert 'strict_status" -ne 1' in script
    assert 'skillspector_version"] == expected_version' in script


def test_publish_workflow_pushes_ghcr_tags() -> None:
    workflow = Path(".github/workflows/publish-image.yml").read_text(encoding="utf-8")

    assert "packages: write" in workflow
    assert "ghcr.io" in workflow
    assert "docker/setup-buildx-action@v4" in workflow
    assert "docker/login-action@v4" in workflow
    assert "docker/metadata-action@v6" in workflow
    assert "docker/build-push-action@v7" in workflow
    assert "type=semver,pattern={{version}}" in workflow
    assert "type=semver,pattern={{major}}" in workflow
    assert "type=semver,pattern=v{{version}}" in workflow
    assert "type=semver,pattern=v{{major}}" in workflow
    assert "type=sha,prefix=sha-,format=long" in workflow
