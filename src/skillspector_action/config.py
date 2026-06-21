from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Config:
    path: Path
    output_dir: Path
    changed_only: bool = False
    fail_on: str = "none"
    min_score: int | None = None
    excludes: list[str] = field(default_factory=list)
    baseline: Path | None = None
    llm: bool = False
    workspace: Path | None = None
    event_name: str = ""
    event_path: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, workspace: Path | None = None) -> "Config":
        source = env or os.environ
        workspace_path = Path(workspace or source.get("GITHUB_WORKSPACE", ".")).resolve()
        fail_on = source.get("INPUT_FAIL_ON", "none").strip().lower() or "none"
        if fail_on not in {"none", "high", "critical"}:
            raise ValueError("INPUT_FAIL_ON must be one of: none, high, critical")

        min_score = _optional_int(source.get("INPUT_MIN_SCORE", ""))
        baseline_value = source.get("INPUT_BASELINE", "").strip()
        event_path_value = source.get("GITHUB_EVENT_PATH", "").strip()

        return cls(
            path=_resolve_under_workspace(source.get("INPUT_PATH", "."), workspace_path),
            output_dir=_resolve_under_workspace(source.get("INPUT_OUTPUT_DIR", "skillspector-results"), workspace_path),
            changed_only=_parse_bool(source.get("INPUT_CHANGED_ONLY", "false")),
            fail_on=fail_on,
            min_score=min_score,
            excludes=_parse_list(source.get("INPUT_EXCLUDE", "")),
            baseline=_resolve_under_workspace(baseline_value, workspace_path) if baseline_value else None,
            llm=_parse_bool(source.get("INPUT_LLM", "false")),
            workspace=workspace_path,
            event_name=source.get("GITHUB_EVENT_NAME", ""),
            event_path=Path(event_path_value) if event_path_value else None,
        )


def _resolve_under_workspace(value: str, workspace: Path) -> Path:
    path = Path(value or ".")
    return path if path.is_absolute() else workspace / path


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_list(value: str) -> list[str]:
    parts = []
    for chunk in value.replace(",", "\n").splitlines():
        item = chunk.strip()
        if item:
            parts.append(item)
    return parts


def _optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None
