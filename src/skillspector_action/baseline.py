from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def message_hash(message: str) -> str:
    normalized = " ".join(str(message).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def filter_baselined_findings(
    findings: list[dict[str, Any]],
    baseline_path: Path | str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries = _load_entries(baseline_path)
    if not entries:
        return findings, []

    active: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for finding in findings:
        if _matches_any(finding, entries):
            suppressed.append(finding)
        else:
            active.append(finding)
    return active, suppressed


def is_baselined_finding(finding: dict[str, Any], baseline_path: Path | str | None) -> bool:
    entries = _load_entries(baseline_path)
    return bool(entries) and _matches_any(finding, entries)


def _load_entries(baseline_path: Path | str | None) -> list[dict[str, str]]:
    if not baseline_path:
        return []
    path = Path(baseline_path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("findings", [])
    return [entry for entry in entries if isinstance(entry, dict)]


def _matches_any(finding: dict[str, Any], entries: list[dict[str, str]]) -> bool:
    rule_id = _finding_rule_id(finding)
    path = _normalize_path(_finding_path(finding))
    digest = message_hash(_finding_message(finding))
    for entry in entries:
        entry_hash = str(entry.get("message_hash", ""))
        if (
            rule_id == str(entry.get("rule_id", ""))
            and path == _normalize_path(str(entry.get("path", "")))
            and entry_hash
            and digest.startswith(entry_hash)
        ):
            return True
    return False


def _finding_rule_id(finding: dict[str, Any]) -> str:
    return str(finding.get("rule_id") or finding.get("ruleId") or finding.get("rule") or "")


def _finding_message(finding: dict[str, Any]) -> str:
    return str(finding.get("message") or finding.get("description") or finding.get("text") or "")


def _finding_path(finding: dict[str, Any]) -> str:
    if finding.get("path"):
        return str(finding["path"])
    location = finding.get("location")
    if isinstance(location, dict) and location.get("path"):
        return str(location["path"])
    locations = finding.get("locations")
    if isinstance(locations, list) and locations:
        physical = locations[0].get("physicalLocation", {}) if isinstance(locations[0], dict) else {}
        artifact = physical.get("artifactLocation", {}) if isinstance(physical, dict) else {}
        uri = artifact.get("uri") if isinstance(artifact, dict) else None
        if uri:
            return str(uri)
    return ""


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")
