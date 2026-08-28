"""Entry point for the git-security-tool pre-commit scan.

Milestone 7: findings now pass through the policy engine, which decides
allow vs block. The exit code finally reflects that decision - a blocking
finding aborts the commit.

Escape hatch while developing: set GIT_SECURITY_NO_BLOCK=1 to report
findings but never block.
"""

import os
import sys

from git_security.git.diff import get_staged_diff, get_staged_files
from git_security.git.repository import get_repo_root
from git_security.models.finding import Finding
from git_security.policy.engine import PolicyConfig, evaluate
from git_security.scanners.gitleaks import run_gitleaks
from git_security.scanners.ruff import run_ruff
from git_security.scanners.semgrep import run_semgrep


def _print_findings(label: str, findings: list[Finding]) -> None:
    print(f"[git-security-tool] {len(findings)} {label}:")
    for f in findings:
        print(
            f"  [{f.severity.name}] {f.tool}:{f.rule} "
            f"{f.file}:{f.line} - {f.message}"
        )


def main() -> int:
    print("[git-security-tool] pre-commit security scan")

    staged_files = get_staged_files()
    if not staged_files:
        print("[git-security-tool] nothing staged - allowing commit")
        return 0

    print(f"[git-security-tool] {len(staged_files)} file(s) staged:")
    for path in staged_files:
        print(f"  - {path}")

    diff = get_staged_diff()
    print(f"[git-security-tool] staged diff: {len(diff.splitlines())} lines")

    repo_root = get_repo_root()
    rules_dir = repo_root / "rules" / "semgrep"

    findings: list[Finding] = []
    findings += run_ruff(staged_files, repo_root)
    findings += run_gitleaks()
    findings += run_semgrep(staged_files, repo_root, rules_dir)

    decision = evaluate(findings, PolicyConfig())

    if not findings:
        print("[git-security-tool] no findings - commit allowed")
        return 0

    if decision.warnings:
        _print_findings("warning(s)", decision.warnings)
    if decision.blocking:
        _print_findings("blocking finding(s)", decision.blocking)

    if not decision.blocked:
        print("[git-security-tool] no blocking findings - commit allowed")
        return 0

    if os.environ.get("GIT_SECURITY_NO_BLOCK") == "1":
        print(
            "[git-security-tool] would block, but GIT_SECURITY_NO_BLOCK=1 "
            "is set - commit allowed"
        )
        return 0

    print(
        "[git-security-tool] commit blocked - fix the blocking findings above, "
        "or set GIT_SECURITY_NO_BLOCK=1 to override"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
