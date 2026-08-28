"""Tests for the policy engine - pure logic, no Git, no scanners."""

from git_security.models.finding import Finding, Severity
from git_security.policy.engine import PolicyConfig, evaluate


def make_finding(severity: Severity, line: int = 1) -> Finding:
    return Finding(
        tool="t", rule="R", severity=severity, file="a.py", line=line, message="m"
    )


def test_no_findings_is_not_blocked():
    decision = evaluate([], PolicyConfig())
    assert decision.blocked is False
    assert decision.blocking == []
    assert decision.warnings == []


def test_low_and_medium_are_warnings_not_blocking():
    findings = [
        make_finding(Severity.INFO),
        make_finding(Severity.LOW),
        make_finding(Severity.MEDIUM),
    ]
    decision = evaluate(findings, PolicyConfig())
    assert decision.blocked is False
    assert len(decision.warnings) == 3
    assert decision.blocking == []


def test_high_severity_blocks():
    high = make_finding(Severity.HIGH)
    decision = evaluate([make_finding(Severity.LOW), high], PolicyConfig())
    assert decision.blocked is True
    assert decision.blocking == [high]
    assert len(decision.warnings) == 1


def test_critical_severity_blocks():
    decision = evaluate([make_finding(Severity.CRITICAL)], PolicyConfig())
    assert decision.blocked is True


def test_custom_threshold_lowered_to_medium():
    findings = [
        make_finding(Severity.LOW),
        make_finding(Severity.MEDIUM),
        make_finding(Severity.HIGH),
    ]
    decision = evaluate(
        findings, PolicyConfig(block_threshold=Severity.MEDIUM)
    )
    assert len(decision.blocking) == 2  # MEDIUM + HIGH
    assert len(decision.warnings) == 1  # LOW


def test_every_finding_is_either_blocking_or_warning():
    findings = [
        make_finding(Severity.INFO),
        make_finding(Severity.LOW),
        make_finding(Severity.HIGH),
        make_finding(Severity.CRITICAL),
    ]
    decision = evaluate(findings, PolicyConfig())
    assert len(decision.blocking) + len(decision.warnings) == len(findings)
