"""Optional AI remediation suggestions - advisory, never changes the block.

Runs only when all of these hold:

* ``[ai] enabled = true`` in ``.git-security-tool.toml``
* the configured provider's API key is set (``ANTHROPIC_API_KEY`` /
  ``GEMINI_API_KEY``)
* for the anthropic provider, the ``anthropic`` package is installed

It never modifies files - it prints suggestions for the developer - and it
always announces before sending code off the machine. Secret-bearing files
are filtered out before this module is reached (see ``scan.py``).
"""

from git_security.config.loader import AIConfig
from git_security.models.finding import Finding
from git_security.suggestions.providers import PROVIDERS

_PREFIX = "[git-security-tool]"

_SYSTEM = (
    "You are a security code-review assistant. You are given one static-analysis "
    "finding and the surrounding code. Reply with exactly two parts: "
    "(1) one sentence naming the risk, then "
    "(2) a minimal safe rewrite of only the affected lines, in a code block. "
    "No preamble, no extra commentary."
)


def suggestions_available(provider_name: str) -> bool:
    provider = PROVIDERS.get(provider_name)
    return provider is not None and provider.available()


def build_prompt(finding: Finding, snippet: str) -> str:
    return (
        f"Finding: {finding.tool}:{finding.rule} [{finding.severity.name}]\n"
        f"Location: {finding.file}:{finding.line}\n"
        f"Message: {finding.message}\n\n"
        f"Code:\n{snippet}"
    )


def explain(items: list[tuple[Finding, str]], config: AIConfig) -> None:
    """Print a suggestion for each (finding, code snippet) pair."""
    provider = PROVIDERS[config.provider]
    model = config.model or provider.default_model

    print(
        f"{_PREFIX} sending {len(items)} finding(s) and code context to "
        f"{provider.name} ({model}) for remediation suggestions..."
    )

    for finding, snippet in items:
        try:
            text = provider.complete(_SYSTEM, build_prompt(finding, snippet), model)
        except RuntimeError as exc:
            print(f"{_PREFIX} suggestion failed for {finding.file}: {exc}")
            continue

        print(
            f"\n{_PREFIX} suggestion for {finding.file}:{finding.line} "
            f"({finding.tool}:{finding.rule}):"
        )
        for line in text.strip().splitlines():
            print(f"    {line}")
    print()
