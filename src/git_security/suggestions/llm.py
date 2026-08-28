"""Optional AI remediation suggestions.

Off by default. Runs only when *all* of these hold:

* ``[ai] enabled = true`` in ``.git-security-tool.toml``
* ``ANTHROPIC_API_KEY`` is set in the environment
* the ``anthropic`` package is installed (``pip install 'git-security-tool[ai]'``)

It never modifies files - it prints suggestions for the developer to apply
by hand - and it always announces before sending code off the machine.
"""

import os

from git_security.models.finding import Finding

_PREFIX = "[git-security-tool]"

_SYSTEM = (
    "You are a security code-review assistant. You are given one static-analysis "
    "finding and the surrounding code. Reply with exactly two parts: "
    "(1) one sentence naming the risk, then "
    "(2) a minimal safe rewrite of only the affected lines, in a code block. "
    "No preamble, no extra commentary."
)


def suggestions_available() -> bool:
    """True if an API key is present and the anthropic SDK is importable."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def build_prompt(finding: Finding, snippet: str) -> str:
    return (
        f"Finding: {finding.tool}:{finding.rule} [{finding.severity.name}]\n"
        f"Location: {finding.file}:{finding.line}\n"
        f"Message: {finding.message}\n\n"
        f"Code:\n{snippet}"
    )


def explain(items: list[tuple[Finding, str]], model: str) -> None:
    """Print an AI suggestion for each (finding, code snippet) pair."""
    import anthropic

    print(
        f"{_PREFIX} sending {len(items)} finding(s) and code context to the "
        f"Anthropic API ({model}) for remediation suggestions..."
    )
    client = anthropic.Anthropic()

    for finding, snippet in items:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=_SYSTEM,
                messages=[{"role": "user", "content": build_prompt(finding, snippet)}],
            )
        except anthropic.AnthropicError as exc:
            print(f"{_PREFIX} suggestion failed for {finding.file}: {exc}")
            continue

        text = "".join(b.text for b in response.content if b.type == "text")
        print(
            f"\n{_PREFIX} suggestion for {finding.file}:{finding.line} "
            f"({finding.tool}:{finding.rule}):"
        )
        for line in text.strip().splitlines():
            print(f"    {line}")
    print()
