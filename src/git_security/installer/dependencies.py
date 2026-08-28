"""Check which external scanners are available on PATH.

The tool never installs anything itself - it just tells the user what is
present and what is missing. Missing scanners are skipped at scan time.
"""

import shutil

SCANNERS = ("ruff", "gitleaks", "semgrep")


def check_dependencies() -> dict[str, bool]:
    """Map each scanner name to whether its executable is on PATH."""
    return {name: shutil.which(name) is not None for name in SCANNERS}
