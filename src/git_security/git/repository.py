"""Low-level access to the current Git repository.

Every call that shells out to ``git`` goes through :func:`run_git` here.
Higher-level modules (``diff.py``) build on it.
"""

import subprocess
from pathlib import Path


def run_git(args: list[str]) -> str:
    """Run ``git <args>`` and return stdout as text.

    Argument list, no shell - nothing to quote, no injection risk. Raises
    ``RuntimeError`` with git's own stderr if git is missing or exits
    non-zero, so callers never get a silent empty result.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("git executable not found on PATH")

    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def get_repo_root() -> Path:
    """Absolute path to the top level of the current working tree."""
    return Path(run_git(["rev-parse", "--show-toplevel"]).strip())
