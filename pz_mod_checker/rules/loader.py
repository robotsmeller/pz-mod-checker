"""Load rule definitions from JSON files and no-comp.txt."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .version import PZVersion


@dataclass
class Rule:
    """A single compatibility rule."""

    id: str
    type: str  # structure, api_removal, api_rename, api_signature, script_syntax, mod_info, translation, deprecated
    severity: str  # breaking, warning, info
    since: str
    description: str
    # Type-specific fields
    pattern: str = ""
    regex: bool = False
    scan: str = ""  # file glob: *.lua, *.txt
    path: str = ""  # subdirectory to check within mod
    check: str = ""  # dir_exists, file_exists, encoding_utf8, exists
    old_pattern: str = ""
    new_name: str = ""
    field_name: str = ""  # for mod_info rules
    replacement: str = ""
    context: str = ""

    _since_version: PZVersion | None = field(default=None, init=False, repr=False)

    @property
    def since_version(self) -> PZVersion:
        if self._since_version is None:
            self._since_version = PZVersion.parse(self.since)
        return self._since_version


@dataclass
class NoCompEntry:
    """A known-incompatible mod from no-comp.txt."""

    mod_id: str
    max_compatible_version: str
    reason: str


@dataclass
class RuleSet:
    """All loaded rules and known incompatibles."""

    rules: list[Rule] = field(default_factory=list)
    no_comp: list[NoCompEntry] = field(default_factory=list)

    def rules_for_version(self, target: PZVersion) -> list[Rule]:
        """Return rules applicable at or before the target version."""
        return [r for r in self.rules if r.since_version <= target]


def load_rules_from_dir(rules_dir: Path) -> list[Rule]:
    """Load all rule JSON files from a directory."""
    rules: list[Rule] = []

    if not rules_dir.is_dir():
        return rules

    for json_file in sorted(rules_dir.glob("*.json")):
        file_rules = _parse_json_rules(json_file)
        rules.extend(file_rules)

    return rules


def load_no_comp(no_comp_path: Path) -> list[NoCompEntry]:
    """Load known-incompatible mod entries from no-comp.txt."""
    entries: list[NoCompEntry] = []

    if not no_comp_path.is_file():
        return entries

    text = no_comp_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            entries.append(NoCompEntry(
                mod_id=parts[0].strip(),
                max_compatible_version=parts[1].strip(),
                reason="|".join(parts[2:]).strip(),
            ))

    return entries


def load_ruleset(data_dir: Path) -> RuleSet:
    """Load the complete ruleset from the data directory."""
    rules = load_rules_from_dir(data_dir / "rules")
    no_comp = load_no_comp(data_dir / "no-comp.txt")
    return RuleSet(rules=rules, no_comp=no_comp)


_VALID_RULE_KEYS = {
    "id", "type", "severity", "since", "description", "pattern", "regex",
    "scan", "path", "check", "old_pattern", "new_name", "field",
    "replacement", "context",
}


# --- JSON rule parser ---

def _parse_json_rules(json_path: Path) -> list[Rule]:
    """Parse a rule JSON file."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to load {json_path}: {e}", file=sys.stderr)
        return []

    rules: list[Rule] = []
    for block in data.get("changes", []):
        rule = _parse_rule_block(block)
        if rule:
            rules.append(rule)
    return rules


def _parse_rule_block(block: dict[str, Any]) -> Rule | None:
    """Convert a parsed block dict into a Rule."""
    rule_id = block.get("id", "")
    if not rule_id:
        return None

    since = block.get("since", "")
    if not since:
        print(f"Warning: Rule '{rule_id}' has no 'since' field, skipping.", file=sys.stderr)
        return None

    unknown = set(block.keys()) - _VALID_RULE_KEYS
    if unknown:
        print(f"Warning: Rule '{rule_id}' has unknown fields: {unknown}", file=sys.stderr)

    # Handle regex as bool (JSON native) or string (legacy)
    regex_val = block.get("regex", False)
    if isinstance(regex_val, str):
        regex_val = regex_val.lower() in ("true", "yes", "1")

    return Rule(
        id=rule_id,
        type=block.get("type", ""),
        severity=block.get("severity", "warning"),
        since=str(block.get("since", "")),
        description=block.get("description", ""),
        pattern=block.get("pattern", ""),
        regex=bool(regex_val),
        scan=block.get("scan", ""),
        path=block.get("path", ""),
        check=block.get("check", ""),
        old_pattern=block.get("old_pattern", ""),
        new_name=block.get("new_name", ""),
        field_name=block.get("field", ""),
        replacement=block.get("replacement", ""),
        context=block.get("context", ""),
    )
