"""Tests for LLM providers - Gemini response handling is mocked, no network."""

import io
import json
import urllib.error

import pytest

from git_security.suggestions.providers import PROVIDERS, GeminiProvider


class _FakeResponse:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(monkeypatch, payload: dict):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _FakeResponse(payload),
    )


def test_registry_has_both_providers():
    assert set(PROVIDERS) == {"anthropic", "gemini"}


def test_gemini_available_reflects_key(monkeypatch):
    provider = GeminiProvider()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert provider.available() is False
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert provider.available() is True


def test_gemini_complete_returns_text(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    _patch_urlopen(
        monkeypatch,
        {
            "candidates": [
                {"content": {"parts": [{"text": "use parameterized queries"}]}}
            ]
        },
    )
    out = GeminiProvider().complete("sys", "user", "gemini-3.6-flash")
    assert out == "use parameterized queries"


def test_gemini_complete_raises_when_blocked(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    _patch_urlopen(monkeypatch, {"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(RuntimeError, match="SAFETY"):
        GeminiProvider().complete("sys", "user", "gemini-3.6-flash")


def test_gemini_complete_wraps_http_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    def _raise(request, timeout):
        raise urllib.error.HTTPError(
            "url", 400, "Bad Request", {}, io.BytesIO(b'{"error": "bad key"}')
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    with pytest.raises(RuntimeError, match="Gemini API error 400"):
        GeminiProvider().complete("sys", "user", "gemini-3.6-flash")
