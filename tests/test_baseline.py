"""Tests for baseline suppression."""

from git_security.baseline import (
    BASELINE_FILENAME,
    apply_baseline,
    load_baseline,
    write_baseline,
)
from git_security.models.finding import Finding, Severity


def _f(rule: str, file: str = "a.py", line: int = 1, msg: str = "m") -> Finding:
    return Finding(
        tool="semgrep",
        rule=rule,
        severity=Severity.HIGH,
        file=file,
        line=line,
        message=msg,
    )


def test_no_baseline_file_is_empty_set(tmp_path):
    assert load_baseline(tmp_path) == set()


def test_write_then_load_roundtrip(tmp_path):
    findings = [_f("eval"), _f("pickle", file="b.py")]
    path = write_baseline(tmp_path, findings)

    assert path.name == BASELINE_FILENAME
    loaded = load_baseline(tmp_path)
    assert ("semgrep", "eval", "a.py", "m") in loaded
    assert ("semgrep", "pickle", "b.py", "m") in loaded


def test_apply_baseline_suppresses_known_but_not_new(tmp_path):
    write_baseline(tmp_path, [_f("eval")])
    baseline = load_baseline(tmp_path)

    kept, suppressed = apply_baseline([_f("eval"), _f("exec")], baseline)

    assert suppressed == 1
    assert [f.rule for f in kept] == ["exec"]


def test_baseline_is_line_independent(tmp_path):
    write_baseline(tmp_path, [_f("eval", line=10)])
    baseline = load_baseline(tmp_path)

    # same finding, different line -> still suppressed
    kept, suppressed = apply_baseline([_f("eval", line=42)], baseline)
    assert suppressed == 1
    assert kept == []


def test_corrupt_baseline_file_is_ignored(tmp_path):
    (tmp_path / BASELINE_FILENAME).write_text("{ not json")
    assert load_baseline(tmp_path) == set()
