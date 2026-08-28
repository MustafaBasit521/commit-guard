"""Tests for scan-pipeline helpers that don't need real scanners."""

from git_security.scan import _copy_project_config


def test_copies_existing_config_files_only(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    (repo / "ruff.toml").write_text("line-length = 79\n")
    # setup.cfg deliberately absent

    dest = tmp_path / "staged"
    dest.mkdir()
    _copy_project_config(repo, dest)

    assert (dest / "pyproject.toml").read_text().startswith("[tool.ruff]")
    assert (dest / "ruff.toml").read_text() == "line-length = 79\n"
    assert not (dest / "setup.cfg").exists()


def test_noop_when_repo_has_no_config(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    dest = tmp_path / "staged"
    dest.mkdir()

    _copy_project_config(repo, dest)

    assert list(dest.iterdir()) == []
