# git-security-tool — System Architecture

> **Status:** this is the original design doc. The project has since been
> built through milestone 15; where this document and the code disagree, the
> code and `README.md` are authoritative. A full reconciliation pass is
> pending.

## 1. Project Overview

git-security-tool is a Linux-focused local Git security and code-quality tool.

Its primary purpose is to intercept a developer's local Git commit before the commit is created, analyze the staged code changes, detect potential security vulnerabilities, secrets, and code-quality problems, and provide actionable suggestions.

The tool operates locally on the developer's machine and does not require GitHub for its core functionality.

The project will later integrate with CI/CD so that the same security checks can be executed again after code is pushed to a remote repository.

### Core idea

```text
Developer
    │
    │ git commit
    ▼
Git pre-commit hook
    │
    ▼
git-security-tool
    │
    ├── Git Change Collector
    ├── Security Scanner
    ├── Secret Scanner
    ├── Code Quality Scanner
    ├── Analysis Engine
    ├── Suggestion Engine
    └── Reporter
    │
    ▼
PASS / BLOCK
    │
    ▼
Git commit
```

---

# 2. Project Goals

The main goals of git-security-tool are:

1. Automatically inspect code before a local Git commit.
2. Analyze only the changes relevant to the upcoming commit whenever possible.
3. Detect potential security vulnerabilities.
4. Detect accidentally committed secrets and credentials.
5. Detect code-quality and formatting problems.
6. Provide useful explanations for detected problems.
7. Suggest secure or cleaner rewrites.
8. Allow the developer to decide whether suggested fixes should be applied.
9. Block commits when configured security thresholds are exceeded.
10. Provide a simple CLI for installation and management.
11. Package the tool so developers can install it through PyPI.
12. Provide a CI/CD integration for remote validation.
13. Use Docker to provide a reproducible environment for CI execution.

---

# 3. Non-Goals

The initial project will NOT attempt to:

* Replace Git.
* Replace GitHub.
* Replace professional SAST platforms.
* Replace a full IDE security analyzer.
* Automatically modify source code without user approval.
* Support every programming language.
* Deploy a Kubernetes cluster.
* Build a distributed security scanning platform.
* Perform complete program verification.
* Guarantee that code is completely secure.

The tool should be practical and educational rather than attempting to compete with enterprise security platforms.

---

# 4. High-Level Architecture

git-security-tool consists of two major execution environments:

## Local Environment

Used during:

```text
git commit
```

Architecture:

```text
Developer
    │
    ▼
git add
    │
    ▼
git commit
    │
    ▼
.git/hooks/pre-commit
    │
    ▼
git-security-tool CLI
    │
    ▼
Git Change Collector
    │
    ├──────────────┐
    ▼              ▼
Staged Files    Staged Diff
    │              │
    └──────┬───────┘
           ▼
      Scan Pipeline
           │
     ┌─────┼──────────────┐
     ▼     ▼              ▼
 Semgrep Gitleaks        Ruff
     │     │              │
     └─────┼──────────────┘
           ▼
     Analysis Engine
           │
           ▼
    Suggestion Engine
           │
           ▼
        Reporter
           │
       ┌───┴───┐
       ▼       ▼
     PASS     FAIL
       │       │
       ▼       ▼
    Commit   Block
```

---

# 5. CI/CD Environment

After the local workflow is implemented, git-security-tool will also operate inside CI.

The purpose is to provide a second security layer because local Git hooks can be bypassed.

For example:

```bash
git commit --no-verify
```

can bypass a local pre-commit hook.

Therefore, CI should independently validate the pushed code.

Architecture:

```text
Developer
    │
    ▼
git push
    │
    ▼
GitHub
    │
    ▼
GitHub Actions
    │
    ▼
CI Environment
    │
    ▼
git-security-tool
    │
    ├── Security scan
    ├── Secret scan
    ├── Code-quality scan
    └── Tests
    │
    ▼
PASS / FAIL
```

