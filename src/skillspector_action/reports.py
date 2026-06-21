from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

SEVERITY_RANK = {
    "none": 0,
    "info": 1,
    "note": 1,
    "low": 2,
    "warning": 2,
    "medium": 3,
    "error": 3,
    "high": 4,
    "critical": 5,
}


def highest_severity(severities: Iterable[str]) -> str:
    highest = "none"
    for severity in severities:
        normalized = normalize_severity(severity)
        if SEVERITY_RANK.get(normalized, 0) > SEVERITY_RANK[highest]:
            highest = normalized
    return highest


def normalize_severity(severity: Any) -> str:
    normalized = str(severity or "none").strip().lower()
    return normalized if normalized in SEVERITY_RANK else "none"


def merge_json_reports(
    reports: list[dict[str, Any]],
    suppressed_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    suppressed = suppressed_findings or []
    findings = []
    scores = []
    severities = []

    for report in reports:
        scores.append(_risk_score(report))
        severities.append(report.get("risk_severity") or report.get("severity") or "none")
        findings.extend(_report_findings(report))

    finding_severities = [finding.get("severity", "none") for finding in findings]
    severity = highest_severity([*severities, *finding_severities])
    return {
        "version": 1,
        "generated_by": "skillspector-action",
        "scanned_count": len(reports),
        "findings_count": len(findings),
        "suppressed_count": len(suppressed),
        "risk_score": max(scores, default=0),
        "risk_severity": severity,
        "findings": findings,
        "suppressed_findings": suppressed,
        "reports": reports,
    }


def merge_sarif_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    rules_by_id: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    driver = {"name": "SkillSpector", "rules": []}

    for report in reports:
        for run in report.get("runs", []):
            run_driver = run.get("tool", {}).get("driver", {})
            if run_driver.get("name") and driver["name"] == "SkillSpector":
                driver["name"] = run_driver["name"]
            for rule in run_driver.get("rules", []):
                rule_id = str(rule.get("id") or rule.get("ruleId") or "")
                if rule_id and rule_id not in rules_by_id:
                    rules_by_id[rule_id] = deepcopy(rule)
            results.extend(deepcopy(run.get("results", [])))

    driver["rules"] = [rules_by_id[rule_id] for rule_id in sorted(rules_by_id)]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": driver},
                "results": results,
            }
        ],
    }


def render_markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# SkillSpector Summary",
        "",
        f"- Scanned skills: {summary.get('scanned_count', 0)}",
        f"- Findings: {summary.get('findings_count', 0)}",
        f"- Suppressed: {summary.get('suppressed_count', 0)}",
        f"- Risk score: {summary.get('risk_score', 0)}",
        f"- Risk severity: {summary.get('risk_severity', 'none')}",
        "",
    ]
    findings = summary.get("findings", [])
    if findings:
        lines.extend(["## Findings", ""])
        for finding in findings:
            rule_id = finding.get("rule_id") or finding.get("ruleId") or "unknown"
            severity = normalize_severity(finding.get("severity"))
            message = finding.get("message") or finding.get("description") or ""
            path = finding.get("path") or ""
            lines.append(f"- **{severity}** `{rule_id}` {path} - {message}")
        lines.append("")
    return "\n".join(lines)


def _risk_score(report: dict[str, Any]) -> int:
    value = report.get("risk_score", report.get("score", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _report_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("filtered_findings")
    if findings is None:
        findings = report.get("findings")
    return [finding for finding in findings or [] if isinstance(finding, dict)]
