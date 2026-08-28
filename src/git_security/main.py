"""Entry point for the git-security-tool pre-commit scan.

Milestone 2: use subprocess (via the git/ package) to capture what is
actually staged for the commit and print a summary. Still no real checks -
the exit code stays 0.
"""

import sys

from git_security.git.diff import get_staged_diff, get_staged_files


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

    print("[git-security-tool] no checks implemented yet - allowing commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
