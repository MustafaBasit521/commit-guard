# git-security-tool

A local Git **pre-commit gate** for Linux. It scans your *staged* changes and
blocks the commit when it finds something serious — secrets, dangerous code
patterns — while surfacing quality and formatting issues as warnings.

It is an **orchestration layer**, not a new scanner: it runs
[Gitleaks](https://github.com/gitleaks/gitleaks),
[Semgrep](https://semgrep.dev/), and [Ruff](https://docs.astral.sh/ruff/),
normalizes their output, applies your policy, and decides pass/block.

```
git commit
   └─► .git/hooks/pre-commit
        └─► git-security-tool scan
             ├─ gitleaks   → secrets            (CRITICAL → blocks)
             ├─ semgrep    → security patterns  (HIGH → blocks)
             ├─ ruff check → lint               (LOW → warns)
             └─ ruff format --check → format    (LOW → warns)
                  └─► PASS (exit 0) / BLOCK (exit 1)
```

## Install

```bash
pip install -e ".[scanners]"     # the tool + ruff + semgrep
cd your-repo
git-security-tool install         # writes .git/hooks/pre-commit
```

Gitleaks is a Go binary — install it separately if you want secret detection
(the scan skips any tool that isn't on `PATH`).

Commands: `scan`, `install [--force]`, `uninstall`, `check`, `version`.

## What it checks

| category | tool | severity | blocks by default |
|---|---|---|---|
| Secrets / credentials | Gitleaks (staged diff) | CRITICAL | yes |
| Insecure code patterns (17 rules) | Semgrep + bundled rules | HIGH / MEDIUM | HIGH yes |
| Lint (unused imports, undefined names, …) | `ruff check` | LOW | no |
| Formatting | `ruff format --check` | LOW | no |

The bundled Semgrep rules (`src/git_security/rules/semgrep/`) cover code/command
injection (`eval`, `exec`, `os.system`, `shell=True`), unsafe deserialization
(`pickle`, `yaml.load`, insecure XML), weak crypto & disabled TLS verification,
web footguns (Flask `debug=True`, Jinja autoescape off, `mark_safe`), and
filesystem/network hygiene (`extractall`, `mktemp`, `requests` without timeout).

Semgrep/Ruff analysis is **Python only**; Gitleaks is language-agnostic.
Scanners see the exact **staged** content, not your working tree.

## Configuration — `.git-security-tool.toml` (optional, repo root)

```toml
[policy]
block_threshold = "HIGH"          # INFO | LOW | MEDIUM | HIGH | CRITICAL

[scanners]
gitleaks = false                  # disable a scanner

[ignore]
paths = ["tests/fixtures/", "*.generated.py"]

[ai]
enabled = false                   # optional LLM remediation suggestions
provider = "gemini"               # "anthropic" | "gemini"
model = ""                        # blank = provider default
max_findings = 3
```

**AI suggestions** are off by default and advisory only — they never affect
the pass/block decision or modify files, they announce before sending code
to the API, and secret-bearing files are never sent.

| provider | key env var | extra install |
|---|---|---|
| `gemini` | `GEMINI_API_KEY` | none (stdlib HTTP) |
| `anthropic` | `ANTHROPIC_API_KEY` | `pip install ".[ai]"` |

## Overrides

- `GIT_SECURITY_NO_BLOCK=1 git commit …` — run the scan, report, never block.
- `git commit --no-verify` — skip the hook entirely (Git built-in).

## Development

```bash
pip install -e ".[scanners,dev]"
pytest
ruff check src tests && ruff format --check src tests
```

## Scope / non-goals

No dependency-CVE scanning, no license checks, no SBOM, no IaC/container
scanning, no non-Python static analysis. The bundled Semgrep ruleset is
curated and intentionally small — not a replacement for a full SAST platform
or the Semgrep registry.

## License

MIT — see [LICENSE](LICENSE).
