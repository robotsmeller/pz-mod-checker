"""PZ Mod Checker — CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .reporter.cli import print_scan_results
from .reporter.json_out import findings_to_json
from .rules.engine import check_all_mods
from .rules.loader import load_ruleset
from .rules.version import PZVersion
from .scanner.discovery import discover_mods, discover_single_mod


def get_data_dir() -> Path:
    """Locate the data/ directory relative to this file."""
    # Walk up from src/cli.py to project root, then into data/
    return Path(__file__).resolve().parent.parent / "data"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pz-mod-checker",
        description="Check Project Zomboid mods for compatibility issues with a target PZ version.",
    )

    parser.add_argument(
        "target_version",
        help="PZ version to check against (e.g., 42.3.1)",
    )

    parser.add_argument(
        "--mod-dir",
        type=Path,
        action="append",
        default=None,
        help="Directory containing mods (can be specified multiple times). Uses defaults if omitted.",
    )

    parser.add_argument(
        "--mod",
        type=Path,
        default=None,
        help="Check a single mod directory instead of scanning all.",
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to data/ directory with rules. Auto-detected if omitted.",
    )

    parser.add_argument(
        "--format",
        choices=["cli", "json"],
        default="cli",
        help="Output format (default: cli).",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output.",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show file paths, line numbers, and suggestions.",
    )

    parser.add_argument(
        "--severity",
        choices=["all", "breaking", "warning", "info"],
        default="all",
        help="Minimum severity to show (default: all).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Parse target version
    target = PZVersion.parse(args.target_version)

    # Load rules
    data_dir = args.data_dir or get_data_dir()
    if not data_dir.is_dir():
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        return 1

    ruleset = load_ruleset(data_dir)
    if not ruleset.rules and not ruleset.no_comp:
        print("Warning: No rules loaded. Check your data/ directory.", file=sys.stderr)

    # Discover mods
    if args.mod:
        mod = discover_single_mod(args.mod)
        if mod is None:
            print(f"Error: Not a valid mod directory: {args.mod}", file=sys.stderr)
            return 1
        mods = [mod]
    else:
        mod_dirs = args.mod_dir  # None means use defaults
        mods = discover_mods(mod_dirs)

    if not mods:
        print("No mods found.", file=sys.stderr)
        return 0

    # Run checks
    results = check_all_mods(mods, ruleset, target)

    # Filter by severity
    severity_order = {"breaking": 0, "warning": 1, "info": 2}
    if args.severity != "all":
        min_level = severity_order.get(args.severity, 2)
        results = {
            mod_id: [f for f in findings if severity_order.get(f.severity, 2) <= min_level]
            for mod_id, findings in results.items()
        }
        # Remove mods with no remaining findings
        results = {k: v for k, v in results.items() if v}

    # Output
    if args.format == "json":
        print(findings_to_json(results))
    else:
        use_color = not args.no_color
        print_scan_results(results, use_color=use_color, verbose=args.verbose)

    # Exit code: 1 if breaking issues found, 0 otherwise
    has_breaking = any(
        f.severity == "breaking"
        for findings in results.values()
        for f in findings
    )
    return 1 if has_breaking else 0


if __name__ == "__main__":
    sys.exit(main())
