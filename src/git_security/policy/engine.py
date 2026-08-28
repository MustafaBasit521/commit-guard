"""Turn a list of findings into an allow/block decision.

The policy layer is the *only* place that decides whether the commit should
proceed. Scanners just report; ``main()`` just obeys the returned Decision.
Keeping the rule here means we can change blocking behaviour without touching
any scanner.
"""

from dataclasses import dataclass, field

from git_security.models.finding import Finding, Severity

# Severities that abort the commit. Anything below this is shown as a warning
# but does not block. Made configurable from a file in a later milestone.
DEFAULT_BLOCK_THRESHOLD = Severity.HIGH


@dataclass(frozen=True)
class PolicyConfig:
    block_threshold: Severity = DEFAULT_BLOCK_THRESHOLD


@dataclass
class Decision:
    blocked: bool
    blocking: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)


def evaluate(findings: list[Finding], config: PolicyConfig) -> Decision:
    """Split findings into blocking vs warning by severity threshold."""
    blocking = [f for f in findings if f.severity >= config.block_threshold]
    warnings = [f for f in findings if f.severity < config.block_threshold]
    return Decision(
        blocked=bool(blocking),
        blocking=blocking,
        warnings=warnings,
    )
