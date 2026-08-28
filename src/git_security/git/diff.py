"""Read what is currently staged for the next commit.

Everything here shells out to ``git`` through :mod:`subprocess` and returns
plain Python values. Milestone 2 only needs to *see* what the commit will
contain, so there is no parsing of diff contents yet.
"""

import subprocess


def _run_git(args: list[str]) -> str:
    """Run ``git <args>`` and return its stdout as text.

    Uses an argument list (no shell), so there is nothing to quote and no
    injection risk. Raises ``RuntimeError`` with git's own error message if
    the command is missing or exits non-zero, so callers never get a silent
    empty result.
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


def get_staged_files() -> list[str]:
    """Return the paths staged for the next commit.

    ``--diff-filter=ACM`` keeps Added / Copied / Modified files and drops
    deletions, since there is nothing to scan in a file that is being removed.
    """
    output = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"])
    return [line for line in output.splitlines() if line]


def get_staged_diff() -> str:
    """Return the full unified diff of everything staged for the next commit."""
    return _run_git(["diff", "--cached"])
