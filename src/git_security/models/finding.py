"""The normalized finding model.

Every scanner converts its tool's native output into ``Finding`` objects.
From here on, the rest of git-security-tool (policy, reporting) deals only
with ``Finding`` - never a raw tool dict.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    tool: str       # scanner that produced it: "ruff", "gitleaks", ...
    rule: str       # tool-specific rule id: "F401", "aws-access-token", ...
    severity: str   # CRITICAL | HIGH | MEDIUM | LOW | INFO (provisional until M7)
    file: str       # repo-relative path
    line: int       # 1-based line number; 0 when the tool reports none
    message: str    # human-readable description
