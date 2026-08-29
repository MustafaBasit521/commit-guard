# git-security-tool — Claude Code instructions

A local Git **pre-commit gate** (Linux) that scans staged changes and blocks
the commit on serious findings. It is an **orchestration layer** over Ruff,
Semgrep, and Gitleaks — never reimplement what those tools do. Full design:
`./ARCHITECTURE.md`. Usage: `./README.md`.

## Status

Built and working (milestone 15 + extras). Installed and dogfooded on a real
project. Not yet tagged / published to PyPI.

## Dev commands

```bash
pip install -e ".[scanners,dev]"          # tool + ruff + semgrep + pytest
pytest                                     # ~50s (semgrep subprocess tests)
ruff check src tests && ruff format --check src tests
git-security-tool scan --all               # run the tool on this repo
```

Python 3.11+. Package import name `git_security`; CLI / PyPI name
`git-security-tool`.

## Hard rules (the tool must obey its own advice)

- **Scan staged content, not the working tree** — `scan` materializes the
  index into a temp dir. `git diff --cached`, never `git diff`.
- **subprocess: argument lists only.** Never `shell=True`, never build a
  command from untrusted input. `git/repository.py::run_git` is the only
  place that shells to git.
- **The exit code is the gate.** `run_scan` returns 0 (allow) or 1 (block);
  nothing else decides.
- **Policy lives in `policy/engine.py`.** Scanners assign a severity and stop;
  they never decide blocking.
- **AI is advisory** — off by default, opt-in, never changes the decision,
  never writes files, never sends a Gitleaks-flagged file to the API.
- **Never print/log secret values** (Gitleaks runs with `--redact`).
- Keep `ruff check` and `ruff format --check` green on `src/` and `tests/`.

## Conventions

- One module, one job. New capability = new module + one line in `scan.py`.
- Each scanner owns its tool's CLI flags, exit-code meaning, and JSON→Finding
  mapping. Shared plumbing (`run_tool`, `to_repo_relative`) is in
  `scanners/base.py`.
- Config errors raise `ConfigError` → caught in `run_scan` → clean message,
  no traceback.
- A scanner crash is caught per-scanner (`_safe_scan`) — report it, continue.
- Tests: pure logic (policy, mappers, config, ignore, baseline, sarif) has no
  I/O; end-to-end tests use a real temp git repo; semgrep/gitleaks tests skip
  if the tool isn't installed.

## Out of scope

Dependency-CVE scanning, license/SBOM, IaC/container scanning, non-Python
static analysis, Kubernetes/microservices/databases. The bundled Semgrep set
is intentionally small.

## Working style (learning project)

Incremental. For a new concept: explain what/why/how it fits → implement the
smallest version → explain the key code → test → next. Surface any decision
that affects architecture before acting. No large unexplained code dumps.
