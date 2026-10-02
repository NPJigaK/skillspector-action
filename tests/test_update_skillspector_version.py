import base64
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "update_skillspector_version", SCRIPTS / "update-skillspector-version.py"
)
assert SPEC is not None and SPEC.loader is not None
UPDATER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = UPDATER
SPEC.loader.exec_module(UPDATER)

SkillSpectorPin = UPDATER.SkillSpectorPin
latest_release = UPDATER.latest_release
resolve_pin = UPDATER.resolve_pin
update_files = UPDATER.update_files


class FakeGitHubClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.paths: list[str] = []

    def get_json(self, path: str) -> Any:
        self.paths.append(path)
        return self.responses[path]


def _upstream_responses() -> dict[str, Any]:
    release_tag = "v2.13.0"
    annotated_tag_sha = "a" * 40
    commit_sha = "b" * 40
    pyproject = "[project]\nname = 'skillspector'\nversion = '2.13.0'\n"
    encoded_pyproject = base64.b64encode(pyproject.encode("utf-8")).decode("ascii")
    return {
        "/repos/NVIDIA/SkillSpector/releases/latest": {
            "tag_name": release_tag,
            "published_at": "2026-02-01T00:00:00Z",
            "created_at": "2026-02-01T00:00:00Z",
            "draft": False,
            "prerelease": False,
            "html_url": f"https://github.com/NVIDIA/SkillSpector/releases/tag/{release_tag}",
            "id": 2,
        },
        f"/repos/NVIDIA/SkillSpector/git/ref/tags/{release_tag}": {
            "object": {"type": "tag", "sha": annotated_tag_sha}
        },
        f"/repos/NVIDIA/SkillSpector/git/tags/{annotated_tag_sha}": {
            "object": {"type": "commit", "sha": commit_sha}
        },
        f"/repos/NVIDIA/SkillSpector/contents/pyproject.toml?ref={release_tag}": {
            "encoding": "base64",
            "content": encoded_pyproject,
        },
    }


def test_resolve_pin_uses_github_latest_and_peels_annotated_tag() -> None:
    client = FakeGitHubClient(_upstream_responses())

    pin = resolve_pin(client)

    assert pin.tag == "v2.13.0"
    assert pin.version == "2.13.0"
    assert pin.sha == "b" * 40
    assert pin.prerelease is False
    assert "/repos/NVIDIA/SkillSpector/releases/latest" in client.paths


def test_latest_release_rejects_unexpected_prerelease() -> None:
    client = FakeGitHubClient(_upstream_responses())
    client.responses["/repos/NVIDIA/SkillSpector/releases/latest"]["prerelease"] = True

    with pytest.raises(UPDATER.UpdateError, match="unexpectedly draft or prerelease"):
        latest_release(client)


def test_replace_once_rejects_ambiguous_matches() -> None:
    with pytest.raises(UPDATER.UpdateError, match="exactly one test value"):
        UPDATER._replace_once(
            "value=one\nvalue=two\n",
            r"^value=.*$",
            "value=updated",
            "test value",
        )


def test_update_files_updates_pin_badge_sha_and_tests_idempotently(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12-slim-bookworm\n"
        "ARG SKILLSPECTOR_VERSION=2.12.0\n"
        "ARG SKILLSPECTOR_REF=" + "c" * 40 + "\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "[![Bundled SkillSpector](https://img.shields.io/badge/bundled%20SkillSpector-v2.12.0-76B900?logo=nvidia&logoColor=white)](https://github.com/NVIDIA/SkillSpector/releases/tag/v2.12.0)\n"
        "The runtime image currently bundles SkillSpector **v2.12.0**, pinned to its full upstream commit for reproducible builds. Compare the badges.\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_workflows.py").write_text(
        'PINNED_SKILLSPECTOR_VERSION = "2.12.0"\n'
        'PINNED_SKILLSPECTOR_REF = "' + "c" * 40 + '"\n\n\n'
        "def test_placeholder() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_readme.py").write_text(
        '    assert "bundled%20SkillSpector-v2.12.0" in readme\n'
        f'    assert "{"c" * 40}" in readme\n',
        encoding="utf-8",
    )
    pin = SkillSpectorPin(
        tag="v2.13.0",
        version="2.13.0",
        sha="b" * 40,
        release_url="https://github.com/NVIDIA/SkillSpector/releases/tag/v2.13.0",
        prerelease=False,
    )

    assert update_files(tmp_path, pin) is True
    assert update_files(tmp_path, pin) is False

    dockerfile = (tmp_path / "Dockerfile").read_text(encoding="utf-8")
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    workflow_tests = (tmp_path / "tests" / "test_workflows.py").read_text(encoding="utf-8")
    readme_tests = (tmp_path / "tests" / "test_readme.py").read_text(encoding="utf-8")
    assert "ARG SKILLSPECTOR_VERSION=2.13.0" in dockerfile
    assert f"ARG SKILLSPECTOR_REF={'b' * 40}" in dockerfile
    assert "bundled%20SkillSpector-v2.13.0" in readme
    assert "releases/tag/v2.13.0" in readme
    assert f"[`{'b' * 40}`]" in readme
    assert 'PINNED_SKILLSPECTOR_VERSION = "2.13.0"' in workflow_tests
    assert f'PINNED_SKILLSPECTOR_REF = "{'b' * 40}"' in workflow_tests
    assert f'PINNED_SKILLSPECTOR_REF = "{'b' * 40}"\n\n\ndef test_placeholder' in workflow_tests
    assert 'bundled%20SkillSpector-v2.13.0' in readme_tests
    assert f'assert "{"b" * 40}" in readme' in readme_tests


def test_update_workflow_is_scheduled_manual_canonical_and_sha_pinned() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "update-skillspector.yml").read_text(
        encoding="utf-8"
    )
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: write" in workflow
    assert "pull-requests: write" in workflow
    assert "github.repository == 'NPJigaK/skillspector-action'" in workflow
    assert "persist-credentials: false" in workflow
    assert "branch: automation/update-skillspector" in workflow
    assert "delete-branch: false" in workflow
    assert "python -m pytest -q" in workflow
    assert "docker build -t skillspector-action:update-test ." in workflow
    assert "scripts/smoke-test-image.sh skillspector-action:update-test" in workflow
    action_refs = re.findall(r"^\s+uses:\s+[^@\s]+@([0-9a-f]+)", workflow, flags=re.MULTILINE)
    assert action_refs
    assert all(len(ref) == 40 for ref in action_refs)
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)


@pytest.mark.parametrize("bad_version", ["../2.0.0", "2.0.0\nrun: evil", ""])
def test_fixture_versions_cannot_become_shell_or_output_injection(bad_version: str) -> None:
    # This documents the contract enforced before a package version is placed
    # into Dockerfile, README, and the PR title/output.
    assert UPDATER.VERSION_PATTERN.fullmatch(bad_version) is None
