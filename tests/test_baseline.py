import json
from pathlib import Path

from skillspector_action.baseline import filter_baselined_findings, message_hash


def test_baseline_suppresses_matching_finding(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "version": 1,
                "findings": [
                    {
                        "rule_id": "SS001",
                        "path": "skills/alpha/SKILL.md",
                        "message_hash": message_hash("dangerous instruction")[:16],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    findings = [
        {
            "rule_id": "SS001",
            "message": "dangerous instruction",
            "path": "skills/alpha/SKILL.md",
        },
        {
            "rule_id": "SS002",
            "message": "new issue",
            "path": "skills/alpha/SKILL.md",
        },
    ]

    active, suppressed = filter_baselined_findings(findings, baseline_path)

    assert active == [findings[1]]
    assert suppressed == [findings[0]]


def test_missing_baseline_keeps_all_findings(tmp_path: Path) -> None:
    findings = [{"rule_id": "SS001", "message": "issue", "path": "SKILL.md"}]

    active, suppressed = filter_baselined_findings(findings, tmp_path / "missing.json")

    assert active == findings
    assert suppressed == []