---

# 6. Docker Architecture

Docker will primarily be used for CI/CD and reproducible execution.

The local CLI does not need to run inside Docker for every commit.

### Local

```text
Developer machine
    │
    ├── Git
    ├── Python
    ├── git-security-tool
    ├── Semgrep
    ├── Gitleaks
    └── Ruff
```

### CI

```text
GitHub Actions
       │
       ▼
Docker Container
       │
       ├── Python
       ├── git-security-tool
       ├── Semgrep
       ├── Gitleaks
       └── Ruff
```

The Docker image provides a predictable environment so that CI does not depend on the exact configuration of an individual developer's machine.

---

# 7. CI/CD Pipeline

The planned CI/CD pipeline is:

```text
Developer
    │
    ▼
git push
    │
    ▼
GitHub
    │
    ▼
GitHub Actions
    │
    ├── Checkout repository
    │
    ├── Install dependencies
    │
    ├── Run tests
    │
    ├── Run git-security-tool
    │      │
    │      ├── Semgrep
    │      ├── Gitleaks
    │      └── Ruff
    │
    ├── Build Docker image
    │
    └── Push image to container registry
```

Deployment may be added later, but it is not required for the first version.

---

# 8. CLI Architecture

git-security-tool will expose a command-line interface.

Example commands:

```bash
git-security-tool install
git_security uninstall
git_security scan
git_security check
git_security init
git_security version
git_security --help
```

### `git-security-tool install`

Installs/configures git-security-tool for the current Git repository.

Expected behavior:

1. Verify that the current directory belongs to a Git repository.
2. Locate the repository's Git directory.
3. Check required dependencies.
4. Install/configure the pre-commit hook.
5. Create or validate git-security-tool configuration.
6. Display installation status.

### `git-security-tool scan`

Runs the analysis manually without requiring a Git commit.

### `git-security-tool uninstall`

Removes git-security-tool's Git integration from the repository.

### `git-security-tool check`

Checks whether git-security-tool is correctly configured.

### `git-security-tool init`

May eventually initialize project configuration and optional CI configuration.

---

# 9. Git Integration

git-security-tool uses Git Hooks rather than modifying Git itself.

The primary hook is:

```text
pre-commit
```

The hook executes before the commit is created.

Example flow:

```text
git commit
    │
    ▼
Git invokes:
.git/hooks/pre-commit
    │
    ▼
git_security scan
    │
    ▼
analysis
    │
    ▼
exit code
```

Exit code:

```text
0 → allow commit
non-zero → block commit
```

This mechanism is fundamental to the project.

---

# 10. Accessing Committed Code

git-security-tool does not wait for the commit to be created.

Instead, it analyzes the code that is currently staged for the upcoming commit.

Important Git commands include:

```bash
git status
git diff
git diff --cached
git diff --cached --name-only
git rev-parse --git-dir
git rev-parse --is-inside-work-tree
```

The most important command is:

```bash
git diff --cached
```

because it shows changes currently staged for commit.

Changed files can be obtained with:

```bash
git diff --cached --name-only
```

Python's `subprocess` module will initially be used to execute these commands.

---

# 11. Scanner Architecture

git-security-tool should not implement every security rule itself.

Instead, it acts as an orchestration layer around specialized tools.

Planned scanners:

```text
git-security-tool
    │
    ├── Semgrep
    │     └── Security/static analysis
    │
    ├── Gitleaks
    │     └── Secret detection
    │
    └── Ruff
          └── Python code quality/linting
```

Each scanner should have a wrapper inside:

```text
src/git_security/scanners/
```

For example:

```text
semgrep.py
gitleaks.py
ruff.py
```

These modules are responsible for:

* invoking the external tool
* passing appropriate input
* capturing output
* handling errors
* converting results into git-security-tool's internal finding format

---

# 12. Finding Model

Different scanners produce different output formats.

