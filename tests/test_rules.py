"""Tests for rule loading and engine."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rules.loader import Rule, RuleSet, NoCompEntry, load_rules_from_dir, load_no_comp
from src.rules.version import PZVersion
from src.rules.engine import check_mod, Finding
from src.scanner.mod_info import ModInfo


def _create_rule_file(tmp: Path, filename: str, content: str) -> Path:
    rules_dir = tmp / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule_file = rules_dir / filename
    rule_file.write_text(content, encoding="utf-8")
    return rules_dir


def test_load_rules():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rules_dir = _create_rule_file(tmp_path, "42.0.0.yaml", """
version: "42.0.0"
summary: "Test rules"

changes:

  - id: test-structure
    type: structure
    severity: warning
    since: "42.0.0"
    description: "Test structure rule"
    check: dir_exists
    path: "common/"

  - id: test-api
    type: api_removal
    severity: breaking
    since: "42.0.0"
    description: "Test API removal"
    pattern: "OldFunction"
    scan: "*.lua"
""")

        rules = load_rules_from_dir(rules_dir)
        assert len(rules) == 2
        assert rules[0].id == "test-structure"
        assert rules[0].type == "structure"
        assert rules[1].id == "test-api"
        assert rules[1].severity == "breaking"


def test_load_no_comp():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        no_comp_file = tmp_path / "no-comp.txt"
        no_comp_file.write_text("""
# Comment line
BadMod|41.78.16|Totally broken in B42
AnotherBad|41.50.0|Uses removed internals
""", encoding="utf-8")

        entries = load_no_comp(no_comp_file)
        assert len(entries) == 2
        assert entries[0].mod_id == "BadMod"
        assert entries[0].max_compatible_version == "41.78.16"
        assert entries[0].reason == "Totally broken in B42"


def test_rules_for_version():
    r1 = Rule(id="r1", type="structure", severity="warning", since="42.0.0", description="r1")
    r2 = Rule(id="r2", type="api_removal", severity="breaking", since="42.3.0", description="r2")
    r3 = Rule(id="r3", type="deprecated", severity="info", since="42.5.0", description="r3")

    ruleset = RuleSet(rules=[r1, r2, r3])

    target_420 = PZVersion.parse("42.0.0")
    assert len(ruleset.rules_for_version(target_420)) == 1

    target_430 = PZVersion.parse("42.3.0")
    assert len(ruleset.rules_for_version(target_430)) == 2

    target_460 = PZVersion.parse("42.6.0")
    assert len(ruleset.rules_for_version(target_460)) == 3


def test_check_mod_structure():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "TestMod"
        mod_dir.mkdir()
        (mod_dir / "mod.info").write_text("name=Test\nid=TestMod", encoding="utf-8")
        (mod_dir / "media" / "lua").mkdir(parents=True)

        mod = ModInfo(
            mod_id="TestMod",
            name="Test Mod",
            path=mod_dir,
            raw={"name": "Test", "id": "TestMod"},
        )

        rule = Rule(
            id="test-common",
            type="structure",
            severity="warning",
            since="42.0.0",
            description="Missing common/ folder",
            check="dir_exists",
            path="common/",
        )

        ruleset = RuleSet(rules=[rule])
        target = PZVersion.parse("42.0.0")

        findings = check_mod(mod, ruleset, target)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].rule_id == "test-common"

        # Now create the folder and re-check
        (mod_dir / "common").mkdir()
        findings2 = check_mod(mod, ruleset, target)
        assert len(findings2) == 0


def test_check_no_comp():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "BadMod"
        mod_dir.mkdir()
        (mod_dir / "media" / "lua").mkdir(parents=True)

        mod = ModInfo(mod_id="BadMod", name="Bad Mod", path=mod_dir, raw={})

        no_comp = [NoCompEntry(mod_id="BadMod", max_compatible_version="41.78.16", reason="B41 only")]
        ruleset = RuleSet(no_comp=no_comp)

        target = PZVersion.parse("42.0.0")
        findings = check_mod(mod, ruleset, target)
        assert len(findings) == 1
        assert findings[0].severity == "breaking"
        assert "Known incompatible" in findings[0].message


def test_check_api_removal():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "TestMod"
        mod_dir.mkdir()
        lua_dir = mod_dir / "media" / "lua" / "client"
        lua_dir.mkdir(parents=True)
        (lua_dir / "main.lua").write_text(
            "function test()\n  ISInventoryPage:refresh()\nend\n",
            encoding="utf-8",
        )

        mod = ModInfo(mod_id="TestMod", name="Test", path=mod_dir, raw={})

        rule = Rule(
            id="b42-isinventorypage",
            type="api_removal",
            severity="breaking",
            since="42.0.0",
            description="ISInventoryPage removed",
            pattern="ISInventoryPage",
            scan="*.lua",
        )

        ruleset = RuleSet(rules=[rule])
        target = PZVersion.parse("42.0.0")

        findings = check_mod(mod, ruleset, target)
        assert len(findings) == 1
        assert findings[0].file_path is not None
        assert findings[0].line_number == 2


if __name__ == "__main__":
    test_load_rules()
    test_load_no_comp()
    test_rules_for_version()
    test_check_mod_structure()
    test_check_no_comp()
    test_check_api_removal()
    print("All rule tests passed.")
