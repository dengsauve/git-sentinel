"""CLI entrypoint for git-sentinel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from git_sentinel.config import ConfigError, load_config
from git_sentinel.logging_config import configure_logging
from git_sentinel.service import SentinelService


def build_parser() -> argparse.ArgumentParser:
    """Build the root CLI parser."""

    parser = argparse.ArgumentParser(prog="git-sentinel")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in ("validate", "run", "once"):
        command_parser = subparsers.add_parser(command_name)
        command_parser.add_argument("--config", required=True, type=Path)
        if command_name == "once":
            command_parser.add_argument("--repo", dest="repository_name")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.command == "validate":
        print(f"configuration is valid: {args.config}")
        return 0

    service = SentinelService(config)
    if args.command == "once":
        try:
            service.run_once(repository_name=args.repository_name)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    service.install_signal_handlers()
    service.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
