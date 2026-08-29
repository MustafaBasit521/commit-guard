"""Tests for SARIF output."""

import json

from git_security.models.finding import Finding, Severity
from git_security.reporter.sarif import to_sarif


def _f(tool, rule, sev, file="a.py", line=3, msg="bad") -> Finding:
    return Finding(
        tool=tool, rule=rule, severity=sev, file=file, line=line, message=msg
    )


def test_empty_findings_is_valid_sarif():
    doc = json.loads(to_sarif([]))
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["name"] == "git-security-tool"


def test_severity_maps_to_sarif_level():
    doc = json.loads(
        to_sarif(
            [
                _f("semgrep", "eval", Severity.HIGH),
                _f("ruff", "F401", Severity.LOW),
                _f("semgrep", "shell", Severity.MEDIUM),
            ]
        )
    )
    levels = [r["level"] for r in doc["runs"][0]["results"]]
    assert levels == ["error", "note", "warning"]


def test_result_carries_location_and_rule():
    doc = json.loads(to_sarif([_f("gitleaks", "aws", Severity.CRITICAL, line=0)]))
    result = doc["runs"][0]["results"][0]
    assert result["ruleId"] == "gitleaks.aws"
    loc = result["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "a.py"
    assert loc["region"]["startLine"] == 1  # line 0 clamped to 1


def test_rules_are_deduplicated():
    doc = json.loads(
        to_sarif(
            [_f("semgrep", "eval", Severity.HIGH), _f("semgrep", "eval", Severity.HIGH)]
        )
    )
    assert len(doc["runs"][0]["tool"]["driver"]["rules"]) == 1
    assert len(doc["runs"][0]["results"]) == 2
