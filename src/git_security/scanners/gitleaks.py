"""Gitleaks wrapper: staged changes -> list[Finding].

Unlike Ruff, Gitleaks is Git-aware: it scans the *staged* changes directly
(``gitleaks protect --staged``), so this wrapper takes no file list. It maps
Gitleaks' JSON to the normalized ``Finding`` model and nothing else.
"""

import json

from git_security.models.finding import Finding, Severity
from git_security.scanners.base import run_tool

_NOT_FOUND_MSG = (
    "[git-security-tool] gitleaks not found on PATH - skipping "
    "(https://github.com/gitleaks/gitleaks#installing)"
)

# Gitleaks writes its JSON report to a path we pick. On Linux, "/dev/stdout"
# is the process's own stdout, so we read the report straight off the pipe
# with no temp file. This tool is Linux-only by design.
_STDOUT_PATH = "/dev/stdout"


def run_gitleaks() -> list[Finding]:
    """Scan the staged changes for secrets and return normalized findings."""
    proc = run_tool(
        [
            "gitleaks", "protect", "--staged",
            "--report-format", "json",
            "--report-path", _STDOUT_PATH,
            "--redact",      # never echo the actual secret value
            "--no-banner",   # no ASCII-art logo on stderr
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
        severity=Severity.CRITICAL,  # a staged secret always blocks
        file=item.get("File") or "",   # Gitleaks paths are already repo-relative
        line=item.get("StartLine") or 0,
        message=item.get("Description") or "",
    )
