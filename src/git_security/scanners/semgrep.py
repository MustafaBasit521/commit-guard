"""Semgrep wrapper: staged files -> list[Finding].

Runs Semgrep with our local rule set and maps Semgrep's JSON results to the
normalized ``Finding`` model.

Rule-source decision (milestone 6): we use only the local ``rules/semgrep/``
directory - fully offline and deterministic, no code or metadata leaves the
machine. Registry rule packs (``p/python``, ``p/security-audit``) can be
added as an opt-in config option later.
"""

import json
from pathlib import Path

from git_security.models.finding import Finding, Severity
from git_security.scanners.base import run_tool, to_repo_relative

_NOT_FOUND_MSG = (
    "[git-security-tool] semgrep not found on PATH - skipping "
    "(pip install semgrep)"
)

# Semgrep severities -> our severity scale.
_SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}


def run_semgrep(
    files: list[str], repo_root: Path, rules_dir: Path
) -> list[Finding]:
    """Scan *files* with the rules in *rules_dir* and return normalized findings."""
    if not files:
        return []
    if not rules_dir.exists():
        print(
            f"[git-security-tool] semgrep rules not found at {rules_dir} "
            "- skipping"
        )
        return []

    proc = run_tool(
        [
            "semgrep",
            "--config", str(rules_dir),
            "--json",
            "--quiet",
            "--metrics=off",
            "--disable-version-check",
            "--",
            *files,
        ]
    )
    if proc is None:
        print(_NOT_FOUND_MSG)
        return []

    # Semgrep exit codes: 0 = no findings, 1 = findings found, >=2 = error.
    if proc.returncode not in (0, 1):
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"semgrep failed: {detail}")

    if not proc.stdout.strip():
        return []

    data = json.loads(proc.stdout)
    return [_to_finding(r, repo_root) for r in data.get("results", [])]


def _to_finding(result: dict, repo_root: Path) -> Finding:
    extra = result.get("extra") or {}
    start = result.get("start") or {}
    return Finding(
        tool="semgrep",
        rule=result.get("check_id") or "",
        severity=_SEVERITY_MAP.get(extra.get("severity", ""), Severity.MEDIUM),
        file=to_repo_relative(result.get("path") or "", repo_root),
        line=start.get("line") or 0,
        message=(extra.get("message") or "").strip(),
    )
