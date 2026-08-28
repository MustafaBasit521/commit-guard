"""Ruff wrapper: staged Python files -> list[Finding].

Knows how to talk to Ruff and how to map Ruff's JSON to the normalized
``Finding`` model. Knows nothing about Git internals, policy, or reporting.

Approach A (milestone 3): scans the files as they exist in the working tree,
not the exact staged blobs. Editing a file after ``git add`` means Ruff sees
the newer version. Precise staged-content scanning is a later milestone.
"""

import json
from pathlib import Path

from git_security.models.finding import Finding, Severity
from git_security.scanners.base import run_tool, to_repo_relative

_NOT_FOUND_MSG = (
    "[git-security-tool] ruff not found on PATH - skipping "
    "(activate your venv / pip install ruff)"
)


def run_ruff(files: list[str], repo_root: Path) -> list[Finding]:
    """Lint the Python files in *files* and return normalized findings."""
    python_files = [f for f in files if f.endswith(".py")]
    if not python_files:
        return []

    proc = run_tool(
        ["ruff", "check", "--output-format=json", "--", *python_files]
    )
    if proc is None:
        print(_NOT_FOUND_MSG)
        return []

    # Ruff exit codes: 0 = clean, 1 = issues found, 2 = execution error.
    if proc.returncode == 2:
        raise RuntimeError(f"ruff failed: {proc.stderr.strip()}")

    if not proc.stdout.strip():
        return []

    return [_to_finding(item, repo_root) for item in json.loads(proc.stdout)]


def _to_finding(item: dict, repo_root: Path) -> Finding:
    location = item.get("location") or {}
    return Finding(
        tool="ruff",
        rule=item.get("code") or "",
        severity=Severity.LOW,  # code quality never blocks by default
        file=to_repo_relative(item.get("filename") or "", repo_root),
        line=location.get("row") or 0,
        message=item.get("message") or "",
    )
