#!/usr/bin/env python3
"""Update the repository's pinned NVIDIA/SkillSpector release.

The updater follows GitHub's ``/releases/latest`` endpoint so it uses the same
release channel as the README's upstream-latest badge. A release whose notes
still call it a candidate is included when upstream publishes it as a normal
GitHub release, while releases marked with GitHub's prerelease flag are not.

The script is kept dependency-free so it can run on the GitHub-hosted runner
without installing anything.  It updates only the files that describe the
container pin and emits GitHub Actions outputs when requested.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

UPSTREAM_REPOSITORY = "NVIDIA/SkillSpector"
DEFAULT_API_BASE_URL = "https://api.github.com"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.!+_-]*$")


class UpdateError(RuntimeError):
    """An expected, user-facing updater failure."""


@dataclass(frozen=True)
class SkillSpectorPin:
    """The release metadata needed by the Dockerfile and README."""

    tag: str
    version: str
    sha: str
    release_url: str
    prerelease: bool


class GitHubClient:
    """Small GitHub API client with no third-party dependencies."""

    def __init__(self, token: str | None, api_base_url: str = DEFAULT_API_BASE_URL) -> None:
        self._token = token
        self._api_base_url = api_base_url.rstrip("/")

    def get_json(self, path: str) -> Any:
        url = f"{self._api_base_url}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "skillspector-action-updater",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            # Do not include request headers in the error: they can contain the
            # workflow token.  The response body is truncated for readability.
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except OSError:
                detail = ""
            raise UpdateError(
                f"GitHub API request failed with HTTP {exc.code} for {path}: {detail}"
            ) from exc
        except URLError as exc:
            raise UpdateError(f"GitHub API request failed for {path}: {exc.reason}") from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise UpdateError(f"GitHub API returned invalid JSON for {path}") from exc


def _repository_path(repository: str, suffix: str) -> str:
    if not re.fullmatch(r"[^/]+/[^/]+", repository):
        raise UpdateError(f"Invalid GitHub repository: {repository!r}")
    return f"/repos/{repository}{suffix}"


def latest_release(client: GitHubClient, repository: str = UPSTREAM_REPOSITORY) -> dict[str, Any]:
    """Return the release selected by GitHub as the latest stable release."""

    release = client.get_json(_repository_path(repository, "/releases/latest"))
    if not isinstance(release, dict):
        raise UpdateError("GitHub latest release response was not a JSON object")
    if release.get("draft", False) or release.get("prerelease", False):
        raise UpdateError("GitHub latest release was unexpectedly draft or prerelease")
    if not isinstance(release.get("tag_name"), str) or not release["tag_name"]:
        raise UpdateError(f"Latest release has no tag name for {repository}")
    return release


def resolve_tag_commit(
    client: GitHubClient, tag: str, repository: str = UPSTREAM_REPOSITORY
) -> str:
    """Resolve a lightweight or annotated tag to its 40-character commit SHA."""

    encoded_tag = quote(tag, safe="")
    ref = client.get_json(_repository_path(repository, f"/git/ref/tags/{encoded_tag}"))
    if not isinstance(ref, dict) or not isinstance(ref.get("object"), dict):
        raise UpdateError(f"GitHub returned an invalid tag ref for {tag!r}")

    object_info: dict[str, Any] = ref["object"]
    for _ in range(5):
        object_type = object_info.get("type")
        object_sha = object_info.get("sha")
        if object_type == "commit":
            if not isinstance(object_sha, str) or not SHA_PATTERN.fullmatch(object_sha):
                raise UpdateError(f"Tag {tag!r} resolved to an invalid commit SHA")
            return object_sha
        if object_type != "tag" or not isinstance(object_sha, str) or not SHA_PATTERN.fullmatch(object_sha):
            raise UpdateError(f"Tag {tag!r} did not resolve to a commit")

        tag_object = client.get_json(
            _repository_path(repository, f"/git/tags/{quote(object_sha, safe='')}")
        )
        if not isinstance(tag_object, dict) or not isinstance(tag_object.get("object"), dict):
            raise UpdateError(f"GitHub returned an invalid annotated tag for {tag!r}")
        object_info = tag_object["object"]

    raise UpdateError(f"Tag {tag!r} exceeded the annotated-tag resolution limit")


def package_version_at_tag(
    client: GitHubClient, tag: str, repository: str = UPSTREAM_REPOSITORY
) -> str:
    """Read ``project.version`` from the upstream pyproject at ``tag``."""

    encoded_tag = quote(tag, safe="")
    payload = client.get_json(
        _repository_path(repository, f"/contents/pyproject.toml?ref={encoded_tag}")
    )
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise UpdateError(f"GitHub did not return base64 pyproject.toml content at {tag!r}")
    content = payload.get("content")
    if not isinstance(content, str):
        raise UpdateError(f"GitHub returned no pyproject.toml content at {tag!r}")

    try:
        pyproject = base64.b64decode("".join(content.split()), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateError(f"Could not decode pyproject.toml at {tag!r}") from exc

    # tomllib is part of Python 3.11+, and the action already requires Python
    # 3.12.  Keeping parsing here avoids guessing how release-candidate tags
    # map to PEP 440 package versions.
    try:
        document = tomllib.loads(pyproject)
    except tomllib.TOMLDecodeError as exc:
        raise UpdateError(f"Could not parse pyproject.toml at {tag!r}") from exc

    project = document.get("project")
    version = project.get("version") if isinstance(project, dict) else None
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise UpdateError(f"No safe project.version found in pyproject.toml at {tag!r}")
    return version


def resolve_pin(
    client: GitHubClient, repository: str = UPSTREAM_REPOSITORY
) -> SkillSpectorPin:
    release = latest_release(client, repository)
    tag = release["tag_name"]
    if not isinstance(tag, str):  # Defensive; latest_release already checks this.
        raise UpdateError("Latest release has no tag name")
    sha = resolve_tag_commit(client, tag, repository)
    version = package_version_at_tag(client, tag, repository)
    release_url = release.get("html_url")
    if not isinstance(release_url, str) or not release_url:
        release_url = f"https://github.com/{repository}/releases/tag/{quote(tag, safe='')}"
    return SkillSpectorPin(
        tag=tag,
        version=version,
        sha=sha,
        release_url=release_url,
        prerelease=bool(release.get("prerelease", False)),
    )


def _replace_once(text: str, pattern: str, replacement: str, description: str) -> str:
    updated, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise UpdateError(f"Could not find exactly one {description} to update")
    return updated


def _write_if_changed(path: Path, original: str, updated: str) -> bool:
    if original == updated:
        return False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def update_files(repo_root: Path, pin: SkillSpectorPin) -> bool:
    """Update Dockerfile, README, and version assertions; return whether changed."""

    dockerfile_path = repo_root / "Dockerfile"
    readme_path = repo_root / "README.md"
    workflow_tests_path = repo_root / "tests" / "test_workflows.py"
    readme_tests_path = repo_root / "tests" / "test_readme.py"
    paths = (dockerfile_path, readme_path, workflow_tests_path, readme_tests_path)
    missing = [str(path.relative_to(repo_root)) for path in paths if not path.is_file()]
    if missing:
        raise UpdateError(f"Required pin files are missing: {', '.join(missing)}")

    # Build every replacement before writing any file.  A malformed or
    # unexpectedly changed repository should fail without leaving a half-
    # updated working tree behind.
    updates: list[tuple[Path, str, str]] = []

    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    dockerfile_updated = _replace_once(
        dockerfile,
        r"^ARG SKILLSPECTOR_VERSION=[^\r\n]*$",
        f"ARG SKILLSPECTOR_VERSION={pin.version}",
        "Dockerfile SkillSpector version",
    )
    dockerfile_updated = _replace_once(
        dockerfile_updated,
        r"^ARG SKILLSPECTOR_REF=[^\r\n]*$",
        f"ARG SKILLSPECTOR_REF={pin.sha}",
        "Dockerfile SkillSpector commit",
    )
    updates.append((dockerfile_path, dockerfile, dockerfile_updated))

    encoded_version = quote(f"v{pin.version}", safe=".")
    encoded_tag = quote(pin.tag, safe="")
    badge = (
        "[![Bundled SkillSpector]("
        f"https://img.shields.io/badge/bundled%20SkillSpector-{encoded_version}-76B900"
        "?logo=nvidia&logoColor=white)]"
        f"(https://github.com/{UPSTREAM_REPOSITORY}/releases/tag/{encoded_tag})"
    )
    readme = readme_path.read_text(encoding="utf-8")
    readme_updated = _replace_once(
        readme,
        r"^\[!\[Bundled SkillSpector\]\(https://img\.shields\.io/badge/bundled%20SkillSpector-[^)]+\)\]\(https://github\.com/NVIDIA/SkillSpector/releases/tag/[^)]+\)$",
        badge,
        "README bundled SkillSpector badge",
    )
    pin_sentence = (
        f"The runtime image currently bundles SkillSpector **v{pin.version}**, "
        "pinned to its full upstream commit "
        f"[`{pin.sha}`](https://github.com/{UPSTREAM_REPOSITORY}/commit/{pin.sha}) "
        "for reproducible builds."
    )
    readme_updated = _replace_once(
        readme_updated,
        r"^The runtime image currently bundles SkillSpector \*\*v[^*]+\*\*, pinned to its full upstream commit(?: \[[^\r\n]+?\]\([^)]+\))? for reproducible builds\.",
        pin_sentence,
        "README bundled SkillSpector pin sentence",
    )
    updates.append((readme_path, readme, readme_updated))

    workflow_tests = workflow_tests_path.read_text(encoding="utf-8")
    workflow_tests_updated = _replace_once(
        workflow_tests,
        r'^(PINNED_SKILLSPECTOR_VERSION[ \t]*=[ \t]*)(["\'])[^"\']+(["\'])[ \t]*$',
        rf"\g<1>\g<2>{pin.version}\g<3>",
        "test workflow pinned SkillSpector version",
    )
    workflow_tests_updated = _replace_once(
        workflow_tests_updated,
        r'^(PINNED_SKILLSPECTOR_REF[ \t]*=[ \t]*)(["\'])[^"\']+(["\'])[ \t]*$',
        rf"\g<1>\g<2>{pin.sha}\g<3>",
        "test workflow pinned SkillSpector commit",
    )
    updates.append((workflow_tests_path, workflow_tests, workflow_tests_updated))

    readme_tests = readme_tests_path.read_text(encoding="utf-8")
    readme_tests_updated = _replace_once(
        readme_tests,
        r'^([ \t]*assert[ \t]+)"bundled%20SkillSpector-v[^"]+"([ \t]+in[ \t]+readme)[ \t]*$',
        rf'\g<1>"bundled%20SkillSpector-v{pin.version}"\g<2>',
        "README badge version assertion",
    )
    readme_tests_updated = _replace_once(
        readme_tests_updated,
        r'^([ \t]*assert[ \t]+)"[0-9a-f]{40}"([ \t]+in[ \t]+readme)[ \t]*$',
        rf'\g<1>"{pin.sha}"\g<2>',
        "README pinned SkillSpector commit assertion",
    )
    updates.append((readme_tests_path, readme_tests, readme_tests_updated))

    changed = False
    for path, original, updated in updates:
        changed |= _write_if_changed(path, original, updated)
    return changed


def _write_github_output(path: str | None, pin: SkillSpectorPin, changed: bool) -> None:
    if not path:
        return
    output_path = Path(path)
    values = {
        "changed": str(changed).lower(),
        "tag": pin.tag,
        "version": pin.version,
        "sha": pin.sha,
        "release_url": pin.release_url,
        "prerelease": str(pin.prerelease).lower(),
    }
    with output_path.open("a", encoding="utf-8", newline="\n") as output:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise UpdateError(f"Refusing to write multiline GitHub output: {key}")
            output.write(f"{key}={value}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing Dockerfile, README.md, and tests/.",
    )
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="GitHub Actions output file; defaults to GITHUB_OUTPUT when set.",
    )
    parser.add_argument(
        "--github-token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="Token for the GitHub API; defaults to GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--upstream-repository",
        default=UPSTREAM_REPOSITORY,
        help=f"Upstream repository (default: {UPSTREAM_REPOSITORY}).",
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help="GitHub API base URL, primarily useful for local testing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = GitHubClient(args.github_token, args.api_base_url)
        pin = resolve_pin(client, args.upstream_repository)
        changed = update_files(args.repo_root.resolve(), pin)
        _write_github_output(args.github_output, pin, changed)
    except (OSError, UpdateError) as exc:
        print(f"update-skillspector-version: {exc}", file=sys.stderr)
        return 1

    state = "changed" if changed else "already up to date"
    candidate = " (prerelease)" if pin.prerelease else ""
    print(f"SkillSpector {pin.version} ({pin.sha}){candidate}: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
