"""Make the ``src/`` layout importable during tests.

Until we have a proper ``pyproject.toml`` (milestone 9) and ``pip install
-e .``, tests need ``src`` on the path the same way the pre-commit hook sets
PYTHONPATH. This file is auto-loaded by pytest before collecting tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
