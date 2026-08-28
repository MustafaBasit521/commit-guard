"""The pre-commit scan pipeline.

Gather the staged changes, run every scanner, evaluate policy, report, and
return an exit code. Invoked by ``git-security-tool scan`` (see cli.py).

Escape hatch while developing: set GIT_SECURITY_NO_BLOCK=1 to report
findings but never block.
"""

import os
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path

from git_security.config.loader import load_config
from git_security.git.diff import (
    get_staged_diff,
    get_staged_files,
    materialize_staged,
)
from git_security.git.repository import get_repo_root
from git_security.models.finding import Finding
from git_security.policy.engine import evaluate
from git_security.reporter.terminal import report
from git_security.scanners.gitleaks import run_gitleaks
from git_security.scanners.ruff import run_ruff
from git_security.scanners.semgrep import run_semgrep

_PREFIX = "[git-security-tool]"

# Config files a scanner may look for when deciding how to lint a project.
_PROJECT_CONFIG_FILES = ("pyproject.toml", "ruff.toml", ".ruff.toml", "setup.cfg")


def _copy_project_config(repo_root: Path, dest: Path) -> None:
    """Place the repo's lint config at the root of the materialized tree.

    Scanners resolve their configuration by walking up from each file. The
    throwaway directory has none, so without this Ruff (etc.) would silently
    use built-in defaults instead of the project's settings.
    """
    for name in _PROJECT_CONFIG_FILES:
        src = repo_root / name
        if src.is_file():
            shutil.copy2(src, dest / name)


def _semgrep_rules_dir() -> Path:
    """Directory of bundled Semgrep rules.

    The rules ship inside the package. For a normal (non-zipped) install this
    resolves to a real directory on disk, which is all run_semgrep needs.
    """
    return Path(str(files("git_security") / "rules" / "semgrep"))


def run_scan() -> int:
    print(f"{_PREFIX} pre-commit security scan")

    staged_files = get_staged_files()
    if not staged_files:
        print(f"{_PREFIX} nothing staged - allowing commit")
        return 0

    print(f"{_PREFIX} {len(staged_files)} file(s) staged:")
    for path in staged_files:
        print(f"  - {path}")

    diff = get_staged_diff()
    print(f"{_PREFIX} staged diff: {len(diff.splitlines())} lines")

    repo_root = get_repo_root()
    config = load_config(repo_root)
    rules_dir = _semgrep_rules_dir()

    enabled = config.enabled_scanners
    findings: list[Finding] = []

    # Ruff and Semgrep read files from disk, so we hand them the exact staged
    # content copied into a throwaway directory - not the working tree, which
    # may have changed since `git add`.
    with tempfile.TemporaryDirectory(prefix="git-security-tool-") as tmp:
        staged_root = Path(tmp)
        materialize_staged(staged_files, staged_root)
        _copy_project_config(repo_root, staged_root)
        staged_paths = [str(staged_root / f) for f in staged_files]

        if "ruff" in enabled:
            findings += run_ruff(staged_paths, staged_root)
        if "semgrep" in enabled:
            findings += run_semgrep(staged_paths, staged_root, rules_dir)

    # Gitleaks is already git-aware: it scans the staged index itself.
    if "gitleaks" in enabled:
        findings += run_gitleaks()

    decision = evaluate(findings, config.policy)
    report(decision)

    if not decision.blocked:
        print(f"{_PREFIX} commit allowed")
        return 0

    if os.environ.get("GIT_SECURITY_NO_BLOCK") == "1":
        print(
            f"{_PREFIX} would block, but GIT_SECURITY_NO_BLOCK=1 is set "
            "- commit allowed"
        )
        return 0

    print(
        f"{_PREFIX} commit blocked - fix the blocking findings above, "
        "or set GIT_SECURITY_NO_BLOCK=1 to override"
    )
    return 1
