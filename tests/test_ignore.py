"""Tests for path ignore matching."""

from git_security.ignore import filter_ignored, is_ignored


def test_directory_pattern_matches_contents():
    patterns = ("tests/fixtures/",)
    assert is_ignored("tests/fixtures/sample.py", patterns)
    assert is_ignored("tests/fixtures/deep/nested.py", patterns)
    assert not is_ignored("tests/test_real.py", patterns)


def test_glob_pattern_matches_by_suffix():
    patterns = ("*.generated.py",)
    assert is_ignored("src/pkg/models.generated.py", patterns)
    assert not is_ignored("src/pkg/models.py", patterns)


def test_plain_name_matches_path_and_subtree():
    patterns = ("migrations",)
    assert is_ignored("migrations", patterns)
    assert is_ignored("migrations/0001_initial.py", patterns)
    assert not is_ignored("app/migrations_helper.py", patterns)


def test_no_patterns_ignores_nothing():
    assert filter_ignored(["a.py", "b.py"], ()) == ["a.py", "b.py"]


def test_filter_removes_only_matches():
    files = ["src/app.py", "tests/fixtures/x.py", "vendor/lib.py"]
    patterns = ("tests/fixtures/", "vendor/")
    assert filter_ignored(files, patterns) == ["src/app.py"]
