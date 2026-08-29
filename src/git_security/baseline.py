"""Suppress findings already recorded in a baseline file.

A baseline lets a repository adopt the tool without fixing every pre-existing
issue first: ``git-security-tool baseline`` records the current findings into
``.git-security-tool-baseline.json``, and later scans hide anything already
on that list. Newly introduced issues still surface and still block.

Fingerprint is ``(tool, rule, file, message)`` - deliberately line-independent
so unrelated edits to a file don't resurface a baselined finding. Regenerate
the baseline after large refactors.
"""

import json
from pathlib import Path

from git_security.models.finding import Finding

BASELINE_FILENAME = ".git-security-tool-baseline.json"
_VERSION = 1

Fingerprint = tuple[str, str, str, str]


def _fingerprint(finding: Finding) -> Fingerprint:
    return (finding.tool, finding.rule, finding.file, finding.message)


def load_baseline(repo_root: Path) -> set[Fingerprint]:
    """Fingerprints recorded in the baseline file, or an empty set."""
    path = repo_root / BASELINE_FILENAME
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        (
            entry.get("tool", ""),
            entry.get("rule", ""),
            entry.get("file", ""),
            entry.get("message", ""),
        )
        for entry in data.get("findings", [])
    }


def apply_baseline(
    findings: list[Finding], baseline: set[Fingerprint]
) -> tuple[list[Finding], int]:
    """Return (findings not in the baseline, count suppressed)."""
    kept = [f for f in findings if _fingerprint(f) not in baseline]
    return kept, len(findings) - len(kept)


def write_baseline(repo_root: Path, findings: list[Finding]) -> Path:
    """Write *findings* to the baseline file and return its path."""
    entries = sorted({_fingerprint(f) for f in findings})
    payload = {
        "version": _VERSION,
        "findings": [
            {"tool": t, "rule": r, "file": f, "message": m} for (t, r, f, m) in entries
        ],
    }
    path = repo_root / BASELINE_FILENAME
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
