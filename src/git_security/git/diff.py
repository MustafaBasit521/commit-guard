"""Read what is currently staged for the next commit.

Thin queries on top of :func:`git_security.git.repository.run_git`, plus
:func:`materialize_staged` which writes the exact staged content to disk so
scanners analyse what will be committed rather than the working tree.
"""

from pathlib import Path

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


def get_staged_file_content(path: str) -> str:
    """Return the staged (index) content of a single file as text."""
    return run_git(["show", f":{path}"])


def materialize_staged(files: list[str], dest: Path) -> None:
    """Write the staged (index) content of *files* under *dest*.

    Relative paths are preserved and missing sub-directories are created.
    This is the staged blob - the exact bytes that will be committed - not
    the working-tree copy, which may have diverged since ``git add``.
    *dest* must already exist.
    """
    if not files:
        return
    # --prefix is prepended literally, so it must end with a separator.
    prefix = f"{dest}/"
    run_git(["checkout-index", f"--prefix={prefix}", "--", *files])
