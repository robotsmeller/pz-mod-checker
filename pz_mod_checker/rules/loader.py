"""Load rule definitions from YAML files and no-comp.txt."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from .version import PZVersion

# Use stdlib configparser-style YAML parsing to avoid PyYAML dependency.
# Our YAML is simple enough to parse manually.


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
    """Load all rule YAML files from a directory."""
    rules: list[Rule] = []

    if not rules_dir.is_dir():
        return rules

    for yaml_file in sorted(rules_dir.glob("*.yaml")):
        file_rules = _parse_yaml_rules(yaml_file)
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


# --- Simple YAML parser (avoids PyYAML dependency) ---

def _parse_yaml_rules(yaml_path: Path) -> list[Rule]:
    """Parse a rule YAML file using a simple line-by-line parser.

    Handles our specific YAML schema only — not a general YAML parser.
    """
    text = yaml_path.read_text(encoding="utf-8", errors="replace")
    rules: list[Rule] = []

    # Split into change blocks
    # Look for "- id:" as block delimiters
    blocks = _split_change_blocks(text)

    for block in blocks:
        rule = _parse_rule_block(block)
        if rule:
            rules.append(rule)

    return rules


def _split_change_blocks(text: str) -> list[dict[str, str]]:
    """Split YAML text into individual change blocks."""
    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}
    in_changes = False

    for line in text.splitlines():
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            continue

        # Detect changes section
        if stripped == "changes:":
            in_changes = True
            continue

        # Top-level fields (before changes:)
        if not in_changes and ":" in stripped:
            continue

        if not in_changes:
            continue

        # New change block starts with "- id:"
        if stripped.startswith("- id:"):
            if current:
                blocks.append(current)
            current = {"id": stripped.split(":", 1)[1].strip()}
            continue

        # Continuation of current block
        if current and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            if key.startswith("- "):
                key = key[2:].strip()
            value = value.strip().strip('"').strip("'")
            current[key] = value

    if current:
        blocks.append(current)

    return blocks


def _parse_rule_block(block: dict[str, str]) -> Rule | None:
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

    return Rule(
        id=rule_id,
        type=block.get("type", ""),
        severity=block.get("severity", "warning"),
        since=block.get("since", ""),
        description=block.get("description", ""),
        pattern=block.get("pattern", ""),
        regex=block.get("regex", "").lower() in ("true", "yes", "1"),
        scan=block.get("scan", ""),
        path=block.get("path", ""),
        check=block.get("check", ""),
        old_pattern=block.get("old_pattern", ""),
        new_name=block.get("new_name", ""),
        field_name=block.get("field", ""),
        replacement=block.get("replacement", ""),
        context=block.get("context", ""),
    )
