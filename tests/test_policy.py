from skillspector_action.runner import should_fail


def test_fail_on_none_never_fails_for_findings() -> None:
    assert not should_fail({"risk_severity": "critical", "risk_score": 100}, "none", None)


def test_fail_on_high_fails_for_high_and_critical() -> None:
    assert should_fail({"risk_severity": "high", "risk_score": 80}, "high", None)
    assert should_fail({"risk_severity": "critical", "risk_score": 90}, "high", None)


def test_fail_on_critical_only_fails_for_critical() -> None:
    assert not should_fail({"risk_severity": "high", "risk_score": 80}, "critical", None)
    assert should_fail({"risk_severity": "critical", "risk_score": 90}, "critical", None)


def test_min_score_threshold_can_fail() -> None:
    assert should_fail({"risk_severity": "low", "risk_score": 70}, "none", 70)
    assert not should_fail({"risk_severity": "low", "risk_score": 69}, "none", 70)
