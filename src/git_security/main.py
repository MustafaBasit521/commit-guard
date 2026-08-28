"""Entry point for the git-security-tool pre-commit scan.

Milestone 6: three scanners now - Ruff (Python quality), Gitleaks (secrets),
Semgrep (static-analysis security rules). All return normalized ``Finding``
objects into one list. Still no policy - the exit code stays 0.
"""

import sys

from git_security.git.diff import get_staged_diff, get_staged_files
from git_security.git.repository import get_repo_root
from git_security.models.finding import Finding
from git_security.scanners.gitleaks import run_gitleaks
from git_security.scanners.ruff import run_ruff
from git_security.scanners.semgrep import run_semgrep


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

    if findings:
        print(f"[git-security-tool] {len(findings)} finding(s):")
        for finding in findings:
            print(
                f"  [{finding.severity}] {finding.tool}:{finding.rule} "
                f"{finding.file}:{finding.line} - {finding.message}"
            )
    else:
        print("[git-security-tool] no findings")

    print("[git-security-tool] policy not implemented yet - allowing commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
