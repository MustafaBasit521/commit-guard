"""Wrapper around the Ruff linter.

Takes a list of file paths, runs ``ruff`` over the Python ones, and returns
Ruff's raw JSON findings. This module knows nothing about Git, policy, or
reporting - it only knows how to talk to Ruff.

Approach A (milestone 3): we scan the files as they exist in the working
tree, not the exact staged blobs. If a file is edited after ``git add``,
Ruff sees the newer version. Scanning staged content precisely is a later
milestone.
"""

import json
import subprocess


def run_ruff(files: list[str]) -> list[dict]:
    """Run ``ruff check`` over the Python files in *files*.

    Returns Ruff's findings as a list of raw dicts (no normalization yet).
    Returns an empty list if no Python files were given or Ruff is not
    available on PATH.
    """
    python_files = [f for f in files if f.endswith(".py")]
    if not python_files:
        return []

    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", "--", *python_files],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(
            "[git-security-tool] ruff not found on PATH - skipping "
            "(activate your venv / pip install ruff)"
        )
        return []

    # Ruff exit codes: 0 = clean, 1 = lint issues found, 2 = execution error.
    # Only 2 is an actual failure on our side.
    if result.returncode == 2:
        raise RuntimeError(f"ruff failed: {result.stderr.strip()}")

    if not result.stdout.strip():
        return []

    return json.loads(result.stdout)
