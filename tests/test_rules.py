"""The bundled Semgrep rules must stay valid and keep catching the basics."""

import shutil
import subprocess

import pytest

from git_security.scan import _semgrep_rules_dir

pytestmark = pytest.mark.skipif(
    shutil.which("semgrep") is None, reason="semgrep not installed"
)


def _semgrep(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["semgrep", *args, "--metrics=off", "--quiet"],
        capture_output=True,
        text=True,
    )


def test_bundled_rules_validate():
    result = _semgrep("--validate", "--config", str(_semgrep_rules_dir()))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ("import pickle\npickle.loads(x)\n", "python-pickle-load"),
        ("import yaml\nyaml.load(x)\n", "python-yaml-unsafe-load"),
        ("import hashlib\nhashlib.md5(b'x')\n", "python-weak-hash"),
        ("import os\nos.system(cmd)\n", "python-os-system"),
        (
            "import requests\nrequests.get(u, verify=False)\n",
            "python-tls-verification-disabled",
        ),
    ],
)
def test_rule_fires(tmp_path, code, rule):
    sample = tmp_path / "sample.py"
    sample.write_text(code)
    result = _semgrep("--config", str(_semgrep_rules_dir()), "--json", str(sample))
    assert rule in result.stdout
