"""Rule engine — applies rules to scanned mods and produces findings."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ..scanner.lua_reader import (
    check_file_encoding,
    find_lua_files,
    find_script_files,
    find_translation_files,
)
from ..scanner.mod_info import ModInfo
from .loader import NoCompEntry, Rule, RuleSet
from .version import PZVersion

FileCache = dict[Path, list[str]]


@dataclass
class Finding:
    """A compatibility issue found in a mod."""

    mod_id: str
    mod_name: str
    rule_id: str
    severity: str  # breaking, warning, info
    message: str
    file_path: str | None = None
    line_number: int | None = None
    line_text: str | None = None
    context: str | None = None
    suggestion: str | None = None
    confidence: str = "likely"  # certain, likely, speculative
    group: str = ""  # rule group for collapsing related findings


def _make_finding(
    mod: ModInfo,
    rule: Rule | None,
    *,
    rule_id: str = "",
    severity: str = "",
    message: str = "",
    file_path: str | None = None,
    line_number: int | None = None,
    line_text: str | None = None,
    context: str | None = None,
    suggestion: str | None = None,
) -> Finding:
    """Centralized Finding construction from a Rule (or without one for no-comp)."""
    return Finding(
        mod_id=mod.mod_id,
        mod_name=mod.name,
        rule_id=rule.id if rule else rule_id,
        severity=rule.severity if rule else severity,
        message=rule.description if rule else message,
        file_path=file_path,
        line_number=line_number,
        line_text=line_text,
        context=context if context is not None else (rule.context if rule else None),
        suggestion=suggestion,
        confidence=rule.confidence if rule else "certain",
        group=rule.group if rule else "",
    )


def _cached_read_lines(file_path: Path, cache: FileCache) -> list[str]:
    """Read file lines, using cache to avoid re-reading."""
    if file_path not in cache:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            cache[file_path] = text.splitlines()
        except (OSError, PermissionError):
            cache[file_path] = []
    return cache[file_path]


def check_mod(mod: ModInfo, ruleset: RuleSet, target_version: PZVersion) -> list[Finding]:
    """Check a single mod against all applicable rules.

    Args:
        mod: The mod to check.
        ruleset: All loaded rules.
        target_version: The PZ version to check compatibility against.

    Returns:
        List of findings (empty if no issues).
    """
    findings: list[Finding] = []

    # Check no-comp.txt entries first
    findings.extend(_check_no_comp(mod, ruleset.no_comp, target_version))

    # Build file cache for performance (shared across all rules)
    file_cache: FileCache = {}

    # Check version-applicable rules
    applicable_rules = ruleset.rules_for_version(target_version)
    for rule in applicable_rules:
        rule_findings = _apply_rule(mod, rule, file_cache)
        findings.extend(rule_findings)

    return findings


def check_all_mods(
    mods: list[ModInfo],
    ruleset: RuleSet,
    target_version: PZVersion,
) -> dict[str, list[Finding]]:
    """Check all mods, returning findings keyed by mod_id."""
    results: dict[str, list[Finding]] = {}
    for mod in mods:
        findings = check_mod(mod, ruleset, target_version)
        if findings:
            results[mod.mod_id] = findings
    return results


def _check_no_comp(
    mod: ModInfo,
    no_comp: list[NoCompEntry],
    target_version: PZVersion,
) -> list[Finding]:
    """Check if mod is in the known-incompatible list."""
    findings: list[Finding] = []

    for entry in no_comp:
        if mod.mod_id == entry.mod_id:
            max_ver = PZVersion.parse(entry.max_compatible_version)
            if target_version > max_ver:
                findings.append(_make_finding(
                    mod, None,
                    rule_id="no-comp",
                    severity="breaking",
                    message=f"Known incompatible: {entry.reason}",
                    context=f"Last compatible version: {entry.max_compatible_version}",
                ))

    return findings


def _check_condition(mod: ModInfo, rule: Rule, file_cache: FileCache) -> bool:
    """Evaluate a rule's condition. All conditions are AND'd — all must pass."""
    cond = rule.condition
    if not cond:
        return True

    checks: list[bool] = []

    # has_lua_pattern: only apply if mod's Lua files contain this regex
    if "has_lua_pattern" in cond:
        pattern_str = cond["has_lua_pattern"]
        found = False
        try:
            compiled = re.compile(pattern_str)
            for lua_file in find_lua_files(mod.lua_root):
                if found:
                    break
                for line in _cached_read_lines(lua_file, file_cache):
                    if compiled.search(line):
                        found = True
                        break
        except re.error:
            found = True  # invalid condition → apply rule anyway
        checks.append(found)

    # has_files_in_dir: only apply if directory contains files matching glob
    if "has_files_in_dir" in cond:
        dir_path = mod.path / cond["has_files_in_dir"]
        file_glob = cond.get("file_glob", "*")
        checks.append(dir_path.is_dir() and bool(list(dir_path.glob(file_glob))))

    # has_lua_files: only apply if mod has any .lua files
    if cond.get("has_lua_files") == "true":
        checks.append(bool(find_lua_files(mod.lua_root)))

    # has_content_dir: only apply if mod has files under media/lua or media/scripts at root
    if cond.get("has_content_dir") == "true":
        root_lua = mod.path / "media" / "lua"
        root_scripts = mod.path / "media" / "scripts"
        checks.append(
            (root_lua.is_dir() and bool(find_lua_files(root_lua))) or
            (root_scripts.is_dir() and bool(find_script_files(root_scripts)))
        )

    # has_b42_folder / not_has_b42_folder
    if cond.get("has_b42_folder") == "true":
        checks.append(mod.has_b42_folder)
    if cond.get("not_has_b42_folder") == "true":
        checks.append(not mod.has_b42_folder)

    # has_common_folder / not_has_common_folder
    if cond.get("not_has_common_folder") == "true":
        checks.append(not mod.has_common_folder)

    # has_version_min: only apply if mod.info declares versionMin
    if cond.get("has_version_min") == "true":
        checks.append(bool(mod.version_min))

    return all(checks) if checks else True


def _apply_rule(mod: ModInfo, rule: Rule, file_cache: FileCache) -> list[Finding]:
    """Apply a single rule to a mod."""
    if not _check_condition(mod, rule, file_cache):
        return []

    match rule.type:
        case "structure":
            return _check_structure(mod, rule)
        case "api_removal":
            return _check_pattern(mod, rule, file_cache)
        case "api_rename":
            return _check_pattern(mod, rule, file_cache)
        case "api_signature":
            return _check_pattern(mod, rule, file_cache)
        case "script_syntax":
            return _check_script_syntax(mod, rule, file_cache)
        case "mod_info":
            return _check_mod_info(mod, rule)
        case "translation":
            return _check_translation(mod, rule, file_cache)
        case "deprecated":
            return _check_pattern(mod, rule, file_cache)
        case _:
            print(f"Warning: Unknown rule type '{rule.type}' for rule '{rule.id}', skipping.", file=sys.stderr)
            return []


def _check_structure(mod: ModInfo, rule: Rule) -> list[Finding]:
    """Check structural requirements (folder/file existence)."""
    target = mod.path / rule.path

    if not target.resolve().is_relative_to(mod.path.resolve()):
        print(f"Warning: Rule '{rule.id}' path escapes mod directory, skipping.", file=sys.stderr)
        return []

    match rule.check:
        case "dir_exists":
            if not target.is_dir():
                return [_make_finding(mod, rule, context=f"Missing directory: {rule.path}")]
        case "file_exists":
            if not target.is_file():
                return [_make_finding(mod, rule, context=f"Missing file: {rule.path}")]
        case _:
            if rule.check:
                print(f"Warning: Unknown check type '{rule.check}' for rule '{rule.id}'.", file=sys.stderr)

    return []


def _check_pattern(mod: ModInfo, rule: Rule, file_cache: FileCache) -> list[Finding]:
    """Check for pattern matches in Lua files (api_removal, api_rename, deprecated)."""
    pattern = rule.old_pattern if rule.old_pattern else rule.pattern
    if not pattern:
        return []

    # Determine which files to scan
    if rule.scan == "*.lua" or not rule.scan:
        files = find_lua_files(mod.lua_root)
    elif rule.scan == "*.txt":
        scan_root = mod.path / rule.path if rule.path else mod.script_root
        if rule.path and not scan_root.resolve().is_relative_to(mod.path.resolve()):
            print(f"Warning: Rule '{rule.id}' path escapes mod directory, skipping.", file=sys.stderr)
            return []
        files = find_script_files(scan_root)
    else:
        files = find_lua_files(mod.lua_root)

    # Compile regex if needed
    compiled = None
    if rule.regex:
        try:
            compiled = re.compile(pattern)
        except re.error as e:
            print(f"Warning: Invalid regex in rule '{rule.id}': {e}", file=sys.stderr)
            return []

    hits: list[tuple[Path, int, str]] = []  # (file_path, line_num, line_text)
    for file_path in files:
        lines = _cached_read_lines(file_path, file_cache)
        for line_num, line in enumerate(lines, start=1):
            if compiled is not None:
                if compiled.search(line):
                    hits.append((file_path, line_num, line.strip()))
            else:
                if pattern in line:
                    hits.append((file_path, line_num, line.strip()))

    findings: list[Finding] = []
    for hit_path, hit_line_num, hit_line_text in hits:
        suggestion = None
        if rule.type == "api_rename" and rule.new_name:
            suggestion = f"Replace with: {rule.new_name}"
        elif rule.type == "deprecated" and rule.replacement:
            suggestion = f"Use instead: {rule.replacement}"

        findings.append(_make_finding(
            mod, rule,
            file_path=str(hit_path.relative_to(mod.path)),
            line_number=hit_line_num,
            line_text=hit_line_text,
            suggestion=suggestion,
        ))

    return findings


def _check_script_syntax(mod: ModInfo, rule: Rule, file_cache: FileCache) -> list[Finding]:
    """Check script file syntax patterns."""
    if not rule.pattern:
        return []

    scan_root = mod.path / rule.path if rule.path else mod.script_root
    if rule.path and not scan_root.resolve().is_relative_to(mod.path.resolve()):
        print(f"Warning: Rule '{rule.id}' path escapes mod directory, skipping.", file=sys.stderr)
        return []
    files = find_script_files(scan_root)

    # Compile regex if needed
    compiled = None
    if rule.regex:
        try:
            compiled = re.compile(rule.pattern)
        except re.error as e:
            print(f"Warning: Invalid regex in rule '{rule.id}': {e}", file=sys.stderr)
            return []

    hits: list[tuple[Path, int, str]] = []  # (file_path, line_num, line_text)
    for file_path in files:
        lines = _cached_read_lines(file_path, file_cache)
        for line_num, line in enumerate(lines, start=1):
            if compiled is not None:
                if compiled.search(line):
                    hits.append((file_path, line_num, line.strip()))
            else:
                if rule.pattern in line:
                    hits.append((file_path, line_num, line.strip()))

    return [
        _make_finding(
            mod, rule,
            file_path=str(hit_path.relative_to(mod.path)),
            line_number=hit_line_num,
            line_text=hit_line_text,
        )
        for hit_path, hit_line_num, hit_line_text in hits
    ]


def _check_mod_info(mod: ModInfo, rule: Rule) -> list[Finding]:
    """Check mod.info field requirements."""
    field_name = rule.field_name
    if not field_name:
        return []

    match rule.check:
        case "exists":
            if field_name not in mod.raw:
                return [_make_finding(mod, rule, context=f"mod.info missing field: {field_name}")]
        case "not_empty":
            value = mod.raw.get(field_name, "")
            if not value:
                return [_make_finding(mod, rule, context=f"mod.info field '{field_name}' is empty")]
        case _:
            if rule.check:
                print(f"Warning: Unknown check type '{rule.check}' for rule '{rule.id}'.", file=sys.stderr)

    return []


def _check_translation(mod: ModInfo, rule: Rule, file_cache: FileCache) -> list[Finding]:
    """Check translation file requirements."""
    files = find_translation_files(mod.translate_root)
    if not files:
        return []

    findings: list[Finding] = []

    match rule.check:
        case "encoding_utf8":
            for f in files:
                encoding = check_file_encoding(f)
                if encoding != "utf-8":
                    findings.append(_make_finding(
                        mod, rule,
                        file_path=str(f.relative_to(mod.path)),
                        context=f"File encoding: {encoding} (expected UTF-8)",
                    ))
        case _:
            if rule.check:
                print(f"Warning: Unknown check type '{rule.check}' for rule '{rule.id}'.", file=sys.stderr)

    return findings
