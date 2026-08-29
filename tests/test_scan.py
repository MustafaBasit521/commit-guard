"""Tests for the scan pipeline: helpers plus end-to-end runs of run_scan()."""

import subprocess

import pytest

from git_security.config.loader import AIConfig
from git_security.models.finding import Finding, Severity
from git_security.scan import _copy_project_config, _run_ai_suggestions, run_scan

# --- _copy_project_config -------------------------------------------------------


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


# --- AI suggestion gating (never send secrets) --------------------------------


def _f(tool: str, file: str, sev: Severity = Severity.HIGH) -> Finding:
    return Finding(tool=tool, rule="R", severity=sev, file=file, line=1, message="m")


def test_ai_suggestions_skip_gitleaks_and_secret_files(monkeypatch, capsys):
    sent: list = []
    monkeypatch.setattr(
        "git_security.suggestions.llm.suggestions_available", lambda provider: True
    )
    monkeypatch.setattr(
        "git_security.suggestions.llm.explain",
        lambda items, config: sent.extend(items),
    )

    secret = _f("gitleaks", "config.py", Severity.CRITICAL)
    same_file = _f("semgrep", "config.py")  # shares a file with the secret
    other = _f("semgrep", "app.py")

    _run_ai_suggestions(
        [secret, same_file, other], [secret, same_file, other], AIConfig()
    )

    sent_files = {finding.file for finding, _snippet in sent}
    assert sent_files == {"app.py"}  # not config.py, not the gitleaks finding


# --- run_scan end to end -----------------------------------------------------


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_run_scan_allows_clean_commit(git_repo, capsys):
    (git_repo / "ok.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "ok.py"], cwd=git_repo, check=True)

    assert run_scan() == 0
    assert "commit allowed" in capsys.readouterr().out


def test_run_scan_blocks_on_eval(git_repo, capsys):
    (git_repo / "bad.py").write_text("eval(input())\n")
    subprocess.run(["git", "add", "bad.py"], cwd=git_repo, check=True)

    assert run_scan() == 1
    assert "python-dangerous-eval" in capsys.readouterr().out


def test_run_scan_blocks_on_yaml_load(git_repo, capsys):
    (git_repo / "cfg.py").write_text("import yaml\nyaml.load(open('c').read())\n")
    subprocess.run(["git", "add", "cfg.py"], cwd=git_repo, check=True)

    assert run_scan() == 1
    assert "python-yaml-unsafe-load" in capsys.readouterr().out


def test_run_scan_reports_config_error_cleanly(git_repo, capsys):
    (git_repo / "ok.py").write_text("x = 1\n")
    (git_repo / ".git-security-tool.toml").write_text(
        '[policy]\nblock_threshold="huh"\n'
    )
    subprocess.run(["git", "add", "ok.py"], cwd=git_repo, check=True)

    assert run_scan() == 1
    out = capsys.readouterr().out
    assert "config error" in out
    assert "Traceback" not in out


def test_run_scan_ignores_configured_paths(git_repo, capsys):
    (git_repo / "vendored").mkdir()
    (git_repo / "vendored" / "x.py").write_text("eval(input())\n")
    (git_repo / ".git-security-tool.toml").write_text('[ignore]\npaths=["vendored/"]\n')
    subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)

    assert run_scan() == 0


def _commit(repo, name, content):
    (repo / name).write_text(content)
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", name], cwd=repo, check=True)


def test_run_scan_all_passes_on_clean_repo(git_repo, capsys):
    _commit(git_repo, "ok.py", "x = 1\n")

    assert run_scan(scope="all") == 0
    assert "full security scan" in capsys.readouterr().out


def test_run_scan_all_fails_on_committed_eval(git_repo, capsys):
    _commit(git_repo, "bad.py", "eval(input())\n")

    assert run_scan(scope="all") == 1
    out = capsys.readouterr().out
    assert "python-dangerous-eval" in out
    assert "scan failed" in out


def test_run_scan_all_with_nothing_tracked(git_repo, capsys):
    assert run_scan(scope="all") == 0
    assert "no tracked files" in capsys.readouterr().out
