# git-security-tool

[![CI](https://github.com/MustafaBasit521/commit-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/MustafaBasit521/commit-guard/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/git-security-tool)](https://pypi.org/project/git-security-tool/)
[![Python](https://img.shields.io/pypi/pyversions/git-security-tool)](https://pypi.org/project/git-security-tool/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Stop secrets and dangerous code from reaching a commit.** A local Git
pre-commit gate (Linux) that scans your *staged* changes and blocks the
commit when it finds something serious — leaked credentials, `eval()`,
`pickle.loads`, disabled TLS verification — while surfacing lint and
formatting issues as non-blocking warnings. The same engine runs in CI over
the whole repository.

It is an **orchestration layer**, not a new scanner: it runs
[Gitleaks](https://github.com/gitleaks/gitleaks),
[Semgrep](https://semgrep.dev/), and [Ruff](https://docs.astral.sh/ruff/),
normalizes their output into one model, applies your policy, and decides
pass / block.

```
git commit
   └─► .git/hooks/pre-commit
        └─► git-security-tool scan
             ├─ gitleaks            → secrets            (CRITICAL → blocks)
             ├─ semgrep + 17 rules  → insecure code      (HIGH → blocks)
             ├─ ruff check          → lint               (LOW → warns)
             └─ ruff format --check → formatting         (LOW → warns)
                  └─► policy → exit 0 (allow) | exit 1 (block)
```

### What a blocked commit looks like

```
$ git commit -m "add config loader"
[git-security-tool] pre-commit security scan
[git-security-tool] 2 file(s) to scan
[git-security-tool] 1 blocking finding(s):
  [HIGH] semgrep:python-yaml-unsafe-load config.py:14 - yaml.load() without a
  safe loader can construct arbitrary Python objects from the input.
[git-security-tool] summary: 1 blocking, 0 warning(s)
[git-security-tool] commit blocked - fix the blocking findings above, or set
GIT_SECURITY_NO_BLOCK=1 to override
```

## Add it to a project

> New to this? [**INSTALL.md**](INSTALL.md) is a slower, detailed walkthrough
> with expected output and troubleshooting. The steps below are the short
> version.

### 1. Install the tool (once per machine)

The pre-commit hook runs `git-security-tool` from your `PATH`, so install it
somewhere permanent — [pipx](https://pipx.pypa.io/) is cleanest:

```bash
pipx install "git-security-tool[scanners]"      # isolated, always on PATH
```

Or into a virtualenv you keep active / on `PATH`:

```bash
pip install "git-security-tool[scanners]"
```

Then add **Gitleaks** (a Go binary, not on PyPI) for secret detection —
[download a release](https://github.com/gitleaks/gitleaks/releases) and put
it on `PATH`. The scan silently skips any scanner that isn't installed.

```bash
git-security-tool check     # confirms hook status + which scanners are present
```

### 2. Turn on the hook (once per repo)

```bash
cd your-repo
git-security-tool install               # writes .git/hooks/pre-commit
```

`.git/hooks/` is not version-controlled, so every clone / machine runs this
once. `git-security-tool uninstall` removes it; `--force` replaces a hook
you didn't create.

### 3. (existing repo) Baseline what's already there

```bash
git-security-tool scan --all            # see what it finds first
git-security-tool baseline              # grandfather those findings
git add .git-security-tool-baseline.json && git commit -m "add security baseline"
```

New issues still block — only the pre-existing ones are ignored.

### 4. Add the CI check

Local hooks can be skipped (`--no-verify`) or missing on a teammate's
machine, so CI is the real enforcement. Create
`.github/workflows/security.yml`:

```yaml
name: security
on: [push, pull_request]
jobs:
  security:
    uses: MustafaBasit521/commit-guard/.github/workflows/scan.reusable.yml@main
```

That reusable workflow installs the tool + Gitleaks and runs
`git-security-tool scan --all` over the whole repo.

### 5. (optional) Tune it — `.git-security-tool.toml`

See [Configuration](#configuration--git-security-tooltoml-optional-repo-root)
below: severity threshold, disable a scanner, ignore paths, AI suggestions.

---

**Commands:** `scan [--all] [--format sarif]`, `baseline`, `install [--force]`,
`uninstall`, `check`, `version`.

- `scan` — staged changes (pre-commit)
- `scan --all` — every tracked file (CI / audit); `--format sarif` emits SARIF
  on stdout for GitHub code scanning

Verify the ruleset end to end: `./scripts/probe.sh` (checks all 17 rules +
secret detection in a throwaway repo).

## What it checks

| category | tool | severity | blocks by default |
|---|---|---|---|
| Secrets / credentials | Gitleaks | CRITICAL | yes |
| Insecure code patterns (17 rules) | Semgrep + bundled rules | HIGH / MEDIUM | HIGH only |
| Lint (unused imports, undefined names, …) | `ruff check` | LOW | no |
| Formatting | `ruff format --check` | LOW | no |

The bundled Semgrep rules cover code/command injection (`eval`, `exec`,
`os.system`, `shell=True`), unsafe deserialization (`pickle`, `yaml.load`,
insecure XML), weak crypto & disabled TLS verification, web footguns (Flask
`debug=True`, Jinja autoescape off, `mark_safe`), and filesystem/network
hygiene (`extractall`, `mktemp`, `requests` without timeout).

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
| `anthropic` | `ANTHROPIC_API_KEY` | `pip install "git-security-tool[ai]"` |

## Overrides

- `GIT_SECURITY_NO_BLOCK=1 git commit …` — run the scan, report, never block.
- `git commit --no-verify` — skip the hook entirely (Git built-in).

## Development

```bash
pip install -e ".[scanners,dev]"
pytest                                              # 96 tests
ruff check src tests && ruff format --check src tests
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and a milestone-by-milestone
build log.

## Scope / non-goals

No dependency-CVE scanning, no license checks, no SBOM, no IaC/container
scanning, no non-Python static analysis. The bundled Semgrep ruleset is
curated and intentionally small — not a replacement for a full SAST platform
or the Semgrep registry.

## License

MIT — see [LICENSE](LICENSE).
