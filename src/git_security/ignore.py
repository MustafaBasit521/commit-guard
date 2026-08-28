"""Skip staged paths that match the config's ignore patterns.

Patterns are matched against repo-relative POSIX paths:

* ``tests/fixtures/``  - trailing slash means "anything under this directory"
* ``*.generated.py``   - fnmatch glob (``*`` also spans ``/``)
* ``migrations``       - a plain name matches that path and everything under it
"""

from fnmatch import fnmatch


def _matches(path: str, pattern: str) -> bool:
    pattern = pattern.rstrip("/")
    if not pattern:
        return False
    return fnmatch(path, pattern) or fnmatch(path, f"{pattern}/*")


def is_ignored(path: str, patterns: tuple[str, ...]) -> bool:
    return any(_matches(path, pattern) for pattern in patterns)


def filter_ignored(files: list[str], patterns: tuple[str, ...]) -> list[str]:
    if not patterns:
        return list(files)
    return [f for f in files if not is_ignored(f, patterns)]
