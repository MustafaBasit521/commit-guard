"""Tests for the pre-commit hook installer."""

import subprocess

import pytest

from git_security.installer import git_hook
from git_security.installer.dependencies import SCANNERS, check_dependencies

FOREIGN_HOOK = "#!/bin/sh\necho some other hook\n"


def test_hook_content_is_a_shell_script_with_our_marker():
    assert git_hook.HOOK_CONTENT.startswith("#!/bin/sh")
    assert git_hook.MARKER in git_hook.HOOK_CONTENT
    assert "git-security-tool scan" in git_hook.HOOK_CONTENT


def test_check_dependencies_reports_every_scanner():
    deps = check_dependencies()
    assert set(deps) == set(SCANNERS)
    assert all(isinstance(present, bool) for present in deps.values())


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _hook_path(repo):
    return repo / ".git" / "hooks" / "pre-commit"


def test_install_creates_an_executable_managed_hook(git_repo):
    assert git_hook.install() == 0
    hook = _hook_path(git_repo)
    assert hook.is_file()
    assert hook.stat().st_mode & 0o111  # at least one execute bit
    assert git_hook.MARKER in hook.read_text()


def test_install_refuses_foreign_hook_without_force(git_repo):
    hook = _hook_path(git_repo)
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(FOREIGN_HOOK)

    assert git_hook.install() == 1
    assert hook.read_text() == FOREIGN_HOOK  # untouched


def test_install_force_replaces_foreign_hook(git_repo):
    hook = _hook_path(git_repo)
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(FOREIGN_HOOK)

    assert git_hook.install(force=True) == 0
    assert git_hook.MARKER in hook.read_text()


def test_reinstall_over_our_own_hook_is_fine(git_repo):
    assert git_hook.install() == 0
    assert git_hook.install() == 0  # no --force needed


def test_uninstall_removes_our_hook(git_repo):
    git_hook.install()
    assert git_hook.uninstall() == 0
    assert not _hook_path(git_repo).exists()


def test_uninstall_leaves_foreign_hook_alone(git_repo):
    hook = _hook_path(git_repo)
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(FOREIGN_HOOK)

    assert git_hook.uninstall() == 1
    assert hook.exists()


def test_status_exit_code_tracks_installation(git_repo):
    assert git_hook.status() == 1  # not installed yet
    git_hook.install()
    assert git_hook.status() == 0
