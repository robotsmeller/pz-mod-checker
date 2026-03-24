"""PZ Mod Checker — CLI entry point with subcommands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def get_data_dir() -> Path:
    """Locate the data/ directory relative to this file."""
    return Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Subcommand: scan (default)
# ---------------------------------------------------------------------------

def _add_scan_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("scan", help="Scan mods for compatibility issues.")
    p.add_argument("target_version", help="PZ version to check against (e.g., 42.3.1)")
    p.add_argument("--mod-dir", type=Path, action="append", default=None,
                    help="Directory containing mods (repeatable). Uses defaults if omitted.")
    p.add_argument("--mod", type=Path, default=None,
                    help="Check a single mod directory.")
    p.add_argument("--data-dir", type=Path, default=None,
                    help="Path to data/ directory with rules.")
    p.add_argument("--format", choices=["cli", "json"], default="cli",
                    help="Output format (default: cli).")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    p.add_argument("--verbose", "-v", action="store_true",
                    help="Show file paths, line numbers, and suggestions.")
    p.add_argument("--severity", choices=["all", "breaking", "warning", "info"],
                    default="all", help="Minimum severity to show (default: all).")
    p.add_argument("--check-workshop", action="store_true",
                    help="Query Steam Workshop for mod update status.")
    p.add_argument("--no-cache", action="store_true",
                    help="Skip Workshop cache, fetch fresh data.")
    p.set_defaults(func=_cmd_scan)


def _cmd_scan(args: argparse.Namespace) -> int:
    from .reporter.cli import print_scan_results
    from .reporter.json_out import findings_to_json
    from .rules.engine import check_all_mods
    from .rules.loader import load_ruleset
    from .rules.version import PZVersion
    from .scanner.discovery import discover_mods, discover_single_mod

    target = PZVersion.parse(args.target_version)

    data_dir = args.data_dir or get_data_dir()
    if not data_dir.is_dir():
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        return 1

    ruleset = load_ruleset(data_dir)
    if not ruleset.rules and not ruleset.no_comp:
        print("Warning: No rules loaded. Check your data/ directory.", file=sys.stderr)

    if args.mod:
        mod = discover_single_mod(args.mod)
        if mod is None:
            print(f"Error: Not a valid mod directory: {args.mod}", file=sys.stderr)
            return 1
        mods = [mod]
    else:
        mods = discover_mods(args.mod_dir)

    if not mods:
        print("No mods found.", file=sys.stderr)
        return 0

    results = check_all_mods(mods, ruleset, target)

    # Filter by severity
    severity_order = {"breaking": 0, "warning": 1, "info": 2}
    if args.severity != "all":
        min_level = severity_order.get(args.severity, 2)
        results = {
            mod_id: [f for f in findings if severity_order.get(f.severity, 2) <= min_level]
            for mod_id, findings in results.items()
        }
        results = {k: v for k, v in results.items() if v}

    # Output scan results
    if args.format == "json":
        print(findings_to_json(results))
    else:
        use_color = not args.no_color
        print_scan_results(results, use_color=use_color, verbose=args.verbose)

    # Workshop enrichment
    if args.check_workshop:
        from .workshop import check_workshop_updates
        suggestions, _ = check_workshop_updates(mods, use_cache=not args.no_cache)
        if suggestions:
            _print_workshop_suggestions(suggestions, use_color=not args.no_color)

    has_breaking = any(
        f.severity == "breaking"
        for findings in results.values()
        for f in findings
    )
    return 1 if has_breaking else 0


# ---------------------------------------------------------------------------
# Subcommand: diagnose
# ---------------------------------------------------------------------------

def _add_diagnose_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("diagnose", help="Parse last PZ session logs for mod errors.")
    p.add_argument("--zomboid-dir", type=Path, default=None,
                    help="Zomboid user directory (auto-detected if omitted).")
    p.add_argument("--log", type=Path, default=None,
                    help="Path to a specific console.txt file.")
    p.add_argument("--mod-dir", type=Path, action="append", default=None,
                    help="Mod directories for name resolution (repeatable).")
    p.add_argument("--auto-disable", action="store_true",
                    help="Offer to disable mods that caused errors.")
    p.add_argument("--format", choices=["cli", "json"], default="cli",
                    help="Output format (default: cli).")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    p.set_defaults(func=_cmd_diagnose)


def _cmd_diagnose(args: argparse.Namespace) -> int:
    from .diagnose import (
        build_name_to_id_map,
        get_console_log,
        parse_console_log,
        resolve_mod_names,
    )

    # Determine log path
    if args.log:
        log_path = args.log
    else:
        log_path = get_console_log(args.zomboid_dir)

    if not log_path.is_file():
        print(f"Error: Console log not found: {log_path}", file=sys.stderr)
        return 1

    diagnosis = parse_console_log(log_path)

    # Resolve mod names to IDs
    name_to_id = build_name_to_id_map(args.mod_dir)
    resolve_mod_names(diagnosis, name_to_id)

    if args.format == "json":
        import json
        from dataclasses import asdict
        print(json.dumps(asdict(diagnosis), indent=2, default=str))
        return 1 if diagnosis.mod_errors else 0

    # CLI output
    use_color = not args.no_color
    _print_diagnosis(diagnosis, use_color)

    # Auto-disable offer
    if args.auto_disable and diagnosis.mod_errors:
        _offer_auto_disable(diagnosis, name_to_id, args.zomboid_dir)

    return 1 if diagnosis.mod_errors else 0


# ---------------------------------------------------------------------------
# Subcommand: manage
# ---------------------------------------------------------------------------

def _add_manage_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("manage", help="Enable/disable mods and manage profiles.")
    p.add_argument("--zomboid-dir", type=Path, default=None,
                    help="Zomboid user directory (auto-detected if omitted).")
    p.add_argument("--mod-dir", type=Path, action="append", default=None,
                    help="Mod directories for discovery (repeatable).")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")

    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", dest="list_mods",
                       help="List all mods with enabled/disabled status.")
    group.add_argument("--enable", nargs="+", metavar="MOD_ID",
                       help="Enable specific mods.")
    group.add_argument("--disable", nargs="+", metavar="MOD_ID",
                       help="Disable specific mods.")
    group.add_argument("--enable-only", nargs="+", metavar="MOD_ID",
                       help="Enable ONLY these mods, disable all others.")
    group.add_argument("--disable-all", action="store_true",
                       help="Disable all mods.")
    group.add_argument("--disable-breaking", action="store_true",
                       help="Disable mods flagged as breaking by diagnose.")
    group.add_argument("--profile-save", metavar="NAME",
                       help="Save current mod list as a named profile.")
    group.add_argument("--profile-load", metavar="NAME",
                       help="Load a named profile.")
    group.add_argument("--profile-list", action="store_true",
                       help="List all saved profiles.")
    p.set_defaults(func=_cmd_manage)


def _cmd_manage(args: argparse.Namespace) -> int:
    from .manager import (
        disable_mods,
        enable_mods,
        enable_only,
        get_mod_status,
        list_profiles,
        load_profile,
        read_mod_list,
        save_profile,
        write_mod_list,
    )

    from .manager import get_default_txt_path

    zomboid_dir = args.zomboid_dir
    default_txt = get_default_txt_path(zomboid_dir)

    if args.list_mods:
        statuses = get_mod_status(zomboid_dir, args.mod_dir)
        if not statuses:
            print("No mods found.")
            return 0
        enabled_count = sum(1 for s in statuses if s["enabled"])
        print(f"\nMods: {len(statuses)} total, {enabled_count} enabled\n")
        for s in statuses:
            marker = "[ON] " if s["enabled"] else "[OFF]"
            print(f"  {marker} {s['mod_id']}")
        print()
        return 0

    if args.enable:
        mod_list = enable_mods(args.enable, path=default_txt)
        print(f"Enabled {len(args.enable)} mod(s). Total active: {len(mod_list.mods)}")
        return 0

    if args.disable:
        mod_list = disable_mods(args.disable, path=default_txt)
        print(f"Disabled {len(args.disable)} mod(s). Total active: {len(mod_list.mods)}")
        return 0

    if args.enable_only:
        mod_list = enable_only(args.enable_only, path=default_txt)
        print(f"Enabled {len(args.enable_only)} mod(s) exclusively. Total active: {len(mod_list.mods)}")
        return 0

    if args.disable_all:
        mod_list = enable_only([], path=default_txt)
        print(f"All mods disabled. Total active: {len(mod_list.mods)}")
        return 0

    if args.disable_breaking:
        return _disable_breaking_mods(zomboid_dir, args.mod_dir)

    if args.profile_save:
        save_profile(args.profile_save, zomboid_dir=zomboid_dir)
        print(f"Profile '{args.profile_save}' saved.")
        return 0

    if args.profile_load:
        try:
            mod_list = load_profile(args.profile_load, zomboid_dir=zomboid_dir)
            print(f"Profile '{args.profile_load}' loaded. {len(mod_list.mods)} mods active.")
        except KeyError:
            print(f"Error: Profile '{args.profile_load}' not found.", file=sys.stderr)
            return 1
        return 0

    if args.profile_list:
        profiles = list_profiles(zomboid_dir)
        if not profiles:
            print("No profiles found.")
            return 0
        print(f"\nProfiles ({len(profiles)}):\n")
        for prof in profiles:
            print(f"  {prof.name} ({len(prof.mod_ids)} mods)")
        print()
        return 0

    return 0


def _disable_breaking_mods(zomboid_dir: Path | None, mod_dirs: list[Path] | None) -> int:
    """Diagnose last session and disable mods that caused errors."""
    from .diagnose import build_name_to_id_map, get_console_log, parse_console_log, resolve_mod_names
    from .manager import disable_mods, get_default_txt_path

    log_path = get_console_log(zomboid_dir)
    if not log_path.is_file():
        print("Error: No console.txt found. Run PZ first.", file=sys.stderr)
        return 1

    diagnosis = parse_console_log(log_path)
    name_to_id = build_name_to_id_map(mod_dirs)
    resolve_mod_names(diagnosis, name_to_id)

    # Collect mod IDs that caused errors
    to_disable: list[str] = []
    for error in diagnosis.mod_errors:
        if error.mod_id and error.mod_id not in to_disable:
            to_disable.append(error.mod_id)

    if not to_disable:
        print("No mod errors found in last session, nothing to disable.")
        return 0

    default_txt = get_default_txt_path(zomboid_dir)
    mod_list = disable_mods(to_disable, path=default_txt)
    print(f"Disabled {len(to_disable)} breaking mod(s): {', '.join(to_disable)}")
    print(f"Total active: {len(mod_list.mods)}")
    return 0


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_diagnosis(diagnosis, use_color: bool = True) -> None:
    """Print diagnosis results to terminal."""
    from .diagnose import SessionDiagnosis

    C_RED = "\033[91m" if use_color else ""
    C_YEL = "\033[93m" if use_color else ""
    C_CYA = "\033[96m" if use_color else ""
    C_GRN = "\033[92m" if use_color else ""
    C_BLD = "\033[1m" if use_color else ""
    C_DIM = "\033[2m" if use_color else ""
    C_RST = "\033[0m" if use_color else ""

    if use_color and sys.stdout.isatty() is False:
        C_RED = C_YEL = C_CYA = C_GRN = C_BLD = C_DIM = C_RST = ""

    print()
    print(f"{C_BLD}PZ Mod Checker — Diagnosis{C_RST}")
    print(f"  Session: {diagnosis.session_start}")
    print(f"  PZ version: {diagnosis.pz_version}")
    print(f"  Mods loaded: {len(diagnosis.mods_loaded)}")
    print(f"  Require failures: {len(diagnosis.require_failures)}")
    print()

    if not diagnosis.mod_errors:
        print(f"  {C_GRN}No mod errors found in last session.{C_RST}")
        print()
        return

    print(f"  {C_RED}{C_BLD}{len(diagnosis.mod_errors)} errors across "
          f"{len(diagnosis.error_count_by_mod)} mod(s):{C_RST}")
    print()

    for mod_name, count in sorted(
        diagnosis.error_count_by_mod.items(), key=lambda x: -x[1]
    ):
        # Find first error for this mod to show details
        first_error = next(e for e in diagnosis.mod_errors if e.mod_name == mod_name)
        mod_id_str = f" ({first_error.mod_id})" if first_error.mod_id else ""

        print(f"  {C_RED}[ERROR]{C_RST} {C_BLD}{mod_name}{C_RST}{mod_id_str} — {count} error(s)")
        print(f"    {C_DIM}{first_error.error_message}{C_RST}")
        if first_error.stack_frames:
            frame = first_error.stack_frames[0]
            print(f"    {C_DIM}at {frame.file_name}:{frame.line_number}{C_RST}")
        print()

    if diagnosis.require_failures:
        # Deduplicate
        unique = sorted(set(rf.module_path for rf in diagnosis.require_failures))
        print(f"  {C_YEL}[WARN]{C_RST} {len(unique)} missing require() modules:")
        for mod_path in unique[:10]:
            print(f"    {C_DIM}{mod_path}{C_RST}")
        if len(unique) > 10:
            print(f"    {C_DIM}... and {len(unique) - 10} more{C_RST}")
        print()


def _print_workshop_suggestions(suggestions, use_color: bool = True) -> None:
    """Print Workshop suggestions to terminal."""
    C_YEL = "\033[93m" if use_color else ""
    C_GRN = "\033[92m" if use_color else ""
    C_DIM = "\033[2m" if use_color else ""
    C_BLD = "\033[1m" if use_color else ""
    C_RST = "\033[0m" if use_color else ""

    if use_color and sys.stdout.isatty() is False:
        C_YEL = C_GRN = C_DIM = C_BLD = C_RST = ""

    investigate = [s for s in suggestions if s.action == "investigate"]
    ok = [s for s in suggestions if s.action == "likely_ok"]
    no_data = [s for s in suggestions if s.action == "no_data"]

    print()
    print(f"{C_BLD}Workshop Status{C_RST}")
    print(f"  {len(ok)} likely OK, {len(investigate)} need investigation, {len(no_data)} no data")
    print()

    if investigate:
        for s in investigate:
            print(f"  {C_YEL}[?]{C_RST} {s.mod_name} ({s.mod_id})")
            print(f"    {C_DIM}{s.detail}{C_RST}")
        print()


def _offer_auto_disable(diagnosis, name_to_id: dict[str, str], zomboid_dir: Path | None) -> None:
    """Prompt user to disable mods that caused errors."""
    from .manager import disable_mods, save_profile

    to_disable = []
    for error in diagnosis.mod_errors:
        if error.mod_id and error.mod_id not in to_disable:
            to_disable.append(error.mod_id)

    if not to_disable:
        print("Cannot auto-disable: unable to resolve mod IDs for erroring mods.")
        return

    print(f"Disable these {len(to_disable)} mod(s)?")
    for mid in to_disable:
        print(f"  - {mid}")

    try:
        answer = input("\n[y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nSkipped.")
        return

    if answer == "y":
        # Save a backup profile first
        save_profile("pre-fix-auto", zomboid_dir=zomboid_dir)
        mod_list = disable_mods(to_disable, zomboid_dir=zomboid_dir)
        print(f"Disabled {len(to_disable)} mod(s). Profile 'pre-fix-auto' saved.")
        print(f"Total active: {len(mod_list.mods)}")
    else:
        print("Skipped.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="pz-mod-checker",
        description="Project Zomboid mod compatibility scanner, log diagnostics, and mod manager.",
    )

    subparsers = parser.add_subparsers(dest="command")
    _add_scan_parser(subparsers)
    _add_diagnose_parser(subparsers)
    _add_manage_parser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
