"""Tests for the scanner output-to-Finding mappers.

These exercise only the pure ``_to_finding`` / path helpers - no subprocess,
no real tools. They lock in the shape of each tool's JSON that we depend on.
"""

from pathlib import Path

from git_security.models.finding import Severity
from git_security.scanners.base import to_repo_relative
from git_security.scanners.gitleaks import _to_finding as gitleaks_to_finding
from git_security.scanners.ruff import _to_finding as ruff_to_finding
from git_security.scanners.semgrep import _to_finding as semgrep_to_finding

REPO = Path("/repo")


# --- to_repo_relative -------------------------------------------------------

def test_absolute_path_becomes_relative():
    assert to_repo_relative("/repo/src/a.py", REPO) == "src/a.py"


def test_relative_path_is_untouched():
    assert to_repo_relative("src/a.py", REPO) == "src/a.py"


def test_path_outside_repo_is_kept_as_is():
    assert to_repo_relative("/somewhere/else.py", REPO) == "/somewhere/else.py"


# --- ruff -----------------------------------------------------------------

def test_ruff_mapping():
    item = {
        "code": "F401",
        "message": "`os` imported but unused",
        "filename": "/repo/x.py",
        "location": {"row": 3, "column": 1},
    }
    finding = ruff_to_finding(item, REPO)
    assert finding.tool == "ruff"
    assert finding.rule == "F401"
    assert finding.severity is Severity.LOW
    assert finding.file == "x.py"
    assert finding.line == 3


def test_ruff_mapping_tolerates_missing_fields():
    finding = ruff_to_finding({"message": "syntax error", "location": {}}, REPO)
    assert finding.rule == ""
    assert finding.line == 0


# --- gitleaks -----------------------------------------------------------------

def test_gitleaks_mapping():
    item = {
        "RuleID": "aws-access-token",
        "Description": "AWS Access Key",
        "File": "config.py",
        "StartLine": 12,
    }
    finding = gitleaks_to_finding(item)
    assert finding.tool == "gitleaks"
    assert finding.rule == "aws-access-token"
    assert finding.severity is Severity.CRITICAL
    assert finding.file == "config.py"
    assert finding.line == 12


# --- semgrep -----------------------------------------------------------------

def test_semgrep_error_maps_to_high():
    result = {
        "check_id": "src.git_security.rules.semgrep.python-dangerous-eval",
        "path": "/repo/x.py",
        "start": {"line": 4},
        "extra": {"message": "  eval is bad\n", "severity": "ERROR"},
    }
    finding = semgrep_to_finding(result, REPO)
    assert finding.tool == "semgrep"
    assert finding.rule == "python-dangerous-eval"
    assert finding.severity is Severity.HIGH
    assert finding.file == "x.py"
    assert finding.line == 4
    assert finding.message == "eval is bad"


def test_semgrep_unknown_severity_defaults_to_medium():
    result = {
        "check_id": "x",
        "path": "x.py",
        "start": {},
        "extra": {"severity": "NOPE"},
    }
    finding = semgrep_to_finding(result, REPO)
    assert finding.severity is Severity.MEDIUM
    assert finding.line == 0
