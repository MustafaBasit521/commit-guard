"""Gitleaks wrapper: staged changes (or the whole tree) -> list[Finding].

Gitleaks is Git-aware, so this wrapper takes no file list:

* ``staged=True``  -> ``gitleaks git --staged`` (the staged diff, pre-commit)
* ``staged=False`` -> ``gitleaks dir .``        (every file on disk, CI / audit)

It maps Gitleaks' JSON to the normalized ``Finding`` model and nothing else.
"""

import json

from git_security.models.finding import Finding, Severity
from git_security.scanners.base import run_tool

_NOT_FOUND_MSG = (
    "[git-security-tool] gitleaks not found on PATH - skipping "
    "(https://github.com/gitleaks/gitleaks#installing)"
)


def run_gitleaks(staged: bool = True) -> list[Finding]:
    """Scan for secrets and return normalized findings."""
    mode = ["git", "--staged"] if staged else ["dir", "."]
    proc = run_tool(
        [
            "gitleaks",
            *mode,
            "--report-format",
            "json",
            "--report-path",
            "-",  # write the JSON report to stdout
            "--redact",  # never echo the actual secret value
            "--no-banner",
        ]
    )
    if proc is None:
        print(_NOT_FOUND_MSG)
        return []

    # Gitleaks exit codes: 0 = no leaks, 1 = leaks found, other = error.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"gitleaks failed: {proc.stderr.strip()}")

    if not proc.stdout.strip():
        return []

    return [_to_finding(item) for item in json.loads(proc.stdout)]


def _to_finding(item: dict) -> Finding:
    return Finding(
        tool="gitleaks",
        rule=item.get("RuleID") or "",
        severity=Severity.CRITICAL,  # a committed secret always blocks
        file=item.get("File") or "",  # Gitleaks paths are already repo-relative
        line=item.get("StartLine") or 0,
        message=item.get("Description") or "",
    )
