# git-security-tool — Claude Code Project Instructions

> **Status:** original planning doc. The tool is now built through milestone
> 15 (see `README.md` and `src/git_security/`). Implementation order below is
> historical. Current dev commands: `pip install -e ".[scanners,dev]"`,
> `pytest`, `ruff check src tests && ruff format --check src tests`.
> Python 3.11+. Package `git_security`, CLI `git-security-tool`.

## 1. Project Identity

You are working on **git-security-tool**, a Linux-focused local Git security and code-quality CLI tool.

git-security-tool automatically analyzes code before a local Git commit is created.

The core concept is:

```text
git commit
    ↓
Git pre-commit hook
    ↓
git-security-tool
    ↓
Analyze staged changes
    ↓
Security + secrets + quality checks
    ↓
PASS / BLOCK
```

The project is intended to become a practical DevSecOps-oriented developer tool.

---

# 2. Main Objective

Build a tool that:

1. Intercepts local Git commits through a `pre-commit` hook.
2. Identifies files and changes staged for the upcoming commit.
3. Analyzes those changes.
4. Detects potential security vulnerabilities.
5. Detects secrets and credentials.
6. Detects code-quality/formatting issues.
7. Reports findings clearly.
8. Blocks commits according to configurable severity thresholds.
9. Provides remediation suggestions.
10. Optionally uses an LLM to generate contextual rewrites.
11. Provides a CLI for installation and management.
12. Can be packaged and distributed through PyPI.
13. Can run in Docker.
14. Can be integrated into GitHub Actions CI/CD.

---

# 3. Important Scope Decision

Kubernetes is intentionally OUT OF SCOPE for the current version.

Do not introduce Kubernetes unless the project architecture later becomes a centralized distributed service where Kubernetes provides a genuine technical benefit.

Current infrastructure scope:

```text
Git
Git Hooks
Python
CLI
Semgrep
Gitleaks
Ruff
PyPI
Docker
GitHub Actions
CI/CD
```

---

# 4. Core Architectural Principle

git-security-tool is an **orchestration layer**.

Do not attempt to recreate all functionality provided by mature security tools.

Use specialized tools where appropriate:

```text
git-security-tool
    │
    ├── Semgrep → security/static analysis
    ├── Gitleaks → secret detection
    └── Ruff → Python linting/quality
```

git-security-tool is responsible for:

* deciding what should be scanned
* executing tools
* collecting results
* normalizing results
* applying project policy
* generating reports
* deciding whether the commit should be blocked
* providing suggestions

---

# 5. Git Behavior

The project must understand the distinction between:

```text
Working tree
Staging area
Commit
HEAD
Repository
```

The scanner should primarily focus on staged changes.

Important commands:

```bash
git status
git diff
git diff --cached
git diff --cached --name-only
git rev-parse --git-dir
git rev-parse --is-inside-work-tree
```

The key command for upcoming commits is:

```bash
git diff --cached
```

Do not assume that `git diff` represents the changes that will be committed.

Remember:

```text
git diff
        → working tree vs staging area

git diff --cached
        → staging area vs HEAD
        → changes currently staged for commit
```

---

# 6. Git Hook Behavior

The primary integration point is:

```text
pre-commit
```

The hook must run before the commit is created.

Expected behavior:

```text
git commit
    ↓
pre-commit
    ↓
git_security scan
    ↓
exit 0 → commit continues
exit non-zero → commit is blocked
```

Do not use `post-commit` for the main security gate because the commit already exists at that point.

---

# 7. Python Process Execution

Use Python's `subprocess` module to interact with Git and external scanners.

Prefer:

```python
subprocess.run(
    ["git", "diff", "--cached"],
    capture_output=True,
    text=True
)
```

Avoid unnecessary use of:

```python
shell=True
```

Do not construct shell commands from untrusted user-controlled strings.

Handle:

* exit codes
* stdout
* stderr
* missing executables
* timeouts where appropriate

---

# 8. CLI Design

The application should eventually expose commands similar to:

```bash
git-security-tool install
git_security uninstall
git_security scan
git_security check
git_security init
git_security version
```

Use a proper CLI framework only when it provides a clear benefit.

Possible technologies:

* `argparse`
* Typer
* Click
* Rich

For learning purposes, keep the implementation understandable.

Do not introduce a framework merely because it is popular.

---

# 9. Repository Installation

`pip install git-security-tool` and `git-security-tool install` have different responsibilities.

### `pip install git-security-tool`

Installs the git-security-tool Python CLI.

### `git-security-tool install`

Configures git-security-tool for the current Git repository.

