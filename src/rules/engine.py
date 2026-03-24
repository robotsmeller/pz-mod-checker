"""Rule engine — applies rules to scanned mods and produces findings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..scanner.lua_reader import (
    SearchHit,
    check_file_encoding,
    find_lua_files,
    find_script_files,
    find_translation_files,
    search_files,
)
from ..scanner.mod_info import ModInfo
from .loader import NoCompEntry, Rule, RuleSet
from .version import PZVersion


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

    # Check version-applicable rules
    applicable_rules = ruleset.rules_for_version(target_version)
    for rule in applicable_rules:
        rule_findings = _apply_rule(mod, rule)
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
                findings.append(Finding(
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    rule_id="no-comp",
                    severity="breaking",
                    message=f"Known incompatible: {entry.reason}",
                    context=f"Last compatible version: {entry.max_compatible_version}",
                ))

    return findings


def _apply_rule(mod: ModInfo, rule: Rule) -> list[Finding]:
    """Apply a single rule to a mod."""
    match rule.type:
        case "structure":
            return _check_structure(mod, rule)
        case "api_removal":
            return _check_pattern(mod, rule)
        case "api_rename":
            return _check_pattern(mod, rule)
        case "api_signature":
            return _check_pattern(mod, rule)
        case "script_syntax":
            return _check_script_syntax(mod, rule)
        case "mod_info":
            return _check_mod_info(mod, rule)
        case "translation":
            return _check_translation(mod, rule)
        case "deprecated":
            return _check_pattern(mod, rule)
        case _:
            return []


def _check_structure(mod: ModInfo, rule: Rule) -> list[Finding]:
    """Check structural requirements (folder/file existence)."""
    target = mod.path / rule.path

    match rule.check:
        case "dir_exists":
            if not target.is_dir():
                return [Finding(
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=rule.description,
                    context=f"Missing directory: {rule.path}",
                )]
        case "file_exists":
            if not target.is_file():
                return [Finding(
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=rule.description,
                    context=f"Missing file: {rule.path}",
                )]

    return []


def _check_pattern(mod: ModInfo, rule: Rule) -> list[Finding]:
    """Check for pattern matches in Lua files (api_removal, api_rename, deprecated)."""
    pattern = rule.old_pattern if rule.old_pattern else rule.pattern
    if not pattern:
        return []

    # Determine which files to scan
    if rule.scan == "*.lua" or not rule.scan:
        files = find_lua_files(mod.lua_root)
    elif rule.scan == "*.txt":
        scan_root = mod.path / rule.path if rule.path else mod.script_root
        files = find_script_files(scan_root)
    else:
        files = find_lua_files(mod.lua_root)

    hits = search_files(files, pattern, is_regex=rule.regex)

    findings: list[Finding] = []
    for hit in hits:
        suggestion = None
        if rule.type == "api_rename" and rule.new_name:
            suggestion = f"Replace with: {rule.new_name}"
        elif rule.type == "deprecated" and rule.replacement:
            suggestion = f"Use instead: {rule.replacement}"

        findings.append(Finding(
            mod_id=mod.mod_id,
            mod_name=mod.name,
            rule_id=rule.id,
            severity=rule.severity,
            message=rule.description,
            file_path=str(hit.file_path),
            line_number=hit.line_number,
            line_text=hit.line_text,
            context=rule.context,
            suggestion=suggestion,
        ))

    return findings


def _check_script_syntax(mod: ModInfo, rule: Rule) -> list[Finding]:
    """Check script file syntax patterns."""
    if not rule.pattern:
        return []

    scan_root = mod.path / rule.path if rule.path else mod.script_root
    files = find_script_files(scan_root)
    hits = search_files(files, rule.pattern, is_regex=rule.regex)

    return [
        Finding(
            mod_id=mod.mod_id,
            mod_name=mod.name,
            rule_id=rule.id,
            severity=rule.severity,
            message=rule.description,
            file_path=str(hit.file_path),
            line_number=hit.line_number,
            line_text=hit.line_text,
            context=rule.context,
        )
        for hit in hits
    ]


def _check_mod_info(mod: ModInfo, rule: Rule) -> list[Finding]:
    """Check mod.info field requirements."""
    field_name = rule.field_name
    if not field_name:
        return []

    match rule.check:
        case "exists":
            if field_name not in mod.raw:
                return [Finding(
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=rule.description,
                    context=f"mod.info missing field: {field_name}",
                )]
        case "not_empty":
            value = mod.raw.get(field_name, "")
            if not value:
                return [Finding(
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=rule.description,
                    context=f"mod.info field '{field_name}' is empty",
                )]

    return []


def _check_translation(mod: ModInfo, rule: Rule) -> list[Finding]:
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
                    findings.append(Finding(
                        mod_id=mod.mod_id,
                        mod_name=mod.name,
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=rule.description,
                        file_path=str(f),
                        context=f"File encoding: {encoding} (expected UTF-8)",
                    ))

    return findings
