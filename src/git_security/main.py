"""Entry point for the git-security-tool pre-commit scan.

Milestone 8: presentation moved to reporter/terminal.py. main() now only
orchestrates - gather findings, evaluate policy, report, pick an exit code.

Escape hatch while developing: set GIT_SECURITY_NO_BLOCK=1 to report
findings but never block.
"""

import os
import sys

from git_security.git.diff import get_staged_diff, get_staged_files
from git_security.git.repository import get_repo_root
from git_security.models.finding import Finding
from git_security.policy.engine import PolicyConfig, evaluate
from git_security.reporter.terminal import report
from git_security.scanners.gitleaks import run_gitleaks
from git_security.scanners.ruff import run_ruff
from git_security.scanners.semgrep import run_semgrep

_PREFIX = "[git-security-tool]"


def main() -> int:
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
    rules_dir = repo_root / "rules" / "semgrep"

    findings: list[Finding] = []
    findings += run_ruff(staged_files, repo_root)
    findings += run_gitleaks()
    findings += run_semgrep(staged_files, repo_root, rules_dir)

    decision = evaluate(findings, PolicyConfig())
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


if __name__ == "__main__":
    sys.exit(main())
