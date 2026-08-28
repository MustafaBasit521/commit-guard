"""Tests for the argparse layer in cli.py."""

import pytest

from git_security import __version__
from git_security.cli import build_parser, main


def test_version_command(capsys):
    assert main(["version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_no_subcommand_errors(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_scan_parses_all_flag():
    args = build_parser().parse_args(["scan", "--all"])
    assert args.command == "scan"
    assert args.scan_all is True


def test_scan_defaults_to_staged():
    args = build_parser().parse_args(["scan"])
    assert args.scan_all is False


def test_install_parses_force_flag():
    args = build_parser().parse_args(["install", "--force"])
    assert args.command == "install"
    assert args.force is True
