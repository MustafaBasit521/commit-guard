"""Read what is currently staged for the next commit.

Thin queries on top of :func:`git_security.git.repository.run_git`. Milestone
2 only needs to *see* what the commit will contain, so there is no parsing of
diff contents here.
"""

from git_security.git.repository import run_git


def get_staged_files() -> list[str]:
    """Return the paths staged for the next commit.

    ``--diff-filter=ACM`` keeps Added / Copied / Modified files and drops
    deletions, since there is nothing to scan in a file being removed.
    """
    output = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"])
    return [line for line in output.splitlines() if line]


def get_staged_diff() -> str:
    """Return the full unified diff of everything staged for the next commit."""
    return run_git(["diff", "--cached"])
