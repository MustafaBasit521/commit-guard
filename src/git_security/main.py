"""Entry point for the git-security-tool pre-commit scan.

Milestone 1: prove the pre-commit hook can run this program and that our
exit code controls whether the commit is allowed (0) or blocked (non-zero).
No real checks yet.
"""

import sys


def main() -> int:
    print("[git-security-tool] running pre-commit security scan...")
    print("[git-security-tool] no checks implemented yet - allowing commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
