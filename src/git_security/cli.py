"""Command-line interface for git-security-tool.

Thin layer: parse arguments, dispatch to an action, return an exit code.
All real work lives in the modules this calls. argparse (stdlib) is enough
for the handful of subcommands we have - no CLI framework needed yet.
"""

import argparse

from git_security import __version__
from git_security.installer.git_hook import install, status, uninstall
from git_security.scan import run_scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-security-tool",
        description="Local Git security & code-quality gate (pre-commit).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "scan",
        help="scan the staged changes; exit non-zero if policy blocks",
    )

    install_parser = subparsers.add_parser(
        "install", help="install the pre-commit hook into this repository"
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing hook not managed by git-security-tool",
    )

    subparsers.add_parser(
        "uninstall", help="remove the pre-commit hook from this repository"
    )
    subparsers.add_parser(
        "check", help="report pre-commit hook and scanner status"
    )
    subparsers.add_parser("version", help="print the version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "scan":
        return run_scan()
    if args.command == "install":
        return install(force=args.force)
    if args.command == "uninstall":
        return uninstall()
    if args.command == "check":
        return status()
    if args.command == "version":
        print(f"git-security-tool {__version__}")
        return 0

    # argparse enforces `required=True`, so this is unreachable.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
