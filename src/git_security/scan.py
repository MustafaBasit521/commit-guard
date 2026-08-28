"""The pre-commit scan pipeline.

Gather the staged changes, run every scanner, evaluate policy, report, and
return an exit code. Invoked by ``git-security-tool scan`` (see cli.py).

Escape hatch while developing: set GIT_SECURITY_NO_BLOCK=1 to report
findings but never block.
"""

import os
import shutil
import tempfile
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path

from git_security.config.loader import AIConfig, ConfigError, load_config
from git_security.git.diff import (
    get_staged_diff,
    get_staged_file_content,
    get_staged_files,
    materialize_staged,
)
from git_security.git.repository import get_repo_root
from git_security.ignore import filter_ignored, is_ignored
from git_security.models.finding import Finding
from git_security.policy.engine import evaluate
from git_security.reporter.terminal import report
from git_security.scanners.gitleaks import run_gitleaks
from git_security.scanners.ruff import run_ruff, run_ruff_format
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


def _safe_scan(name: str, run: Callable[[], list[Finding]]) -> list[Finding]:
    """Run one scanner, turning a crash into a clear message + empty result.

    A scanner that fails to run leaves that dimension unchecked; we say so
    loudly and let the other scanners and the policy decide the commit.
    """
    try:
        return run()
    except RuntimeError as exc:
        print(f"{_PREFIX} {name} failed to run - skipping it: {exc}")
        return []


def _staged_snippet(finding: Finding, context: int = 5) -> str:
    """A few lines of the staged file around the finding, with line numbers."""
    try:
        lines = get_staged_file_content(finding.file).splitlines()
    except RuntimeError:
        return ""
    if finding.line <= 0:
        window = lines[: 2 * context + 1]
        start = 1
    else:
        start = max(1, finding.line - context)
        window = lines[start - 1 : finding.line + context]
    return "\n".join(f"{start + i}: {text}" for i, text in enumerate(window))


def _run_ai_suggestions(
    blocking: list[Finding], all_findings: list[Finding], ai: AIConfig
) -> None:
    from git_security.suggestions.llm import explain, suggestions_available

    if not suggestions_available(ai.provider):
        print(
            f"{_PREFIX} AI suggestions are enabled but the '{ai.provider}' "
            "provider is unavailable - check its API key "
            "(ANTHROPIC_API_KEY / GEMINI_API_KEY)"
        )
        return

    # Never send secret-bearing code off the machine: skip Gitleaks findings
    # and skip any file that Gitleaks flagged (its snippet could include the
    # secret).
    secret_files = {f.file for f in all_findings if f.tool == "gitleaks"}
    targets = [
        f for f in blocking if f.tool != "gitleaks" and f.file not in secret_files
    ][: ai.max_findings]

    if not targets:
        print(
            f"{_PREFIX} no findings eligible for AI suggestions "
            "(secret-bearing code is never sent)"
        )
        return
    explain([(f, _staged_snippet(f)) for f in targets], ai)


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

    repo_root = get_repo_root()
    try:
        config = load_config(repo_root)
    except ConfigError as exc:
        print(f"{_PREFIX} config error: {exc}")
        return 1

    scannable = filter_ignored(staged_files, config.ignore_paths)
    ignored = len(staged_files) - len(scannable)
    suffix = f" ({ignored} ignored by config)" if ignored else ""
    print(f"{_PREFIX} {len(scannable)} file(s) to scan{suffix}:")
    for path in scannable:
        print(f"  - {path}")

    if not scannable:
        print(f"{_PREFIX} nothing to scan after ignores - allowing commit")
        return 0

    diff = get_staged_diff()
    print(f"{_PREFIX} staged diff: {len(diff.splitlines())} lines")

    rules_dir = _semgrep_rules_dir()
    enabled = config.enabled_scanners
    findings: list[Finding] = []

    # Ruff and Semgrep read files from disk, so we hand them the exact staged
    # content copied into a throwaway directory - not the working tree, which
    # may have changed since `git add`.
    with tempfile.TemporaryDirectory(prefix="git-security-tool-") as tmp:
        staged_root = Path(tmp)
        materialize_staged(scannable, staged_root)
        _copy_project_config(repo_root, staged_root)
        staged_paths = [str(staged_root / f) for f in scannable]

        if "ruff" in enabled:
            findings += _safe_scan("ruff", lambda: run_ruff(staged_paths, staged_root))
            findings += _safe_scan(
                "ruff format", lambda: run_ruff_format(staged_paths, staged_root)
            )
        if "semgrep" in enabled:
            findings += _safe_scan(
                "semgrep",
                lambda: run_semgrep(staged_paths, staged_root, rules_dir),
            )

    # Gitleaks is git-aware and scans the whole staged index, so filter its
    # findings by the same ignore patterns after the fact.
    if "gitleaks" in enabled:
        leaks = _safe_scan("gitleaks", run_gitleaks)
        findings += [f for f in leaks if not is_ignored(f.file, config.ignore_paths)]

    decision = evaluate(findings, config.policy)
    report(decision)

    if config.ai.enabled and decision.blocking:
        _run_ai_suggestions(decision.blocking, findings, config.ai)

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
