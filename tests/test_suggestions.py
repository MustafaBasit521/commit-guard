"""Tests for the optional AI suggestion layer (no real API calls)."""

import sys

from git_security.models.finding import Finding, Severity
from git_security.suggestions.llm import build_prompt, suggestions_available

FINDING = Finding(
    tool="semgrep",
    rule="python-dangerous-eval",
    severity=Severity.HIGH,
    file="app.py",
    line=4,
    message="eval() executes arbitrary code",
)


def test_unknown_provider_is_unavailable():
    assert suggestions_available("openai") is False


def test_anthropic_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert suggestions_available("anthropic") is False


def test_anthropic_unavailable_when_sdk_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setitem(sys.modules, "anthropic", None)  # forces ImportError
    assert suggestions_available("anthropic") is False


def test_gemini_available_with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert suggestions_available("gemini") is True


def test_gemini_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert suggestions_available("gemini") is False


def test_build_prompt_includes_finding_and_code():
    prompt = build_prompt(FINDING, "3: x = 1\n4: eval(x)")
    assert "semgrep:python-dangerous-eval" in prompt
    assert "app.py:4" in prompt
    assert "eval() executes arbitrary code" in prompt
    assert "4: eval(x)" in prompt
