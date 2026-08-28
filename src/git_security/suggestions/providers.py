"""LLM providers for remediation suggestions.

Each provider exposes the same tiny surface:

* ``name``            - identifier used in ``[ai] provider`` and in messages
* ``default_model``   - used when ``[ai] model`` is left blank
* ``env_var``         - the API-key environment variable
* ``available()``     - key present (and any SDK importable)
* ``complete(system, user, model) -> str`` - one call, text back,
  ``RuntimeError`` on any failure

This layer is advisory only. The deterministic scanners decide whether a
commit is blocked; providers just explain findings.
"""

import json
import os
import urllib.error
import urllib.request

_TIMEOUT = 30
_MAX_OUTPUT_TOKENS = 2048


class AnthropicProvider:
    name = "anthropic"
    default_model = "claude-opus-5"
    env_var = "ANTHROPIC_API_KEY"

    def available(self) -> bool:
        if not os.environ.get(self.env_var):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def complete(self, system: str, user: str, model: str) -> str:
        import anthropic

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model or self.default_model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AnthropicError as exc:
            raise RuntimeError(f"Anthropic API error: {exc}") from exc
        return "".join(b.text for b in response.content if b.type == "text")


class GeminiProvider:
    name = "gemini"
    default_model = "gemini-2.5-flash"
    env_var = "GEMINI_API_KEY"
    _URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent"
    )

    def available(self) -> bool:
        return bool(os.environ.get(self.env_var))

    def complete(self, system: str, user: str, model: str) -> str:
        url = self._URL.format(model=model or self.default_model)
        body = json.dumps(
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": _MAX_OUTPUT_TOKENS},
            }
        ).encode()
        request = urllib.request.Request(  # noqa: S310 - hardcoded https host
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": os.environ[self.env_var],
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT) as resp:  # noqa: S310
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        candidates = payload.get("candidates") or []
        if not candidates:
            reason = payload.get("promptFeedback", {}).get(
                "blockReason", "no candidates returned"
            )
            raise RuntimeError(f"Gemini returned nothing ({reason})")
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise RuntimeError(
                "Gemini response had no text "
                f"(finishReason={candidates[0].get('finishReason')})"
            )
        return text


PROVIDERS = {p.name: p for p in (AnthropicProvider(), GeminiProvider())}
