"""Tests for staged-content queries, especially materialize_staged."""

import subprocess

import pytest

from git_security.git.diff import get_staged_files, materialize_staged


@pytest.fixture
def repo(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_get_staged_files_lists_added_paths(repo):
    (repo / "a.py").write_text("x = 1\n")
    (repo / "b.py").write_text("y = 2\n")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)

    assert get_staged_files() == ["a.py"]  # b.py not staged


def test_materialize_uses_staged_content_not_working_tree(repo):
    target = repo / "a.py"
    target.write_text("STAGED\n")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
    target.write_text("WORKING TREE EDIT\n")  # diverge after `git add`

    dest = repo / "out"
    dest.mkdir()
    materialize_staged(["a.py"], dest)

    assert (dest / "a.py").read_text() == "STAGED\n"


def test_materialize_recreates_subdirectories(repo):
    (repo / "pkg").mkdir()
    (repo / "pkg" / "m.py").write_text("z = 3\n")
    subprocess.run(["git", "add", "pkg/m.py"], cwd=repo, check=True)

    dest = repo / "out"
    dest.mkdir()
    materialize_staged(["pkg/m.py"], dest)

    assert (dest / "pkg" / "m.py").read_text() == "z = 3\n"


def test_materialize_empty_list_is_a_noop(repo):
    dest = repo / "out"
    dest.mkdir()
    materialize_staged([], dest)
    assert list(dest.iterdir()) == []
