"""Load repo-level configuration from ``.git-security-tool.toml``.

The file is optional. When it is absent - or a key within it is missing -
the built-in defaults apply. Parsing uses ``tomllib`` from the standard
library (Python 3.11+), so this adds no dependency.

Example ``.git-security-tool.toml`` at the repo root::

    [policy]
    block_threshold = "CRITICAL"   # INFO | LOW | MEDIUM | HIGH | CRITICAL

    [scanners]
    gitleaks = false               # disable a scanner
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from git_security.models.finding import Severity
from git_security.policy.engine import PolicyConfig

CONFIG_FILENAME = ".git-security-tool.toml"

_ALL_SCANNERS = ("ruff", "gitleaks", "semgrep")


@dataclass(frozen=True)
class Config:
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    enabled_scanners: frozenset[str] = frozenset(_ALL_SCANNERS)


def load_config(repo_root: Path) -> Config:
    """Read ``.git-security-tool.toml`` from *repo_root*, or return defaults."""
    path = repo_root / CONFIG_FILENAME
    if not path.is_file():
        return Config()

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    return Config(
        policy=_load_policy(raw.get("policy", {})),
        enabled_scanners=_load_scanners(raw.get("scanners", {})),
    )


def _load_policy(section: dict) -> PolicyConfig:
    name = section.get("block_threshold")
    if name is None:
        return PolicyConfig()
    try:
        threshold = Severity[name.upper()]
    except (KeyError, AttributeError):
        valid = ", ".join(s.name for s in Severity)
        raise ValueError(
            f"invalid policy.block_threshold: {name!r} (expected one of {valid})"
        )
    return PolicyConfig(block_threshold=threshold)


def _load_scanners(section: dict) -> frozenset[str]:
    enabled = set(_ALL_SCANNERS)
    for name in _ALL_SCANNERS:
        if section.get(name) is False:
            enabled.discard(name)
    return frozenset(enabled)
