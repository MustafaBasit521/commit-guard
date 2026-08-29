# git-security-tool — Architecture

This is the as-built reference. It also doubles as a design retrospective:
each section explains **what** a piece does and **why** it ended up that way.
For usage, see `README.md`.

---

## 1. What it is

A local Git **pre-commit gate** for Linux. On `git commit` it scans the
*staged* changes; if policy says a finding is serious enough, the commit is
aborted (`exit 1`). The same engine runs in CI over the whole repo.

It is an **orchestration layer**, not a scanner. Detection is delegated to
three mature tools; this project decides what to scan, runs them, normalizes
their output, applies policy, and reports.

```
git commit
  └─► .git/hooks/pre-commit  (3-line shell shim)
       └─► git-security-tool scan
            ├─ ruff check         → lint            (LOW  → warn)
            ├─ ruff format --check → formatting     (LOW  → warn)
            ├─ semgrep + 17 rules → insecure code   (HIGH/MEDIUM)
            └─ gitleaks           → secrets         (CRITICAL → block)
                 └─► policy.evaluate() → Decision
                      └─► exit 0 (allow) | exit 1 (block)
```

Core design rule, held throughout: **the exit code is the entire control
mechanism.** Everything else is logic for choosing between `0` and `1`.

---

## 2. Package layout

```
src/git_security/
├── __main__.py         python -m git_security  → cli.main()
├── cli.py              argparse; dispatch to an action; return an exit code
├── scan.py             the pipeline: gather → scan → policy → report → exit
│
├── git/
│   ├── repository.py   run_git() — the ONLY place that shells to git
│   ├── diff.py         staged files, staged diff, materialize_staged, ls-files
│   └── hooks.py        resolve this repo's hooks dir / pre-commit path
│
├── scanners/
│   ├── base.py         run_tool() (missing-tool tolerant), to_repo_relative()
│   ├── ruff.py         run_ruff (lint) + run_ruff_format  → list[Finding]
│   ├── gitleaks.py     run_gitleaks(staged=…)             → list[Finding]
│   └── semgrep.py      run_semgrep(files, root, rules_dir) → list[Finding]
│
├── models/finding.py   Severity (IntEnum) + Finding (frozen dataclass)
├── policy/engine.py    PolicyConfig, Decision, evaluate()
├── config/loader.py    .git-security-tool.toml → Config (+ ConfigError)
├── ignore.py           glob/prefix path-ignore matching
├── baseline.py         suppress findings already recorded in a baseline file
│
├── reporter/
│   ├── terminal.py     Decision → human text
│   └── sarif.py        findings → SARIF 2.1.0 JSON (for CI code scanning)
│
├── installer/
│   ├── git_hook.py     install / uninstall / status; the managed hook text
│   └── dependencies.py which scanners are on PATH
│
├── suggestions/
│   ├── llm.py          optional AI explanation of blocking findings
│   └── providers.py    AnthropicProvider, GeminiProvider (same 4 methods)
│
└── rules/semgrep/*.yml  17 bundled rules, shipped as package data
```

**Why a package and not one file:** every module has one job and one reason
to change. `cli.py` reads like a table of contents; `scan.py` is pure
orchestration; each scanner owns exactly one tool's quirks. Adding a
capability is usually one new module + one line in `scan.py`.

---

## 3. The data flow

### 3.1 Get the files

`git/diff.py` provides three sources:

| function | used by | returns |
|---|---|---|
| `get_staged_files()` | pre-commit (`scan`) | staged paths, `--diff-filter=ACM` (no deletions) |
| `get_tracked_files()` | CI (`scan --all`) | `git ls-files` |
| `materialize_staged(files, dest)` | pre-commit only | writes the **index** blob content into a temp dir via `git checkout-index` |

**Why `materialize_staged`:** a commit is built from the *index*, not the
working tree. Stage `x.py`, edit it again, and a working-tree scan would
flag code that isn't being committed *and* miss code that is — the dangerous
direction for a security gate. So `scan` (staged mode) copies the exact
staged bytes to a throwaway dir and scans that. `scan --all` has no "staged"
concept, so it scans the working tree in place. Gitleaks is Git-aware and
scans the index itself (`gitleaks git --staged`), so it never needs the
temp dir.

`_copy_project_config()` also drops the repo's `pyproject.toml` / `ruff.toml`
into the temp dir — scanners resolve config by walking up from each file, and
a bare temp dir would make Ruff silently use built-in defaults.

