"""AskMeDB CLI — command-line tools for schema annotation, evaluation, and serving."""

import argparse
import sys


def main():
    """Main CLI entry point for askmedb."""
    parser = argparse.ArgumentParser(
        prog="askmedb",
        description="AskMeDB — natural-language database query tools",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register subcommands
    from .annotate import register as register_annotate
    from .eval import register as register_eval
    from .serve import register as register_serve

    register_annotate(subparsers)
    register_eval(subparsers)
    register_serve(subparsers)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)
