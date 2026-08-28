"""Tests for the .git-security-tool.toml loader."""

import pytest

from git_security.config.loader import CONFIG_FILENAME, ConfigError, load_config
from git_security.models.finding import Severity


def write_config(repo: object, text: str) -> None:
    (repo / CONFIG_FILENAME).write_text(text)


def test_no_file_gives_defaults(tmp_path):
    config = load_config(tmp_path)
    assert config.policy.block_threshold is Severity.HIGH
    assert config.enabled_scanners == frozenset({"ruff", "gitleaks", "semgrep"})


def test_block_threshold_is_read_case_insensitively(tmp_path):
    write_config(tmp_path, '[policy]\nblock_threshold = "critical"\n')
    config = load_config(tmp_path)
    assert config.policy.block_threshold is Severity.CRITICAL


def test_invalid_block_threshold_raises(tmp_path):
    write_config(tmp_path, '[policy]\nblock_threshold = "spicy"\n')
    with pytest.raises(ConfigError, match="block_threshold"):
        load_config(tmp_path)


def test_malformed_toml_raises_config_error(tmp_path):
    write_config(tmp_path, "this is not = valid toml [[[")
    with pytest.raises(ConfigError, match=CONFIG_FILENAME):
        load_config(tmp_path)


def test_scanner_can_be_disabled(tmp_path):
    write_config(tmp_path, "[scanners]\ngitleaks = false\n")
    config = load_config(tmp_path)
    assert "gitleaks" not in config.enabled_scanners
    assert "ruff" in config.enabled_scanners
    assert "semgrep" in config.enabled_scanners


def test_partial_config_keeps_other_defaults(tmp_path):
    write_config(tmp_path, '[policy]\nblock_threshold = "MEDIUM"\n')
    config = load_config(tmp_path)
    assert config.policy.block_threshold is Severity.MEDIUM
    assert config.enabled_scanners == frozenset({"ruff", "gitleaks", "semgrep"})


def test_scanner_set_to_true_stays_enabled(tmp_path):
    write_config(tmp_path, "[scanners]\nruff = true\n")
    config = load_config(tmp_path)
    assert "ruff" in config.enabled_scanners


def test_ignore_paths_are_loaded(tmp_path):
    write_config(tmp_path, '[ignore]\npaths = ["tests/fixtures/", "*.gen.py"]\n')
    config = load_config(tmp_path)
    assert config.ignore_paths == ("tests/fixtures/", "*.gen.py")


def test_ignore_paths_default_empty(tmp_path):
    assert load_config(tmp_path).ignore_paths == ()


def test_ignore_paths_must_be_list_of_strings(tmp_path):
    write_config(tmp_path, '[ignore]\npaths = "nope"\n')
    with pytest.raises(ConfigError, match="ignore.paths"):
        load_config(tmp_path)


def test_ai_defaults_are_off(tmp_path):
    ai = load_config(tmp_path).ai
    assert ai.enabled is False
    assert ai.provider == "anthropic"
    assert ai.model == ""
    assert ai.max_findings == 3


def test_ai_config_is_read(tmp_path):
    write_config(
        tmp_path,
        '[ai]\nenabled = true\nprovider = "gemini"\n'
        'model = "gemini-2.5-pro"\nmax_findings = 1\n',
    )
    ai = load_config(tmp_path).ai
    assert ai.enabled is True
    assert ai.provider == "gemini"
    assert ai.model == "gemini-2.5-pro"
    assert ai.max_findings == 1


def test_ai_provider_must_be_known(tmp_path):
    write_config(tmp_path, '[ai]\nprovider = "openai"\n')
    with pytest.raises(ConfigError, match="ai.provider"):
        load_config(tmp_path)


def test_ai_max_findings_must_be_positive_int(tmp_path):
    write_config(tmp_path, "[ai]\nmax_findings = 0\n")
    with pytest.raises(ConfigError, match="ai.max_findings"):
        load_config(tmp_path)
