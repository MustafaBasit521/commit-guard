"""Shared plumbing for scanner wrappers.

Each scanner module owns the tool-specific knowledge: which command to run,
how to read its exit codes, how to map its output to ``Finding``. What every
scanner shares - run an external process, cope if it isn't installed, and
report paths consistently - lives here.
"""

import subprocess
from pathlib import Path


def run_tool(cmd: list[str]) -> subprocess.CompletedProcess | None:
    """Run an external tool with stdout/stderr captured.

    Returns the ``CompletedProcess`` for any exit code, or ``None`` if the
    executable is not on PATH - so callers can skip a missing tool cleanly
    instead of crashing the commit.
    """
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None


def to_repo_relative(path: str, repo_root: Path) -> str:
    """Make an absolute path repo-relative; leave anything else untouched."""
    p = Path(path)
    if not p.is_absolute():
        return path
    try:
        return str(p.relative_to(repo_root))
    except ValueError:
        return path
