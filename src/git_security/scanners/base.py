"""Shared plumbing for scanner wrappers.

Each scanner module owns the tool-specific knowledge: which command to run,
how to read its exit codes, how to map its output to ``Finding``. What every
scanner shares is "run an external process, and cope if it isn't installed" -
that lives here.
"""

import subprocess


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
