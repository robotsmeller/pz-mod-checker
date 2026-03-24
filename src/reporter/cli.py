"""CLI table output for scan results."""

from __future__ import annotations

from ..rules.engine import Finding


# ANSI color codes
COLORS = {
    "breaking": "\033[91m",  # Red
    "warning": "\033[93m",   # Yellow
    "info": "\033[96m",      # Cyan
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
}


def format_severity(severity: str, use_color: bool = True) -> str:
    """Format a severity label with optional color."""
    label = severity.upper()
    if not use_color:
        return f"[{label}]"
    color = COLORS.get(severity, "")
    return f"{color}[{label}]{COLORS['reset']}"


def print_scan_results(
    results: dict[str, list[Finding]],
    use_color: bool = True,
    verbose: bool = False,
) -> None:
    """Print scan results as a formatted CLI table."""
    if not results:
        msg = "No compatibility issues found."
        if use_color:
            print(f"\033[92m{msg}\033[0m")  # Green
        else:
            print(msg)
        return

    total_findings = sum(len(f) for f in results.values())
    breaking = sum(1 for fs in results.values() for f in fs if f.severity == "breaking")
    warnings = sum(1 for fs in results.values() for f in fs if f.severity == "warning")
    infos = sum(1 for fs in results.values() for f in fs if f.severity == "info")

    # Header
    print()
    _print_header(f"PZ Mod Checker — {total_findings} issues in {len(results)} mods", use_color)
    print()

    # Summary bar
    parts = []
    if breaking:
        parts.append(f"{format_severity('breaking', use_color)} {breaking}")
    if warnings:
        parts.append(f"{format_severity('warning', use_color)} {warnings}")
    if infos:
        parts.append(f"{format_severity('info', use_color)} {infos}")
    print("  ".join(parts))
    print()

    # Per-mod details
    for mod_id, findings in sorted(results.items()):
        mod_name = findings[0].mod_name if findings else mod_id
        _print_mod_section(mod_id, mod_name, findings, use_color, verbose)


def _print_header(text: str, use_color: bool) -> None:
    """Print a styled header line."""
    width = max(len(text) + 4, 60)
    line = "=" * width
    if use_color:
        print(f"{COLORS['bold']}{line}{COLORS['reset']}")
        print(f"{COLORS['bold']}  {text}{COLORS['reset']}")
        print(f"{COLORS['bold']}{line}{COLORS['reset']}")
    else:
        print(line)
        print(f"  {text}")
        print(line)


def _print_mod_section(
    mod_id: str,
    mod_name: str,
    findings: list[Finding],
    use_color: bool,
    verbose: bool,
) -> None:
    """Print findings for a single mod."""
    # Mod header
    if use_color:
        print(f"  {COLORS['bold']}{mod_name}{COLORS['reset']} ({mod_id})")
    else:
        print(f"  {mod_name} ({mod_id})")

    for finding in findings:
        severity = format_severity(finding.severity, use_color)
        print(f"    {severity} {finding.message}")

        if verbose:
            if finding.file_path:
                rel_path = finding.file_path
                loc = f"{rel_path}:{finding.line_number}" if finding.line_number else rel_path
                if use_color:
                    print(f"      {COLORS['dim']}at {loc}{COLORS['reset']}")
                else:
                    print(f"      at {loc}")

            if finding.line_text:
                if use_color:
                    print(f"      {COLORS['dim']}> {finding.line_text[:100]}{COLORS['reset']}")
                else:
                    print(f"      > {finding.line_text[:100]}")

            if finding.suggestion:
                if use_color:
                    print(f"      {COLORS['dim']}fix: {finding.suggestion}{COLORS['reset']}")
                else:
                    print(f"      fix: {finding.suggestion}")

            if finding.context:
                if use_color:
                    print(f"      {COLORS['dim']}note: {finding.context}{COLORS['reset']}")
                else:
                    print(f"      note: {finding.context}")

    print()
