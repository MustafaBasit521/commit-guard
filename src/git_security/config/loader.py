"""Load repo-level configuration from ``.git-security-tool.toml``.

The file is optional. When it is absent - or a key within it is missing -
the built-in defaults apply. Parsing uses ``tomllib`` from the standard
library (Python 3.11+), so this adds no dependency.

A malformed file raises :class:`ConfigError`; callers turn that into a clean
message rather than a traceback.

Example ``.git-security-tool.toml`` at the repo root::

    [policy]
    block_threshold = "CRITICAL"   # INFO | LOW | MEDIUM | HIGH | CRITICAL

    [scanners]
    gitleaks = false               # disable a scanner

    [ignore]
    paths = ["tests/fixtures/", "*.generated.py"]

    [ai]
    enabled = true                 # off by default; also needs ANTHROPIC_API_KEY
    model = "claude-opus-5"
    max_findings = 3
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from git_security.models.finding import Severity
from git_security.policy.engine import PolicyConfig

CONFIG_FILENAME = ".git-security-tool.toml"

_ALL_SCANNERS = ("ruff", "gitleaks", "semgrep")


class ConfigError(Exception):
    """Raised when ``.git-security-tool.toml`` is present but malformed."""


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    model: str = "claude-opus-5"
    max_findings: int = 3


@dataclass(frozen=True)
class Config:
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    enabled_scanners: frozenset[str] = frozenset(_ALL_SCANNERS)
    ignore_paths: tuple[str, ...] = ()
    ai: AIConfig = field(default_factory=AIConfig)


def load_config(repo_root: Path) -> Config:
    """Read ``.git-security-tool.toml`` from *repo_root*, or return defaults."""
    path = repo_root / CONFIG_FILENAME
    if not path.is_file():
        return Config()

    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"could not read {CONFIG_FILENAME}: {exc}") from exc

    return Config(
        policy=_load_policy(raw.get("policy", {})),
        enabled_scanners=_load_scanners(raw.get("scanners", {})),
        ignore_paths=_load_ignore(raw.get("ignore", {})),
        ai=_load_ai(raw.get("ai", {})),
    )


def _load_policy(section: dict) -> PolicyConfig:
    name = section.get("block_threshold")
    if name is None:
        return PolicyConfig()
    try:
        threshold = Severity[name.upper()]
    except (KeyError, AttributeError):
        valid = ", ".join(s.name for s in Severity)
        raise ConfigError(
            f"invalid policy.block_threshold: {name!r} (expected one of {valid})"
        ) from None
    return PolicyConfig(block_threshold=threshold)


def _load_scanners(section: dict) -> frozenset[str]:
    enabled = set(_ALL_SCANNERS)
    for name in _ALL_SCANNERS:
        if section.get(name) is False:
            enabled.discard(name)
    return frozenset(enabled)


def _load_ignore(section: dict) -> tuple[str, ...]:
    paths = section.get("paths", [])
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise ConfigError("ignore.paths must be a list of strings")
    return tuple(paths)


def _load_ai(section: dict) -> AIConfig:
    model = section.get("model", "claude-opus-5")
    max_findings = section.get("max_findings", 3)
    if not isinstance(model, str):
        raise ConfigError("ai.model must be a string")
    if isinstance(max_findings, bool) or not isinstance(max_findings, int):
        raise ConfigError("ai.max_findings must be an integer")
    if max_findings < 1:
        raise ConfigError("ai.max_findings must be >= 1")
    return AIConfig(
        enabled=section.get("enabled", False) is True,
        model=model,
        max_findings=max_findings,
    )
