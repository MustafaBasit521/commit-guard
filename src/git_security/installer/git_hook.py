"""Install, remove, and report on the git-security-tool pre-commit hook.

The hook itself is tiny and lives in ``.git/hooks/`` (not version-controlled),
so every repo needs this command to set it up. We only ever touch a hook we
created - identified by MARKER - unless the user passes --force.
"""

import stat
from pathlib import Path

from git_security.git.hooks import pre_commit_hook
from git_security.git.repository import run_git
from git_security.installer.dependencies import check_dependencies

_PREFIX = "[git-security-tool]"

MARKER = "git-security-tool managed hook"

HOOK_CONTENT = f"""\
#!/bin/sh
# {MARKER} - do not edit; regenerate with `git-security-tool install`
if ! command -v git-security-tool >/dev/null 2>&1; then
    echo "git-security-tool not on PATH - skipping scan (is your venv active?)" >&2
    exit 0
fi
exec git-security-tool scan
"""

_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def _inside_work_tree() -> bool:
    try:
        return run_git(["rev-parse", "--is-inside-work-tree"]).strip() == "true"
    except RuntimeError:
        return False


def _is_ours(path: Path) -> bool:
    try:
        return path.is_file() and MARKER in path.read_text()
    except (OSError, UnicodeDecodeError):
        return False


def _print_dependencies() -> None:
    deps = check_dependencies()
    for name, present in deps.items():
        print(f"  {name}: {'ok' if present else 'missing'}")
    if not all(deps.values()):
        print(
            f"{_PREFIX} missing scanners are skipped at scan time; "
            "install them for full coverage"
        )


def install(force: bool = False) -> int:
    if not _inside_work_tree():
        print(f"{_PREFIX} not inside a Git repository")
        return 1

    hook = pre_commit_hook()
    hook.parent.mkdir(parents=True, exist_ok=True)

    if hook.exists() and not _is_ours(hook) and not force:
        print(
            f"{_PREFIX} a pre-commit hook already exists at {hook} and was not "
            f"created by git-security-tool.\n"
            f"{_PREFIX} re-run with --force to replace it."
        )
        return 1

    hook.write_text(HOOK_CONTENT)
    hook.chmod(hook.stat().st_mode | _EXEC_BITS)
    print(f"{_PREFIX} installed pre-commit hook at {hook}")
    _print_dependencies()
    return 0


def uninstall() -> int:
    if not _inside_work_tree():
        print(f"{_PREFIX} not inside a Git repository")
        return 1

    hook = pre_commit_hook()
    if not hook.exists():
        print(f"{_PREFIX} no pre-commit hook to remove")
        return 0
    if not _is_ours(hook):
        print(
            f"{_PREFIX} pre-commit hook at {hook} was not created by "
            "git-security-tool - leaving it alone"
        )
        return 1

    hook.unlink()
    print(f"{_PREFIX} removed pre-commit hook at {hook}")
    return 0


def status() -> int:
    if not _inside_work_tree():
        print(f"{_PREFIX} not inside a Git repository")
        return 1

    hook = pre_commit_hook()
    if _is_ours(hook):
        print(f"{_PREFIX} pre-commit hook: installed ({hook})")
        installed = True
    elif hook.exists():
        print(
            f"{_PREFIX} pre-commit hook: present but not managed by "
            f"git-security-tool ({hook})"
        )
        installed = False
    else:
        print(f"{_PREFIX} pre-commit hook: not installed")
        installed = False

    print(f"{_PREFIX} scanners:")
    _print_dependencies()
    return 0 if installed else 1
