"""Locate this repository's hooks directory and its pre-commit hook.

Git's hooks directory is usually ``.git/hooks`` but can be moved with the
``core.hooksPath`` config or differ inside worktrees. ``git rev-parse
--git-path hooks`` resolves all of that for us.
"""

from pathlib import Path

from git_security.git.repository import run_git


def hooks_dir() -> Path:
    """Absolute path to the hooks directory Git will actually use."""
    raw = run_git(["rev-parse", "--git-path", "hooks"]).strip()
    path = Path(raw)
    if not path.is_absolute():
        top = run_git(["rev-parse", "--show-toplevel"]).strip()
        path = Path(top) / path
    return path


def pre_commit_hook() -> Path:
    """Absolute path to this repository's ``pre-commit`` hook file."""
    return hooks_dir() / "pre-commit"