git-security-tool should normalize those results into a common internal representation.

Conceptually:

```python
Finding(
    tool="semgrep",
    file="database.py",
    line=42,
    severity="HIGH",
    category="SQL Injection",
    message="Potential SQL injection vulnerability",
    suggestion="Use parameterized queries"
)
```

The exact implementation may evolve.

The important architectural principle is:

> Scanner-specific output should not leak throughout the rest of the application.

The analysis layer should work with git-security-tool's own normalized findings.

---

# 13. Severity System

git-security-tool should eventually classify findings using levels such as:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

The project configuration can determine which severities block a commit.

Example:

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

This should be configurable rather than hard-coded.

---

# 14. Suggestion Engine

The suggestion engine is responsible for turning findings into useful remediation advice.

There should initially be two types of suggestions.

## Rule-Based Suggestions

Known problems can have predefined secure rewrites.

Example:

```text
Problem:
Hardcoded credential

Suggested approach:
Use an environment variable.
```

## AI-Based Suggestions

An LLM may later be used to generate contextual explanations and code rewrites.

Flow:

```text
Finding
   │
   ▼
Relevant code
   │
   ▼
Suggestion Engine
   │
   ▼
LLM
   │
   ├── Explanation
   ├── Secure rewrite
   └── Reasoning
```

AI-generated changes should NOT automatically modify source files in the initial version.

The tool should present the suggestion to the developer.

---

# 15. Reporting

The reporter converts findings into a developer-friendly terminal interface.

Example:

```text
╭─────────────────────────────────────╮
│       git-security-tool Security Scan     │
╰─────────────────────────────────────╯

Files analyzed: 3

Security:
  ❌ 1 HIGH
  ⚠  1 MEDIUM

Secrets:
  ✓ No secrets detected

Code Quality:
  ⚠ 2 issues

Commit blocked.

Recommended actions:
  • Remove hardcoded credential
  • Fix formatting issues
```

The reporter should eventually support multiple formats:

```text
terminal
JSON
SARIF
```

Terminal output is the initial priority.

---

# 16. Project Folder Structure

The planned structure is:

```text
git_security/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── docker.yml
│
├── src/
│   └── git_security/
│       ├── __init__.py
│       ├── cli.py
│       │
│       ├── git/
│       │   ├── __init__.py
│       │   ├── repository.py
│       │   ├── diff.py
│       │   └── hooks.py
│       │
│       ├── scanners/
│       │   ├── __init__.py
│       │   ├── semgrep.py
│       │   ├── gitleaks.py
│       │   └── ruff.py
│       │
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── findings.py
│       │   ├── severity.py
│       │   └── suggestions.py
│       │
│       ├── installer/
│       │   ├── __init__.py
│       │   ├── dependencies.py
│       │   └── git_hook.py
│       │
│       └── reporter/
│           ├── __init__.py
│           └── terminal.py
│
├── rules/
│   └── semgrep/
│       └── custom-security.yml
│
├── tests/
│   ├── test_git.py
│   ├── test_scanners.py
│   ├── test_analysis.py
│   └── test_installer.py
│
├── Dockerfile
├── .dockerignore
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

---

# 17. Python Packaging

git-security-tool will be distributed as a Python package.

The package metadata will be defined in:

```text
pyproject.toml
```

The package will eventually be published to PyPI.

The intended user experience is:

```bash
pip install git-security-tool
```

followed by:

```bash
cd my-project
git-security-tool install
```

The distinction is important:

```text
pip install git-security-tool
        │
        ▼
Install git-security-tool CLI globally/environment-wide

git-security-tool install
        │
        ▼
