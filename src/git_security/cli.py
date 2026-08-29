"""Command-line interface for git-security-tool.

Thin layer: parse arguments, dispatch to an action, return an exit code.
All real work lives in the modules this calls. argparse (stdlib) is enough
for the handful of subcommands we have - no CLI framework needed yet.
"""

import argparse

from git_security import __version__
from git_security.installer.git_hook import install, status, uninstall
from git_security.scan import run_scan, write_baseline_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-security-tool",
        description="Local Git security & code-quality gate (pre-commit).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan",
        help="scan staged changes (or --all tracked files); non-zero if blocked",
    )
    scan_parser.add_argument(
        "--all",
        action="store_true",
        dest="scan_all",
        help="scan every tracked file in the working tree (for CI / audits)",
    )
    scan_parser.add_argument(
        "--format",
        choices=("text", "sarif"),
        default="text",
        dest="output_format",
        help="output format (sarif goes to stdout for GitHub code scanning)",
    )

    subparsers.add_parser(
        "baseline",
        help="record current findings so future scans ignore them",
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
    subparsers.add_parser("check", help="report pre-commit hook and scanner status")
    subparsers.add_parser("version", help="print the version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "scan":
        return run_scan(
            scope="all" if args.scan_all else "staged",
            output_format=args.output_format,
        )
    if args.command == "baseline":
        return write_baseline_file()
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