### 3.2 Run the scanners

`scan._collect_findings(scope)` runs each enabled scanner through
`_safe_scan()` — a wrapper that turns a scanner crash (`RuntimeError`) into
a printed message + empty list, so one broken tool doesn't take down the
commit with a traceback. A scanner that isn't installed is skipped silently
by `base.run_tool()` returning `None`.

### 3.3 Normalize — the `Finding` model

```python
@dataclass(frozen=True)
class Finding:
    tool: str; rule: str; severity: Severity
    file: str; line: int; message: str
```

Each scanner's `_to_finding()` converts its tool's native JSON into this.
The three tools emit wildly different shapes:

| | Ruff | Gitleaks | Semgrep |
|---|---|---|---|
| path key | `filename` (absolute) | `File` (relative) | `path` |
| line | `location.row` | `StartLine` | `start.line` |
| rule | `code` (can be null) | `RuleID` | `check_id` (path-namespaced) |
| severity | *(none — assigned)* | *(none — CRITICAL)* | `extra.severity` (ERROR/WARNING/INFO) |

Absorbing that asymmetry in one place per scanner is the whole point — from
here on, policy and reporting see only `Finding`.

`Severity` is an `IntEnum` so policy can write `f.severity >= threshold`
directly (it's `4 >= 3` underneath) while still being a typo-proof named
constant.

### 3.4 Baseline + ignores

Before policy:

- `ignore.filter_ignored()` drops files matching `[ignore] paths` patterns
  (`tests/fixtures/`, `*.generated.py`, …). Gitleaks findings are filtered
  after the fact since it scans everything.
- `baseline.apply_baseline()` removes findings whose
  `(tool, rule, file, message)` fingerprint is already in
  `.git-security-tool-baseline.json`. This lets an established repo adopt the
  tool without a big-bang cleanup: existing issues are grandfathered, new
  ones still block. The fingerprint deliberately excludes line number so
  unrelated edits don't resurface a baselined finding.

### 3.5 Policy

```python
def evaluate(findings, config) -> Decision:
    blocking = [f for f in findings if f.severity >= config.block_threshold]
    warnings = [f for f in findings if f.severity <  config.block_threshold]
    return Decision(blocked=bool(blocking), blocking=..., warnings=...)
```

One pure function. No printing, no `sys.exit`, no subprocess — which is why
it's trivially unit-tested with fake `Finding`s. `block_threshold` defaults
to `HIGH` (secrets + RCE-class patterns block; style warns) and is
overridable per repo.

**Why a whole module for ten lines:** it is the single place blocking
behaviour is defined. Per-directory thresholds, per-rule allowlists,
"never block on Fridays" — all of that would land here, and scanners /
`scan.py` wouldn't change.

### 3.6 Report + exit

- text mode → `reporter/terminal.py` groups warnings then blocking findings,
  sorted by `(file, line, tool)`, long messages collapsed to one line.
- sarif mode (`--format sarif`) → `reporter/sarif.py` prints SARIF 2.1.0 to
  **stdout** (progress goes to stderr so the JSON is clean); CI uploads it
  to GitHub code scanning.

Then `run_scan` returns `0` or `1`. In staged mode, `GIT_SECURITY_NO_BLOCK=1`
forces `0` while still reporting — the dev escape hatch (distinct from
`git commit --no-verify`, which skips the hook entirely).

---

## 4. The other entry points

- **`git-security-tool install`** — `installer/git_hook.py` writes a 3-line
  shell shim to this repo's hooks dir (resolved via
  `git rev-parse --git-path hooks`, so `core.hooksPath` / worktrees work).
  The shim carries a marker comment; `install` refuses to overwrite a hook
  it didn't write unless `--force`, and `uninstall` only removes its own.
- **`git-security-tool baseline`** — runs a full-repo scan and writes every
  current finding to the baseline file.
- **`git-security-tool check`** — is the hook installed, which scanners are
  present.

---

## 5. Optional AI suggestions

Off by default. Enabled only when `[ai] enabled = true` **and** the provider's
API key is set. `providers.py` has `AnthropicProvider` and `GeminiProvider`
behind one 4-method shape (`name`, `default_model`, `available()`,
`complete()`); `[ai] provider` picks one. Gemini uses stdlib `urllib` (no
dependency); Anthropic needs `pip install ".[ai]"`.

