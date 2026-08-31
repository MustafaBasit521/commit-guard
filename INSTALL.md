# Installing and using git-security-tool

A detailed, step-by-step guide. If you just want the short version, see the
["Add it to a project"](README.md#add-it-to-a-project) section of the README.

There are two things to install, and then one command per repository:

1. **The tool itself** — a Python package, installed once per machine.
2. **Gitleaks** — a separate program for secret detection, once per machine.
3. **`git-security-tool install`** — run once inside each Git repo you want
   protected.

---

## Step 0 — Check the prerequisites

You need **Python 3.11 or newer** and **Git**. Check:

```bash
python3 --version      # must be 3.11.x or higher
git --version
```

If Python is older than 3.11, install a newer one (`sudo apt install
python3.12` on Ubuntu, or use [pyenv](https://github.com/pyenv/pyenv)).

---

## Step 1 — Install the tool

The pre-commit hook will call `git-security-tool` by name, so it has to be on
your `PATH` permanently — not inside a virtualenv you sometimes forget to
activate. **pipx** is the clean way to do this: it installs the tool in its
own isolated environment and puts just the command on your `PATH`.

### Option A — pipx (recommended)

```bash
# install pipx itself, once
python3 -m pip install --user pipx
python3 -m pipx ensurepath
# close and reopen your terminal here, so PATH updates

# install the tool (the [scanners] part also pulls in ruff + semgrep)
pipx install "git-security-tool[scanners]"
```

### Option B — plain pip (user install)

```bash
pip install --user "git-security-tool[scanners]"
```

Make sure `~/.local/bin` is on your `PATH` (pipx's `ensurepath` does this; for
plain pip you may need to add `export PATH="$HOME/.local/bin:$PATH"` to your
`~/.bashrc` and run `source ~/.bashrc`).

### Option C — inside a project virtualenv

Only if you always work with that venv activated:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "git-security-tool[scanners]"
```

### Verify

```bash
git-security-tool version
```

Should print something like `git-security-tool 0.1.2`. If you get
`command not found`, your `PATH` isn't picking up where it was installed —
reopen the terminal, or add the install location to `~/.bashrc`.

---

## Step 2 — Install Gitleaks (for secret detection)

Gitleaks is a single downloadable program (written in Go, not on PyPI). The
tool works without it, but then it can't catch leaked API keys / tokens.

### Linux (x64)

```bash
cd /tmp

# find and download the latest release
url=$(curl -s https://api.github.com/repos/gitleaks/gitleaks/releases/latest \
  | grep -o 'https://[^"]*linux_x64\.tar\.gz' | head -1)
curl -sL "$url" -o gitleaks.tar.gz

# unpack and move the binary somewhere on PATH
tar xzf gitleaks.tar.gz gitleaks
mkdir -p ~/.local/bin
mv gitleaks ~/.local/bin/

# check
gitleaks version
```

### macOS

```bash
brew install gitleaks
```

### Verify everything is visible

```bash
git-security-tool check
```

You'll see which scanners are present:

```
[git-security-tool] pre-commit hook: not installed
[git-security-tool] scanners:
  ruff: ok
  gitleaks: ok
  semgrep: ok
```

Any `missing` here just means that check is skipped — install it if you want
that coverage.

---

## Step 3 — Turn on the hook in a repository

Do this **once per repo** (the hook lives in `.git/hooks/`, which is not
committed, so a fresh `git clone` needs this again).

```bash
cd ~/path/to/your-project
git-security-tool install
```

Output:

```
[git-security-tool] installed pre-commit hook at .../.git/hooks/pre-commit
  ruff: ok
  gitleaks: ok
  semgrep: ok
```

If the repo already has a pre-commit hook that this tool didn't create, it
will refuse and tell you to re-run with `--force` (which replaces it).

---

## Step 4 — See it work

Now every `git commit` runs the scan first.

```bash
# make a file with an obvious problem
printf 'eval(input())\n' > _probe.py
git add _probe.py
git commit -m "test"
```

Expected — the commit is **blocked**:

```
[git-security-tool] pre-commit security scan
[git-security-tool] 1 file(s) to scan
[git-security-tool] 1 blocking finding(s):
  [HIGH] semgrep:python-dangerous-eval _probe.py:1 - eval() executes arbitrary
  code from its argument ...
[git-security-tool] commit blocked - fix the blocking findings above, or set
GIT_SECURITY_NO_BLOCK=1 to override
```

Clean up the probe:

```bash
git restore --staged _probe.py && rm _probe.py
```

A normal commit with no problems just passes through with
`commit allowed`.

---

## Step 5 — Adopting an existing project (optional but recommended)

An older codebase probably has findings already. You don't want to be blocked
on day one for issues you didn't just write.

```bash
cd ~/path/to/your-project

# 1. see what's there
git-security-tool scan --all

# 2. if there's a lot, record it as a "baseline" - those get grandfathered
git-security-tool baseline

# 3. commit the baseline file
git add .git-security-tool-baseline.json
git commit -m "add git-security-tool baseline"
```

From now on, **new** problems block; the recorded ones are ignored. As you
fix them, regenerate the baseline (`git-security-tool baseline` again) to
shrink it.

---

## Step 6 — Configuration (optional)

Create `.git-security-tool.toml` in the repo root:

```toml
[policy]
# what severity blocks a commit. HIGH (default) blocks secrets + RCE-class
# code. Use "CRITICAL" to only block secrets while you get used to it.
block_threshold = "HIGH"

[scanners]
# turn a scanner off entirely
# gitleaks = false

[ignore]
# skip generated code, migrations, vendored libraries, fixtures
paths = ["migrations/", "vendor/", "tests/fixtures/", "*.generated.py"]

[ai]
# optional: ask an LLM to explain and suggest a fix for blocking findings.
# off by default. also needs an API key in your environment.
enabled = false
provider = "gemini"          # or "anthropic"
```

Commit this file — it's meant to be shared across the team.

---

## Step 7 — Add the CI check

The local hook can be skipped (`git commit --no-verify`) or simply not
installed on a teammate's machine. CI is the layer nobody can bypass.

Create `.github/workflows/security.yml` in your project:

```yaml
name: security
on: [push, pull_request]

jobs:
  security:
    uses: MustafaBasit521/commit-guard/.github/workflows/scan.reusable.yml@main
```

Commit and push it. GitHub will run `git-security-tool scan --all` over the
whole repo on every push and pull request, and the check fails if there's a
blocking finding.

---

## Troubleshooting

**`git commit` doesn't run any scan / no `[git-security-tool]` output**
The hook isn't installed, or the tool isn't on `PATH` in that shell. Run
`git-security-tool check` and `which git-security-tool`. If `check` says
"not installed", run `git-security-tool install`.

**Hook prints "git-security-tool not on PATH - skipping scan"**
The hook ran but couldn't find the command. This happens when you installed
into a virtualenv that isn't active, or `~/.local/bin` isn't on `PATH`. Use
pipx (Step 1, Option A), or add the install location to `~/.bashrc`.

**Committing from VS Code / a Git GUI does nothing**
GUI apps sometimes don't inherit your shell `PATH`. Install with pipx so the
command lives in `~/.local/bin`, restart the app, and make sure that
directory is on the system `PATH`.

**`command not found: git-security-tool` right after installing**
Reopen your terminal (pipx updates `PATH` in a way the current shell hasn't
picked up), or run `python3 -m pipx ensurepath` again.

**A commit is blocked and I need to commit anyway (emergency)**
```bash
GIT_SECURITY_NO_BLOCK=1 git commit -m "..."   # runs the scan, reports, doesn't block
git commit --no-verify -m "..."               # skips the hook entirely
```
Use these sparingly — CI will still catch it.

**Remove the tool from a repo**
```bash
git-security-tool uninstall
```

**Uninstall completely**
```bash
pipx uninstall git-security-tool     # or: pip uninstall git-security-tool
```