The latter should:

1. verify the current directory is a Git repository
2. locate the Git directory
3. check dependencies
4. install/configure the pre-commit hook
5. validate the installation

Do not make `pip install` automatically modify arbitrary Git repositories.

---

# 10. Scanner Integration

Each external scanner should have its own wrapper.

Expected structure:

```text
src/git_security/scanners/
├── semgrep.py
├── gitleaks.py
└── ruff.py
```

Each wrapper should isolate scanner-specific behavior.

For example:

```python
run_semgrep(...)
run_gitleaks(...)
run_ruff(...)
```

The rest of git-security-tool should not need to know the exact command-line syntax of each tool.

---

# 11. Finding Normalization

Different tools return different formats.

Normalize them into a common git-security-tool representation.

Conceptually:

```python
Finding(
    tool="semgrep",
    file="example.py",
    line=10,
    severity="HIGH",
    category="SQL Injection",
    message="Potential SQL injection",
    suggestion="Use parameterized queries"
)
```

The exact class/schema can change during implementation.

The architectural principle must remain:

> External scanner output should be converted into git-security-tool's internal representation as early as practical.

---

# 12. Severity Policy

Support severity levels:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

The project should eventually support configuration such as:

```yaml
security:
  block_on:
    - CRITICAL
    - HIGH
```

Possible behavior:

```text
CRITICAL → block
HIGH     → block
MEDIUM   → warning
LOW      → warning
INFO     → informational
```

Do not hard-code policy everywhere in the scanner implementations.

Keep policy decisions in the analysis layer.

---

# 13. Security Requirements

git-security-tool itself must follow secure coding practices.

### Required principles

* Avoid `shell=True` unless there is a strong reason.
* Prefer argument arrays in `subprocess.run`.
* Never print secrets unnecessarily.
* Do not leak API keys in logs.
* Validate paths.
* Handle malformed scanner output safely.
* Treat external tool output as untrusted input.
* Do not automatically modify user source code without explicit approval.
* Make external LLM usage optional.
* Clearly tell users when source code is being sent to an external service.
* Keep credentials out of repository files.
* Never hard-code API keys.

---

# 14. AI Integration

AI is an optional enhancement, not the core security mechanism.

The security decision should NOT depend exclusively on an LLM.

Preferred architecture:

```text
Git diff
   ↓
Deterministic scanners
   ↓
Findings
   ↓
Optional LLM
   ↓
Explanation + remediation suggestion
```

Do NOT design:

```text
Git diff
   ↓
LLM
   ↓
"Is this secure?"
```

as the primary security gate.

Deterministic security tools such as Semgrep and Gitleaks should perform the primary detection.

The LLM can improve:

* explanations
* contextual suggestions
* rewrite proposals
* developer experience

---

# 15. AI Safety

Never automatically apply LLM-generated code changes in the initial version.

Preferred behavior:

```text
Finding detected

Suggested rewrite:

<code>

Apply this suggestion? [y/N]
```

The developer remains in control.

LLM suggestions should be treated as recommendations, not authoritative security guarantees.

---

# 16. Docker

Docker is primarily for reproducible CI/CD execution.

Do not unnecessarily force every local Git commit to run inside a Docker container.

Preferred architecture:

```text
LOCAL:

git commit
    ↓
git-security-tool CLI
    ↓
local scanners
```

and:

```text
CI:

GitHub Actions
    ↓
Docker
    ↓
git-security-tool
    ↓
scanners
```

Maintain a clear separation between local developer experience and CI infrastructure.

---

# 17. CI/CD

GitHub Actions will provide CI/CD automation.

The CI pipeline should eventually:

```text
Checkout repository
        ↓
Install dependencies
        ↓
Run tests
        ↓
Run git-security-tool
        ↓
Run security checks
        ↓
Build Docker image
```

The local pre-commit hook is the first defense layer.

CI is the second defense layer.

Reason:

```bash
git commit --no-verify
```

can bypass local hooks.

Therefore:

```text
Local protection
        +
CI protection
```

is intentional.

---

# 18. Python Packaging

The project should be packaged using modern Python packaging practices.

Primary configuration:

```text
pyproject.toml
```

The intended user experience is:

```bash
pip install git-security-tool
```

followed by:

```bash
cd my-project
git-security-tool install
```

The CLI should be registered through a Python package entry point.

Example conceptual configuration:

```toml
[project.scripts]
git_security = "git_security.cli:main"
```

The exact packaging configuration may evolve.

---

# 19. Project Structure

Maintain the following conceptual separation:

