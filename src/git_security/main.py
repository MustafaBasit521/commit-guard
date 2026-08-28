"""Entry point for the git-security-tool pre-commit scan.

Milestone 4: run two real scanners over the staged changes - Ruff (Python
code quality) and Gitleaks (secrets) - and print what they find. Still no
policy: the exit code stays 0 regardless of findings.
"""

import sys

from git_security.git.diff import get_staged_diff, get_staged_files
from git_security.scanners.gitleaks import run_gitleaks
from git_security.scanners.ruff import run_ruff


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

    ruff_findings = run_ruff(staged_files)
    if ruff_findings:
        print(f"[git-security-tool] ruff: {len(ruff_findings)} issue(s)")
        for finding in ruff_findings:
            location = finding.get("location") or {}
            print(
                f"  {finding.get('filename')}:{location.get('row')} "
                f"{finding.get('code')} {finding.get('message')}"
            )
    else:
        print("[git-security-tool] ruff: no issues")

    leaks = run_gitleaks()
    if leaks:
        print(f"[git-security-tool] gitleaks: {len(leaks)} secret(s)")
        for leak in leaks:
            print(
                f"  {leak.get('File')}:{leak.get('StartLine')} "
                f"{leak.get('RuleID')} {leak.get('Description')}"
            )
    else:
        print("[git-security-tool] gitleaks: no secrets")

    print("[git-security-tool] policy not implemented yet - allowing commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
