#!/bin/sh
# Verify every bundled Semgrep rule fires, plus secret detection. Creates a
# throwaway git repo, drops one probe file per rule category and a fake
# secret, runs `git-security-tool scan --all`, then reports which of the 17
# rules were seen. Touches nothing in your real repositories.
#
#   ./scripts/probe.sh
set -eu

probe=$(mktemp -d)
trap 'rm -rf "$probe"' EXIT
cd "$probe"
git init -q
git config user.email probe@example.com
git config user.name probe

# match the real project's lint config so the output isn't full of ruff noise
cat > pyproject.toml <<'EOF'
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"]
EOF

cat > injection.py <<'EOF'
import os
import subprocess
eval(user_input)                       # python-dangerous-eval
exec(user_input)                       # python-dangerous-exec
os.system(cmd)                         # python-os-system
os.popen(cmd)                          # python-os-popen
subprocess.run(cmd, shell=True, check=True)   # python-subprocess-shell-true
EOF

cat > deserialization.py <<'EOF'
import pickle
import xml.etree.ElementTree as ET

import yaml
pickle.loads(blob)                     # python-pickle-load
yaml.load(text)                        # python-yaml-unsafe-load
ET.fromstring(untrusted_xml)           # python-insecure-xml-parser
EOF

cat > crypto_tls.py <<'EOF'
import hashlib
import ssl

import requests
hashlib.md5(b"x")                      # python-weak-hash
requests.get(u, verify=False, timeout=5)   # python-tls-verification-disabled
ssl._create_unverified_context()       # python-ssl-unverified-context
EOF

cat > web.py <<'EOF'
import jinja2
from django.utils.safestring import mark_safe
app.run(debug=True)                    # python-flask-debug-true
jinja2.Environment()                   # python-jinja-autoescape-disabled
mark_safe(user_input)                  # python-django-mark-safe
EOF

cat > filesystem_net.py <<'EOF'
import tempfile

import requests
archive.extractall(dest)               # python-archive-extractall
tempfile.mktemp()                      # python-tempfile-mktemp
requests.get(url)                      # python-requests-no-timeout
EOF

# Fake GitHub token - not a real credential; never leaves this temp repo.
# The gitleaks:allow marker keeps *this* script committable; the secrets.txt
# it writes has no such marker and is what the probe expects gitleaks to flag.
tok='ghp_016C7f4a9BdEfGhIjKlMnOpQrStUvWx0y1Z2a'  # gitleaks:allow
printf 'API_TOKEN=%s\n' "$tok" > secrets.txt

git add -A
out=$(git-security-tool scan --all 2>&1 || true)
printf '%s\n' "$out"

echo
echo "=================================================================="
rules="python-dangerous-eval python-dangerous-exec python-os-system \
python-os-popen python-subprocess-shell-true python-pickle-load \
python-yaml-unsafe-load python-insecure-xml-parser python-weak-hash \
python-tls-verification-disabled python-ssl-unverified-context \
python-flask-debug-true python-jinja-autoescape-disabled \
python-django-mark-safe python-archive-extractall python-tempfile-mktemp \
python-requests-no-timeout"

missing=0
for r in $rules; do
    if printf '%s' "$out" | grep -q "semgrep:$r"; then
        echo "  ok   $r"
    else
        echo "  MISS $r"
        missing=$((missing + 1))
    fi
done

if printf '%s' "$out" | grep -q "gitleaks:"; then
    echo "  ok   gitleaks secret detection"
else
    echo "  MISS gitleaks secret detection"
    missing=$((missing + 1))
fi

echo "=================================================================="
if [ "$missing" -eq 0 ]; then
    echo "All 17 rules + secret detection fired."
else
    echo "$missing check(s) missing - a rule regressed."
    exit 1
fi