Configure git-security-tool for the current Git repository
```

---

# 18. Dependency Philosophy

Python dependencies should be declared through Python packaging.

External CLI dependencies such as:

```text
Semgrep
Gitleaks
Ruff
```

should be detected by git-security-tool.

The installer should provide clear information about missing dependencies.

git-security-tool should never silently install arbitrary system software without user awareness.

---

# 19. Docker

Docker-related files should remain separate from the Python source code.

Primary files:

```text
Dockerfile
.dockerignore
```

The Docker image should provide the environment required for CI execution.

The Docker image should be reproducible and version-controlled.

---

# 20. CI/CD Files

GitHub Actions workflows will live under:

```text
.github/workflows/
```

Example:

```text
ci.yml
docker.yml
```

Responsibilities:

### `ci.yml`

* install dependencies
* run tests
* run git-security-tool
* verify the project

### `docker.yml`

* build Docker image
* optionally run validation
* publish the image to a container registry

---

# 21. Security Principles

git-security-tool itself is a security-related tool, so its own implementation should follow secure development practices.

Important principles:

1. Never execute untrusted shell strings through a shell unnecessarily.
2. Prefer argument lists with `subprocess.run()`.
3. Validate paths.
4. Avoid exposing secrets in terminal output.
5. Do not send source code to an external LLM unless explicitly configured.
6. Make AI functionality optional.
7. Never automatically overwrite source files in the initial implementation.
8. Treat scanner output as untrusted data.
9. Use non-zero exit codes consistently.
10. Test security-critical behavior.

Example preferred pattern:

```python
subprocess.run(
    ["git", "diff", "--cached"],
    capture_output=True,
    text=True,
    check=False
)
```

rather than constructing arbitrary shell commands.

---

# 22. Development Philosophy

The project should be implemented incrementally.

Do not implement the complete architecture in one step.

Recommended order:

```text
Phase 1
Git fundamentals
        ↓
Phase 2
Python subprocess
        ↓
Phase 3
Read staged Git changes
        ↓
Phase 4
Build pre-commit hook
        ↓
Phase 5
Create basic CLI
        ↓
Phase 6
Integrate Semgrep
        ↓
Phase 7
Integrate Ruff
        ↓
Phase 8
Integrate Gitleaks
        ↓
Phase 9
Normalize findings
        ↓
Phase 10
PASS/BLOCK logic
        ↓
Phase 11
Terminal reporting
        ↓
Phase 12
Package for PyPI
        ↓
Phase 13
Docker
        ↓
Phase 14
GitHub Actions CI/CD
        ↓
Phase 15
AI suggestions
```

Each phase should be tested before moving to the next.

---

# 23. Current Scope

The initial implementation is:

```text
Linux
Python
Git
Git Hooks
Semgrep
Gitleaks
Ruff
Docker
GitHub Actions
PyPI
```

Kubernetes is intentionally excluded from the current scope.

Kubernetes may be considered only if the architecture later evolves into a centralized, distributed scanning service.

---

# 24. Target End-to-End Architecture

The final planned system is:

```text
                         DEVELOPER
                             │
                             ▼
                       Local Git Repo
                             │
                             ▼
                         git commit
                             │
                             ▼
                    pre-commit hook
                             │
                             ▼
                       git-security-tool
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           Semgrep        Gitleaks         Ruff
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                       Analysis Engine
                             │
                             ▼
                       Suggestion Engine
                             │
                             ▼
                          Reporter
                             │
                       ┌─────┴─────┐
                       ▼           ▼
                     PASS         FAIL
                       │           │
                       ▼           ▼
                    Commit       Block
                       │
                       ▼
                    git push
                       │
                       ▼
                     GitHub
                       │
                       ▼
                GitHub Actions
                       │
                       ▼
                     Docker
                       │
                       ▼
                  git-security-tool
                       │
                ┌──────┼──────┐
                ▼      ▼      ▼
              Tests  Security Quality
                │      │      │
                └──────┼──────┘
                       ▼
                    CI PASS
                       │
                       ▼
                 Docker Build
                       │
                       ▼
               Container Registry
```

This architecture should evolve as implementation progresses rather than being treated as a rigid design.