```text
src/git_security/
│
├── cli.py
│
├── git/
│   ├── repository.py
│   ├── diff.py
│   └── hooks.py
│
├── scanners/
│   ├── semgrep.py
│   ├── gitleaks.py
│   └── ruff.py
│
├── analysis/
│   ├── findings.py
│   ├── severity.py
│   └── suggestions.py
│
├── installer/
│   ├── dependencies.py
│   └── git_hook.py
│
└── reporter/
    └── terminal.py
```

Keep responsibilities separated.

Do not create one giant `main.py` containing the entire application.

---

# 20. Development Style

The developer of this project is learning the concepts while implementing them.

Therefore, when introducing a new concept:

1. Explain what it is.
2. Explain why git-security-tool needs it.
3. Explain how it fits into the architecture.
4. Then implement it.
5. Explain the important code.
6. Test it.
7. Only then proceed to the next component.

Do not blindly generate large amounts of code without explanation.

The goal is both:

```text
BUILD THE PROJECT
        +
LEARN THE ENGINEERING CONCEPTS
```

---

# 21. Implementation Order

Follow this progression unless there is a strong reason to change it:

### Phase 1 — Git

Learn and implement:

```text
git status
git diff
git diff --cached
git diff --cached --name-only
git rev-parse
```

### Phase 2 — subprocess

Learn:

```python
subprocess.run()
```

### Phase 3 — Git hook

Implement:

```text
pre-commit
```

### Phase 4 — Basic CLI

Implement:

```bash
git_security scan
git-security-tool install
```

### Phase 5 — Semgrep

Integrate security analysis.

### Phase 6 — Ruff

Integrate Python code quality.

### Phase 7 — Gitleaks

Integrate secret detection.

### Phase 8 — Findings

Create a common finding model.

### Phase 9 — Policy

Implement severity and PASS/BLOCK logic.

### Phase 10 — Reporting

Create clear terminal output.

### Phase 11 — Packaging

Prepare:

```text
pyproject.toml
```

and publish to PyPI.

### Phase 12 — Docker

Create a reproducible CI image.

### Phase 13 — GitHub Actions

Implement CI/CD.

### Phase 14 — AI suggestions

Add optional LLM-powered remediation suggestions.

---

# 22. Testing Requirements

Every major component should have tests.

Examples:

```text
tests/
├── test_git.py
├── test_scanners.py
├── test_analysis.py
└── test_installer.py
```

Test important scenarios:

### Clean commit

```text
No findings
→ exit 0
→ commit allowed
```

### High-severity vulnerability

```text
HIGH finding
→ policy says block
→ exit non-zero
→ commit blocked
```

### Missing dependency

```text
Semgrep unavailable
→ clear error
→ no silent failure
```

### Non-Git directory

```text
git-security-tool install
→ detect missing Git repository
→ useful error message
```

---

# 23. Do Not Overengineer

The first version should NOT contain:

* Kubernetes
* microservices
* distributed queues
* databases
* complex web dashboards
* unnecessary cloud infrastructure
* custom vulnerability databases
* a custom static-analysis engine

Build the smallest useful version first.

The desired initial product is:

```text
CLI
 +
Git Hook
 +
Git diff
 +
Semgrep
 +
Gitleaks
 +
Ruff
 +
Terminal report
```

Then expand.

---

# 24. Definition of Success

The first meaningful milestone is:

```bash
pip install git-security-tool
```

Then:

```bash
cd test-project
git-security-tool install
```

Then:

```bash
git add .
git commit -m "test"
```

git-security-tool automatically executes.

For a vulnerable staged file:

```text
❌ Security issue detected
❌ Commit blocked
```

For clean code:

```text
✓ Security checks passed
✓ Code quality passed
✓ Commit allowed
```

If this works reliably, the core project is successful.

---

# 25. Final Product Vision

The long-term architecture is:

```text
                git-security-tool
                     │
          ┌──────────┴──────────┐
          │                     │
       LOCAL                   CI/CD
          │                     │
     Git Hook              GitHub Actions
          │                     │
          ▼                     ▼
      CLI Tool                Docker
          │                     │
          └──────────┬──────────┘
                     ▼
              Analysis Engine
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Semgrep    Gitleaks     Ruff
          │          │          │
          └──────────┼──────────┘
                     ▼
                  Findings
                     │
                     ▼
              Suggestion Engine
                     │
                Optional LLM
                     │
                     ▼
                  Reporter
```

The primary goal is to create a practical local security gate that integrates naturally into a developer's existing Git workflow.

Do not sacrifice simplicity merely to add technologies.

Every technology added to the project should have a clear architectural purpose.
