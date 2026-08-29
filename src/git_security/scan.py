"""The scan pipeline.

Gather the files to check, run every scanner, evaluate policy, report, and
return an exit code.

* ``run_scan("staged")`` - the pre-commit path: scans the exact staged blob
  content and can offer AI suggestions.
* ``run_scan("all")`` - the CI / audit path: scans every tracked file in the
  working tree; supports ``--format sarif``.
* ``write_baseline_file()`` - records the current findings so a repo can
  adopt the tool without fixing everything first.

Escape hatch (staged mode only): set GIT_SECURITY_NO_BLOCK=1 to report
findings but never block.
"""

import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path

from git_security.baseline import apply_baseline, load_baseline, write_baseline
from git_security.config.loader import AIConfig, Config, ConfigError, load_config
from git_security.git.diff import (
    get_staged_file_content,
    get_staged_files,
    get_tracked_files,
    materialize_staged,
)
from git_security.git.repository import get_repo_root
from git_security.ignore import filter_ignored, is_ignored
from git_security.models.finding import Finding
from git_security.policy.engine import evaluate
from git_security.reporter.sarif import to_sarif
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


def _safe_scan(name: str, run: Callable[[], list[Finding]], log) -> list[Finding]:
    """Run one scanner, turning a crash into a clear message + empty result."""
    try:
        return run()
    except RuntimeError as exc:
        log(f"{_PREFIX} {name} failed to run - skipping it: {exc}")
        return []


def _run_file_scanners(
    paths: list[str], root: Path, rules_dir: Path, enabled: frozenset[str], log
) -> list[Finding]:
    findings: list[Finding] = []
    if "ruff" in enabled:
        findings += _safe_scan("ruff", lambda: run_ruff(paths, root), log)
        findings += _safe_scan("ruff format", lambda: run_ruff_format(paths, root), log)
    if "semgrep" in enabled:
        findings += _safe_scan(
            "semgrep", lambda: run_semgrep(paths, root, rules_dir), log
        )
    return findings


def _semgrep_rules_dir() -> Path:
    """Directory of bundled Semgrep rules (shipped inside the package)."""
    return Path(str(files("git_security") / "rules" / "semgrep"))


def _collect_findings(scope: str, log) -> tuple[list[Finding], Path, Config]:
    """Run every enabled scanner for *scope*. Raises ConfigError."""
    staged = scope == "staged"
    repo_root = get_repo_root()
    config = load_config(repo_root)

    candidates = get_staged_files() if staged else get_tracked_files()
    scannable = filter_ignored(candidates, config.ignore_paths)

    if not scannable:
        if not candidates:
            log(
                f"{_PREFIX} "
                + ("nothing staged" if staged else "no tracked files to scan")
            )
        else:
            log(f"{_PREFIX} nothing to scan after ignores")
        return [], repo_root, config

    ignored = len(candidates) - len(scannable)
    suffix = f" ({ignored} ignored by config)" if ignored else ""
    log(f"{_PREFIX} {len(scannable)} file(s) to scan{suffix}")

    rules_dir = _semgrep_rules_dir()
    enabled = config.enabled_scanners
    findings: list[Finding] = []

    if staged:
        # Scan the exact staged blob content, not the working tree.
        with tempfile.TemporaryDirectory(prefix="git-security-tool-") as tmp:
            root = Path(tmp)
            materialize_staged(scannable, root)
            _copy_project_config(repo_root, root)
            paths = [str(root / f) for f in scannable]
            findings += _run_file_scanners(paths, root, rules_dir, enabled, log)
    else:
        paths = [str(repo_root / f) for f in scannable]
        findings += _run_file_scanners(paths, repo_root, rules_dir, enabled, log)

    if "gitleaks" in enabled:
        leaks = _safe_scan("gitleaks", lambda: run_gitleaks(staged=staged), log)
        findings += [f for f in leaks if not is_ignored(f.file, config.ignore_paths)]

    return findings, repo_root, config


# --- AI suggestions ---------------------------------------------------------


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
    # and skip any file that Gitleaks flagged.
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


# --- entry points ----------------------------------------------------------


def run_scan(scope: str = "staged", output_format: str = "text") -> int:
    staged = scope == "staged"
    sarif = output_format == "sarif"
    # In sarif mode stdout must be pure JSON, so progress goes to stderr.
    log: Callable[[str], None] = (
        (lambda m: print(m, file=sys.stderr)) if sarif else print
    )
    log(
        f"{_PREFIX} " + ("pre-commit security scan" if staged else "full security scan")
    )

    try:
        findings, repo_root, config = _collect_findings(scope, log)
    except ConfigError as exc:
        log(f"{_PREFIX} config error: {exc}")
        return 1

    baseline = load_baseline(repo_root)
    if baseline:
        findings, suppressed = apply_baseline(findings, baseline)
        if suppressed:
            log(f"{_PREFIX} {suppressed} finding(s) suppressed by baseline")

    decision = evaluate(findings, config.policy)

    if sarif:
        print(to_sarif(decision.blocking + decision.warnings))
    else:
        report(decision)

    if staged and config.ai.enabled and decision.blocking:
        _run_ai_suggestions(decision.blocking, findings, config.ai)

    passed = "commit allowed" if staged else "scan passed"
    blocked = "commit blocked" if staged else "scan failed"

    if not decision.blocked:
        log(f"{_PREFIX} {passed}")
        return 0

    if staged and os.environ.get("GIT_SECURITY_NO_BLOCK") == "1":
        log(f"{_PREFIX} would block, but GIT_SECURITY_NO_BLOCK=1 is set - {passed}")
        return 0

    override = ", or set GIT_SECURITY_NO_BLOCK=1 to override" if staged else ""
    log(f"{_PREFIX} {blocked} - fix the blocking findings above{override}")
    return 1


def write_baseline_file() -> int:
    """Record the current full-repo findings into the baseline file."""
    try:
        findings, repo_root, _ = _collect_findings("all", print)
    except ConfigError as exc:
        print(f"{_PREFIX} config error: {exc}")
        return 1
    path = write_baseline(repo_root, findings)
    print(f"{_PREFIX} recorded {len(findings)} finding(s) in {path.name}")
    print(f"{_PREFIX} commit this file; future scans will ignore those findings")
    return 0
