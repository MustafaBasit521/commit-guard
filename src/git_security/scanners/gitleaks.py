"""Wrapper around Gitleaks (secret / credential detection).

Unlike Ruff, Gitleaks is Git-aware: instead of taking a list of files, it
scans the *staged* changes directly (``gitleaks protect --staged``). So this
wrapper takes no arguments - it asks Gitleaks what secrets are in whatever is
currently staged for commit.

Like the Ruff wrapper, this module knows nothing about policy or reporting.
It only knows how to talk to Gitleaks and hand back raw findings.
"""

import json
import subprocess

# Gitleaks writes its JSON report to a path we choose. On Linux, "/dev/stdout"
# lets us read it straight from the pipe without a temp file. This tool is
# Linux-only by design, so that is fine.
_STDOUT_PATH = "/dev/stdout"


def run_gitleaks() -> list[dict]:
    """Scan the staged changes for secrets.

    Returns Gitleaks' findings as a list of raw dicts (no normalization yet).
    Returns an empty list if Gitleaks is not installed.
    Raises RuntimeError if Gitleaks runs but errors out.
    """
    try:
        result = subprocess.run(
            [
                "gitleaks",
                "protect",
                "--staged",
                "--report-format", "json",
                "--report-path", _STDOUT_PATH,
                "--redact",      # never echo the actual secret value
                "--no-banner",   # no ASCII-art logo on stderr
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print(
            "[git-security-tool] gitleaks not found on PATH - skipping "
            "(https://github.com/gitleaks/gitleaks#installing)"
        )
        return []

    # Gitleaks exit codes: 0 = no leaks, 1 = leaks found, anything else = error.
    if result.returncode not in (0, 1):
        raise RuntimeError(f"gitleaks failed: {result.stderr.strip()}")

    if not result.stdout.strip():
        return []

    return json.loads(result.stdout)