Guarantees: it never changes the block decision, never writes files,
announces before sending code to the API, and **never sends a file Gitleaks
flagged** (a secret could be in the surrounding snippet).

---

## 6. Two defense layers

| | local | CI |
|---|---|---|
| trigger | `git commit` | `git push` / PR |
| command | `git-security-tool scan` (staged) | `git-security-tool scan --all` |
| bypass | `--no-verify`, or not installed | none |
| purpose | fast feedback, before it's in history | enforcement nobody can skip |

`.github/workflows/scan.reusable.yml` is a `workflow_call` reusable workflow
so downstream repos reference it in three lines instead of copy-pasting.

---

## 7. Build history — milestone by milestone

Each milestone was: explain the concept → smallest implementation → explain
the code → test → next. The lesson each one carried:

| # | Milestone | What it established |
|---|---|---|
| 1 | Hook runs a Python program | Git finds an executable `pre-commit`; exit 0/non-zero is the whole gate; hooks aren't version-controlled |
| 2 | `subprocess` captures staged changes | argument lists (never `shell=True`); `git diff --cached` ≠ `git diff`; `CompletedProcess` |
| 3 | Ruff wrapper | linter exit codes (1 = "found issues" is normal, not failure); JSON output over text scraping |
| 4 | Gitleaks wrapper | a second tool with a different invocation model and a different JSON shape → motivates normalization |
| 5 | `Finding` model + `scanners/base.py` | two concrete tool outputs = the right time to design the common one; extract the shared helper, keep the per-tool quirks |
| 6 | Semgrep | source → AST → pattern match → structured finding; first tool with real severities; offline (`--metrics=off`) |
| 7 | Policy engine | `Severity` becomes an ordered `IntEnum`; `evaluate()` is pure; **the exit code finally means something** |
| 8 | Reporter module + pytest | pull presentation out of `main`; the pure policy/mapper code begs for tests |
| 9 | Packaging | `pyproject.toml` (hatchling), `[project.scripts]` creates the command, rules ship as package data, `-e` editable install |
| 10 | `install` / `uninstall` / `check` | the hook must be written per-repo; only ever touch a hook we created (marker + `--force`) |
| 11 | Config file | `tomllib` (stdlib, 3.11+); reuse `PolicyConfig`; malformed config = clean message, not traceback |
| 12 | Scan the staged blob | the accuracy bug: index vs working tree; `git checkout-index` to a temp dir; copy project config so scanners keep their settings |
| 13 | Path ignores | `fnmatch` glob + directory prefix; filter Gitleaks findings after the fact |
| 14 | `ruff format --check` | linting ≠ formatting; the tool must pass its own checks (reformatted the codebase) |
| 15 | Optional AI | advisory only; opt-in; announce before sending; never send secret-bearing files |
| — | Gemini provider | provider-pluggable behind one shape; stdlib `urllib` keeps core zero-dependency |
| — | `scan --all` + CI | CI has no "staged" — scan tracked files in place; the second, unbypassable layer |
| — | 17 Semgrep rules | injection / deserialization / crypto-TLS / web / filesystem-net; validated in CI |
| — | Baseline + SARIF | adopt-on-a-dirty-repo; GitHub code-scanning integration |
| — | Hardening | `ConfigError` handling, per-scanner isolation (`_safe_scan`), AI secret-leak guard, fixed Gitleaks 8.30 (`protect`/`detect` removed → `git --staged` / `dir`) |

### Mistakes worth remembering

- **`git reset --hard` on a commit that held real work** wiped milestone 7;
  recovered from reflog. `--hard` discards commits *and* uncommitted changes.
- **Staging a scratch file alongside real work** made the "undo the probe"
  step also undo the milestone. Test with the probe unstaged, or `git add`
  only the real files.
- **`--amend` after pushing** diverged local/remote; fixed with
  `push --force-with-lease` (safe here — solo repo).
- **Ruff's shifting defaults** kept flagging our own code (`PLW1510`,
  `TRY004`); fixed by pinning `[tool.ruff.lint] select`.

---

## 8. Scope boundaries

Not in scope: dependency-CVE scanning, license checks, SBOM, IaC/container
scanning, non-Python static analysis. The bundled Semgrep set is curated and
small — not a replacement for the Semgrep registry or a full SAST platform.
Kubernetes / microservices / a database were explicitly ruled out from day
one and never needed.
