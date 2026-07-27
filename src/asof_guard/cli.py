"""Command-line interface for AsOfGuard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence, TextIO

from . import __version__
from .fixture_library import fixture_catalog, fixture_text, load_fixture
from .models import TraceFormatError
from .parser import load_trace, parse_trace
from .reporting import SUPPORTED_FORMATS, render_verdict
from .rules import explain_rule, iter_rules
from .verifier import verify_trace


INPUT_ERROR = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asof-guard",
        description="Verify temporal integrity of RAG and agent-memory JSONL traces.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="verify a JSONL trace")
    verify_parser.add_argument("trace", nargs="?", help="trace path, or - for standard input")
    verify_parser.add_argument("--fixture", metavar="NAME", help="verify a packaged fixture")
    verify_parser.add_argument(
        "--format",
        choices=SUPPORTED_FORMATS,
        default="text",
        help="report format (default: text)",
    )
    verify_parser.add_argument("--output", metavar="PATH", help="write the report to a file")

    fixtures_parser = subparsers.add_parser("fixtures", help="inspect synthetic fixture traces")
    fixture_subparsers = fixtures_parser.add_subparsers(dest="fixtures_command", required=True)
    fixture_list = fixture_subparsers.add_parser("list", help="list packaged fixtures")
    fixture_list.add_argument("--format", choices=("text", "json"), default="text")
    fixture_show = fixture_subparsers.add_parser("show", help="print a fixture's JSONL")
    fixture_show.add_argument("name")

    explain_parser = subparsers.add_parser("explain", help="explain verifier rules")
    explain_parser.add_argument("code", nargs="?", help="rule code; omit to list all rules")
    explain_parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _write_output(content: str, output_path: Optional[str]) -> None:
    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)


def _verify(args: argparse.Namespace) -> int:
    if bool(args.trace) == bool(args.fixture):
        raise TraceFormatError("verify requires exactly one TRACE path or --fixture NAME")
    if args.fixture:
        try:
            trace = load_fixture(args.fixture)
        except KeyError as exc:
            raise TraceFormatError(f"unknown fixture: {args.fixture}") from exc
    elif args.trace == "-":
        trace = parse_trace(sys.stdin, source="<stdin>")
    else:
        trace = load_trace(args.trace)
    verdict = verify_trace(trace)
    _write_output(render_verdict(verdict, args.format), args.output)
    return verdict.exit_code


def _fixtures(args: argparse.Namespace) -> int:
    if args.fixtures_command == "show":
        try:
            sys.stdout.write(fixture_text(args.name))
        except KeyError as exc:
            raise TraceFormatError(f"unknown fixture: {args.name}") from exc
        return 0

    catalog = fixture_catalog()
    if args.format == "json":
        sys.stdout.write(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    else:
        for entry in catalog:
            codes = ",".join(entry["expected_codes"]) or "none"
            sys.stdout.write(
                f"{entry['name']:<38} {str(entry['expected_status']):<13} {codes}\n"
                f"  {entry['description']}\n"
            )
        sys.stdout.write(f"\n{len(catalog)} fixture(s)\n")
    return 0


def _explain(args: argparse.Namespace) -> int:
    if args.code:
        try:
            details = explain_rule(args.code)
        except KeyError as exc:
            raise TraceFormatError(f"unknown rule code: {args.code}") from exc
        entries = [(args.code.strip().upper(), details)]
    else:
        entries = list(iter_rules())

    if args.format == "json":
        payload = {code: dict(details) for code, details in entries}
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        for index, (code, details) in enumerate(entries):
            if index:
                sys.stdout.write("\n")
            sys.stdout.write(f"{code}: {details['title']}\n")
            sys.stdout.write(f"  {details['description']}\n")
            sys.stdout.write(f"  Remediation: {details['remediation']}\n")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return a process exit code."""

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "verify":
            return _verify(args)
        if args.command == "fixtures":
            return _fixtures(args)
        if args.command == "explain":
            return _explain(args)
        parser.error("missing command")
        return INPUT_ERROR
    except SystemExit as exc:
        return 0 if exc.code == 0 else INPUT_ERROR
    except (TraceFormatError, OSError, ValueError) as exc:
        sys.stderr.write(f"asof-guard: error: {exc}\n")
        return INPUT_ERROR
    except BrokenPipeError:
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
