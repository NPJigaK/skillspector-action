import json
from pathlib import Path

from skillspector_action.baseline import message_hash
from skillspector_action.config import Config
from skillspector_action.runner import ScanResult, run_action


def _fake_sarif(rule_id: str = "SS001") -> dict:
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "SkillSpector", "rules": [{"id": rule_id}]}},
                "results": [{"ruleId": rule_id, "message": {"text": "issue"}}],
            }
        ],
    }


def test_run_action_writes_reports_and_outputs(tmp_path: Path, monkeypatch) -> None:
    skill_dir = tmp_path / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")
    output_dir = tmp_path / "results"
    github_output = tmp_path / "github_output.txt"
    step_summary = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))

    def scanner(target: Path, work_dir: Path, use_llm: bool) -> ScanResult:
        return ScanResult(
            json_report={
                "target": target.as_posix(),
                "risk_score": 80,
                "risk_severity": "HIGH",
                "filtered_findings": [
                    {"rule_id": "SS001", "severity": "high", "message": "issue", "path": "skills/alpha/SKILL.md"}
                ],
            },
            sarif_report=_fake_sarif(),
        )

    code = run_action(
        Config(path=tmp_path, output_dir=output_dir, fail_on="none"),
        scanner=scanner,
    )

    assert code == 0
    results = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert results["scanned_count"] == 1
    assert results["findings_count"] == 1
    assert (output_dir / "results.sarif").exists()
    assert (output_dir / "summary.md").exists()
    assert "risk-score=80" in github_output.read_text(encoding="utf-8")
    assert "SkillSpector Summary" in step_summary.read_text(encoding="utf-8")


def test_run_action_empty_targets_succeeds(tmp_path: Path) -> None:
    output_dir = tmp_path / "results"

    code = run_action(Config(path=tmp_path, output_dir=output_dir, fail_on="critical"))

    assert code == 0
    results = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert results["scanned_count"] == 0


def test_config_from_env_parses_inputs(tmp_path: Path) -> None:
    env = {
        "INPUT_PATH": "skills",
        "INPUT_CHANGED_ONLY": "true",
        "INPUT_FAIL_ON": "critical",
        "INPUT_MIN_SCORE": "75",
        "INPUT_EXCLUDE": "vendor/**\narchive/**",
        "INPUT_BASELINE": "baseline.json",
        "INPUT_LLM": "true",
        "INPUT_OUTPUT_DIR": "out",
    }

    config = Config.from_env(env, workspace=tmp_path)

    assert config.path == tmp_path / "skills"
    assert config.changed_only is True
    assert config.fail_on == "critical"
    assert config.min_score == 75
    assert config.excludes == ["vendor/**", "archive/**"]
    assert config.baseline == tmp_path / "baseline.json"
    assert config.llm is True
    assert config.output_dir == tmp_path / "out"


def test_baseline_suppression_removes_sarif_results_and_failure(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "version": 1,
                "findings": [
                    {
                        "rule_id": "SS001",
                        "path": "skills/alpha/SKILL.md",
                        "message_hash": message_hash("issue")[:16],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def scanner(target: Path, work_dir: Path, use_llm: bool) -> ScanResult:
        return ScanResult(
            json_report={
                "target": target.as_posix(),
                "risk_score": 100,
                "risk_severity": "CRITICAL",
                "filtered_findings": [
                    {"rule_id": "SS001", "severity": "critical", "message": "issue", "path": "skills/alpha/SKILL.md"}
                ],
            },
            sarif_report={
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {"driver": {"name": "SkillSpector", "rules": [{"id": "SS001"}]}},
                        "results": [
                            {
                                "ruleId": "SS001",
                                "message": {"text": "issue"},
                                "locations": [
                                    {
                                        "physicalLocation": {
                                            "artifactLocation": {"uri": "skills/alpha/SKILL.md"}
                                        }
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        )

    code = run_action(
        Config(path=tmp_path, output_dir=tmp_path / "results", fail_on="critical", min_score=1, baseline=baseline),
        scanner=scanner,
    )

    results = json.loads((tmp_path / "results" / "results.json").read_text(encoding="utf-8"))
    sarif = json.loads((tmp_path / "results" / "results.sarif").read_text(encoding="utf-8"))
    assert code == 0
    assert results["findings_count"] == 0
    assert results["suppressed_count"] == 1
    assert results["risk_score"] == 0
    assert results["risk_severity"] == "none"
    assert sarif["runs"][0]["results"] == []
