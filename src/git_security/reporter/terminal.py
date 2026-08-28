"""Turn a policy Decision into human-readable terminal output.

All the "how do we present findings" logic lives here, so ``main()`` only
has to orchestrate and pick an exit code. A JSON / SARIF reporter for CI can
be added alongside this without touching ``main()``.
"""

from git_security.models.finding import Finding
from git_security.policy.engine import Decision

_PREFIX = "[git-security-tool]"
_MESSAGE_LIMIT = 120


def report(decision: Decision) -> None:
    """Print warnings, then blocking findings, then a one-line summary."""
    if not decision.warnings and not decision.blocking:
        print(f"{_PREFIX} no findings")
        return

    if decision.warnings:
        _section("warning(s), do not block", decision.warnings)
    if decision.blocking:
        _section("blocking finding(s)", decision.blocking)

    print(
        f"{_PREFIX} summary: {len(decision.blocking)} blocking, "
        f"{len(decision.warnings)} warning(s)"
    )


def _section(title: str, findings: list[Finding]) -> None:
    print(f"{_PREFIX} {len(findings)} {title}:")
    for f in sorted(findings, key=lambda x: (x.file, x.line, x.tool)):
        print(
            f"  [{f.severity.name}] {f.tool}:{f.rule} "
            f"{f.file}:{f.line} - {_one_line(f.message)}"
        )


def _one_line(message: str, limit: int = _MESSAGE_LIMIT) -> str:
    """Collapse whitespace/newlines and truncate long messages."""
    message = " ".join(message.split())
    if len(message) <= limit:
        return message
    return message[: limit - 1] + "…"
