import json

from skillspector_action.reports import (
    highest_severity,
    merge_json_reports,
    merge_sarif_reports,
    render_markdown_summary,
)


def test_merge_json_reports_computes_counts_score_and_severity() -> None:
    reports = [
        {
            "target": "skills/alpha",
            "risk_score": 42,
            "risk_severity": "MEDIUM",
            "filtered_findings": [
                {"rule_id": "SS001", "severity": "medium", "message": "issue", "path": "skills/alpha/SKILL.md"}
            ],
        },
        {
            "target": "skills/beta",
            "risk_score": 91,
            "risk_severity": "CRITICAL",
            "filtered_findings": [
                {"rule_id": "SS002", "severity": "critical", "message": "bad", "path": "skills/beta/SKILL.md"}
            ],
        },
    ]

    merged = merge_json_reports(reports, suppressed_findings=[{"rule_id": "SS000"}])

    assert merged["scanned_count"] == 2
    assert merged["findings_count"] == 2
    assert merged["suppressed_count"] == 1
    assert merged["risk_score"] == 91
    assert merged["risk_severity"] == "critical"


def test_highest_severity_orders_values() -> None:
    assert highest_severity(["low", "critical", "medium"]) == "critical"
    assert highest_severity([]) == "none"


def test_merge_sarif_reports_outputs_single_run_with_deduplicated_rules() -> None:
    sarif_one = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "SkillSpector", "rules": [{"id": "SS001", "name": "One"}]}},
                "results": [{"ruleId": "SS001", "message": {"text": "one"}}],
            }
        ],
    }
    sarif_two = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "SkillSpector", "rules": [{"id": "SS001", "name": "One"}]}},
                "results": [{"ruleId": "SS001", "message": {"text": "two"}}],
            }
        ],
    }

    merged = merge_sarif_reports([sarif_one, sarif_two])

    assert merged["version"] == "2.1.0"
    assert len(merged["runs"]) == 1
    assert merged["runs"][0]["tool"]["driver"]["rules"] == [{"id": "SS001", "name": "One"}]
    assert [result["message"]["text"] for result in merged["runs"][0]["results"]] == ["one", "two"]
    json.dumps(merged)


def test_render_markdown_summary_contains_key_counts() -> None:
    markdown = render_markdown_summary(
        {
            "scanned_count": 2,
            "findings_count": 1,
            "suppressed_count": 3,
            "risk_score": 88,
            "risk_severity": "high",
        }
    )

    assert "Scanned skills: 2" in markdown
    assert "Findings: 1" in markdown
    assert "Suppressed: 3" in markdown
    assert "Risk score: 88" in markdown
    assert "Risk severity: high" in markdown
