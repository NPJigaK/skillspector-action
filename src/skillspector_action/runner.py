from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .baseline import filter_baselined_findings, is_baselined_finding
from .config import Config
from .discovery import discover_skill_targets, targets_for_changed_files
from .gitdiff import changed_files_from_git, fetch_ref
from .reports import highest_severity, merge_json_reports, merge_sarif_reports, normalize_severity, render_markdown_summary

Scanner = Callable[[Path, Path, bool], "ScanResult"]


@dataclass(frozen=True)
class ScanResult:
    json_report: dict[str, Any]
    sarif_report: dict[str, Any]


def run_action(config: Config, scanner: Scanner | None = None) -> int:
    scanner = scanner or run_skillspector
    config.output_dir.mkdir(parents=True, exist_ok=True)
    targets = _discover_targets(config)

    json_reports: list[dict[str, Any]] = []
    sarif_reports: list[dict[str, Any]] = []
    suppressed_findings: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="skillspector-action-") as temp:
        work_dir = Path(temp)
        for target in targets:
            result = scanner(target, work_dir, config.llm)
            report = dict(result.json_report)
            findings = _extract_findings(report)
            active, suppressed = filter_baselined_findings(findings, config.baseline)
            _replace_findings(report, active, had_original_findings=bool(findings))
            suppressed_findings.extend(suppressed)
            json_reports.append(report)
            sarif_reports.append(_filter_sarif_report(result.sarif_report, config.baseline))

    summary = merge_json_reports(json_reports, suppressed_findings=suppressed_findings)
    sarif = merge_sarif_reports(sarif_reports)
    markdown = render_markdown_summary(summary)

    json_path = config.output_dir / "results.json"
    sarif_path = config.output_dir / "results.sarif"
    markdown_path = config.output_dir / "summary.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    sarif_path.write_text(json.dumps(sarif, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(markdown, encoding="utf-8")

    _write_outputs(summary, json_path, sarif_path, markdown_path)
    _append_step_summary(markdown)

    return 1 if should_fail(summary, config.fail_on, config.min_score) else 0


def run_skillspector(target: Path, work_dir: Path, use_llm: bool) -> ScanResult:
    safe_name = str(abs(hash(target.as_posix())))
    json_path = work_dir / f"{safe_name}.json"
    sarif_path = work_dir / f"{safe_name}.sarif"

    base = ["skillspector", "scan", str(target)]
    no_llm = [] if use_llm else ["--no-llm"]
    subprocess.run([*base, *no_llm, "--format", "json", "--output", str(json_path)], check=True)
    subprocess.run([*base, *no_llm, "--format", "sarif", "--output", str(sarif_path)], check=True)

    return ScanResult(
        json_report=json.loads(json_path.read_text(encoding="utf-8")),
        sarif_report=json.loads(sarif_path.read_text(encoding="utf-8")),
    )


def should_fail(summary: dict[str, Any], fail_on: str, min_score: int | None) -> bool:
    score = int(summary.get("risk_score", 0) or 0)
    severity = normalize_severity(summary.get("risk_severity"))

    if min_score is not None and score >= min_score:
        return True
    if fail_on == "high" and severity in {"high", "critical"}:
        return True
    if fail_on == "critical" and severity == "critical":
        return True
    return False


def _discover_targets(config: Config) -> list[Path]:
    if not config.changed_only:
        return discover_skill_targets(config.path, excludes=config.excludes)

    changed_files = _changed_files_for_event(config)
    if changed_files is None:
        return discover_skill_targets(config.path, excludes=config.excludes)

    scan_relative_files = _files_relative_to_scan_root(config, changed_files)
    return targets_for_changed_files(config.path, scan_relative_files, excludes=config.excludes)


def _changed_files_for_event(config: Config) -> list[str] | None:
    if config.event_name not in {"pull_request", "pull_request_target"} or not config.event_path:
        return None
    workspace = config.workspace or Path.cwd()
    try:
        event = json.loads(config.event_path.read_text(encoding="utf-8"))
        base_sha = event["pull_request"]["base"]["sha"]
        fetch_ref(workspace, "origin", base_sha)
        return changed_files_from_git(workspace, base_sha)
    except (OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError):
        return None


def _files_relative_to_scan_root(config: Config, changed_files: list[str]) -> list[str]:
    workspace = (config.workspace or Path.cwd()).resolve()
    scan_root = config.path.resolve()
    try:
        scan_root_rel = scan_root.relative_to(workspace)
    except ValueError:
        return changed_files

    result = []
    for changed_file in changed_files:
        changed_path = Path(changed_file)
        if scan_root_rel == Path("."):
            result.append(changed_path.as_posix())
        else:
            try:
                result.append(changed_path.relative_to(scan_root_rel).as_posix())
            except ValueError:
                continue
    return result


def _extract_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("filtered_findings")
    if findings is None:
        findings = report.get("findings")
    return [finding for finding in findings or [] if isinstance(finding, dict)]


def _replace_findings(
    report: dict[str, Any],
    findings: list[dict[str, Any]],
    had_original_findings: bool = False,
) -> None:
    if "filtered_findings" in report:
        report["filtered_findings"] = findings
    else:
        report["findings"] = findings
    if had_original_findings and not findings:
        report["risk_score"] = 0
        report["risk_severity"] = "none"
    elif findings:
        report["risk_severity"] = highest_severity([finding.get("severity", "none") for finding in findings])
        scores = [_finding_score(finding) for finding in findings]
        if any(score is not None for score in scores):
            report["risk_score"] = max(score for score in scores if score is not None)


def _finding_score(finding: dict[str, Any]) -> int | None:
    value = finding.get("risk_score", finding.get("score"))
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _filter_sarif_report(report: dict[str, Any], baseline_path: Path | None) -> dict[str, Any]:
    if not baseline_path:
        return report
    filtered = json.loads(json.dumps(report))
    for run in filtered.get("runs", []):
        run["results"] = [
            result
            for result in run.get("results", [])
            if not is_baselined_finding(_finding_from_sarif_result(result), baseline_path)
        ]
    return filtered


def _finding_from_sarif_result(result: dict[str, Any]) -> dict[str, Any]:
    message = result.get("message", {})
    text = message.get("text", "") if isinstance(message, dict) else ""
    return {
        "rule_id": result.get("ruleId", ""),
        "message": text,
        "path": _sarif_result_path(result),
    }


def _sarif_result_path(result: dict[str, Any]) -> str:
    locations = result.get("locations")
    if isinstance(locations, list) and locations:
        physical = locations[0].get("physicalLocation", {}) if isinstance(locations[0], dict) else {}
        artifact = physical.get("artifactLocation", {}) if isinstance(physical, dict) else {}
        uri = artifact.get("uri") if isinstance(artifact, dict) else None
        if uri:
            return str(uri)
    return ""


def _write_outputs(summary: dict[str, Any], json_path: Path, sarif_path: Path, markdown_path: Path) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    values = {
        "sarif": sarif_path.as_posix(),
        "json": json_path.as_posix(),
        "markdown": markdown_path.as_posix(),
        "risk-score": str(summary.get("risk_score", 0)),
        "risk-severity": str(summary.get("risk_severity", "none")),
        "findings-count": str(summary.get("findings_count", 0)),
        "scanned-count": str(summary.get("scanned_count", 0)),
    }
    with Path(output_path).open("a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def _append_step_summary(markdown: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary_file:
            summary_file.write(markdown)
            summary_file.write("\n")
