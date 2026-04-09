"""Tests for rule loading and engine."""

import tempfile
from pathlib import Path

from pz_mod_checker.rules.loader import Rule, RuleSet, NoCompEntry, load_rules_from_dir, load_no_comp
from pz_mod_checker.rules.version import PZVersion
from pz_mod_checker.rules.engine import check_mod, Finding
from pz_mod_checker.scanner.mod_info import ModInfo


def _create_rule_file(tmp: Path, filename: str, content: str) -> Path:
    rules_dir = tmp / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule_file = rules_dir / filename
    rule_file.write_text(content, encoding="utf-8")
    return rules_dir


def test_load_rules():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rules_dir = _create_rule_file(tmp_path, "42.0.0.json", """{
  "version": "42.0.0",
  "summary": "Test rules",
  "changes": [
    {
      "id": "test-structure",
      "type": "structure",
      "severity": "warning",
      "since": "42.0.0",
      "description": "Test structure rule",
      "check": "dir_exists",
      "path": "common/"
    },
    {
      "id": "test-api",
      "type": "api_removal",
      "severity": "breaking",
      "since": "42.0.0",
      "description": "Test API removal",
      "pattern": "OldFunction",
      "scan": "*.lua"
    }
  ]
}""")

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


def _make_mod_with_lua(tmp_path: Path, mod_id: str = "TestMod",
                       lua_content: str = "", version_min: str = "",
                       has_42: bool = False, has_common: bool = False) -> ModInfo:
    """Helper: create a mod directory with optional Lua content and structure."""
    mod_dir = tmp_path / mod_id
    mod_dir.mkdir(exist_ok=True)
    lua_dir = mod_dir / "media" / "lua" / "client"
    lua_dir.mkdir(parents=True, exist_ok=True)
    if lua_content:
        (lua_dir / "main.lua").write_text(lua_content, encoding="utf-8")
    if has_42:
        (mod_dir / "42").mkdir(exist_ok=True)
    if has_common:
        (mod_dir / "common").mkdir(exist_ok=True)
    raw = {"name": mod_id, "id": mod_id}
    if version_min:
        raw["versionMin"] = version_min
    return ModInfo(mod_id=mod_id, name=mod_id, path=mod_dir,
                   version_min=version_min, raw=raw)


# --- Condition tests ---

def test_condition_has_lua_pattern_match():
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="TraitFactory.addTrait()")
        rule = Rule(id="test", type="structure", severity="warning", since="42.0.0",
                    description="Test", check="dir_exists", path="missing/",
                    condition={"has_lua_pattern": "TraitFactory"})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 1  # condition met, dir missing → finding


def test_condition_has_lua_pattern_no_match():
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="-- no traits here")
        rule = Rule(id="test", type="structure", severity="warning", since="42.0.0",
                    description="Test", check="dir_exists", path="missing/",
                    condition={"has_lua_pattern": "TraitFactory"})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 0  # condition not met → rule skipped


def test_condition_has_lua_pattern_invalid_regex():
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="some code")
        rule = Rule(id="test", type="structure", severity="warning", since="42.0.0",
                    description="Test", check="dir_exists", path="missing/",
                    condition={"has_lua_pattern": "[invalid regex"})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 1  # invalid regex → apply rule anyway


def test_condition_has_files_in_dir_exists():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod = _make_mod_with_lua(tmp_path)
        tr_dir = mod.path / "media" / "lua" / "shared" / "Translate"
        tr_dir.mkdir(parents=True)
        (tr_dir / "EN.txt").write_text("test", encoding="utf-8")
        rule = Rule(id="test", type="structure", severity="info", since="42.0.0",
                    description="Test", check="dir_exists", path="missing/",
                    condition={"has_files_in_dir": "media/lua/shared/Translate", "file_glob": "*.txt"})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 1  # condition met


def test_condition_has_files_in_dir_missing():
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp))
        rule = Rule(id="test", type="structure", severity="info", since="42.0.0",
                    description="Test", check="dir_exists", path="missing/",
                    condition={"has_files_in_dir": "media/lua/shared/Translate", "file_glob": "*.txt"})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 0  # no translate dir → skip


def test_condition_has_lua_files_true():
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="code")
        rule = Rule(id="test", type="mod_info", severity="info", since="42.0.0",
                    description="Test", check="exists", field_name="versionMin",
                    condition={"has_lua_files": "true"})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 1  # has lua files, missing versionMin


def test_condition_has_lua_files_false():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "EmptyMod"
        mod_dir.mkdir()
        mod = ModInfo(mod_id="EmptyMod", name="Empty", path=mod_dir, raw={"name": "Empty", "id": "EmptyMod"})
        rule = Rule(id="test", type="mod_info", severity="info", since="42.0.0",
                    description="Test", check="exists", field_name="versionMin",
                    condition={"has_lua_files": "true"})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 0  # no lua files → skip


def test_condition_has_b42_folder():
    with tempfile.TemporaryDirectory() as tmp:
        mod_yes = _make_mod_with_lua(Path(tmp), mod_id="ModWith42", has_42=True)
        mod_no = _make_mod_with_lua(Path(tmp), mod_id="ModNo42", has_42=False)
        rule = Rule(id="test", type="mod_info", severity="info", since="42.0.0",
                    description="Test", check="exists", field_name="versionMin",
                    condition={"has_b42_folder": "true"})
        rs = RuleSet(rules=[rule])
        v = PZVersion.parse("42.0.0")
        assert len(check_mod(mod_yes, rs, v)) == 1  # has 42/ + no versionMin
        assert len(check_mod(mod_no, rs, v)) == 0   # no 42/ → skip


def test_condition_not_has_b42_folder():
    with tempfile.TemporaryDirectory() as tmp:
        mod_yes = _make_mod_with_lua(Path(tmp), mod_id="ModWith42", has_42=True)
        mod_no = _make_mod_with_lua(Path(tmp), mod_id="ModNo42", has_42=False, lua_content="code")
        rule = Rule(id="test", type="structure", severity="info", since="42.0.0",
                    description="Test", check="dir_exists", path="common/",
                    condition={"has_lua_files": "true", "not_has_b42_folder": "true"})
        rs = RuleSet(rules=[rule])
        v = PZVersion.parse("42.0.0")
        assert len(check_mod(mod_no, rs, v)) == 1   # no 42/ + has lua → flagged
        assert len(check_mod(mod_yes, rs, v)) == 0   # has 42/ → skip


def test_condition_not_has_common_folder():
    with tempfile.TemporaryDirectory() as tmp:
        mod_common = _make_mod_with_lua(Path(tmp), mod_id="ModCommon", has_common=True, version_min="42.0.0")
        mod_bare = _make_mod_with_lua(Path(tmp), mod_id="ModBare", version_min="42.0.0")
        rule = Rule(id="test", type="structure", severity="info", since="42.0.0",
                    description="Test", check="dir_exists", path="42/",
                    condition={"has_version_min": "true", "not_has_common_folder": "true"})
        rs = RuleSet(rules=[rule])
        v = PZVersion.parse("42.0.0")
        assert len(check_mod(mod_bare, rs, v)) == 1    # no common/ → flagged
        assert len(check_mod(mod_common, rs, v)) == 0   # has common/ → skip


def test_condition_has_version_min():
    with tempfile.TemporaryDirectory() as tmp:
        mod_with = _make_mod_with_lua(Path(tmp), mod_id="ModVer", version_min="42.0.0")
        mod_without = _make_mod_with_lua(Path(tmp), mod_id="ModNoVer")
        rule = Rule(id="test", type="structure", severity="info", since="42.0.0",
                    description="Test", check="dir_exists", path="42/",
                    condition={"has_version_min": "true"})
        rs = RuleSet(rules=[rule])
        v = PZVersion.parse("42.0.0")
        assert len(check_mod(mod_with, rs, v)) == 1   # has versionMin, no 42/ → flagged
        assert len(check_mod(mod_without, rs, v)) == 0  # no versionMin → skip


def test_condition_has_content_dir():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Mod with root media/lua content
        mod = _make_mod_with_lua(tmp_path, mod_id="CodeMod", lua_content="code")
        rule = Rule(id="test", type="structure", severity="info", since="42.0.0",
                    description="Test", check="dir_exists", path="42/",
                    condition={"has_content_dir": "true"})
        rs = RuleSet(rules=[rule])
        v = PZVersion.parse("42.0.0")
        assert len(check_mod(mod, rs, v)) == 1  # has media/lua at root

        # Empty mod
        empty_dir = tmp_path / "EmptyMod"
        empty_dir.mkdir()
        empty_mod = ModInfo(mod_id="EmptyMod", name="Empty", path=empty_dir, raw={})
        assert len(check_mod(empty_mod, rs, v)) == 0  # no content dir


def test_condition_and_composition():
    """Multiple conditions must ALL be true (AND logic)."""
    with tempfile.TemporaryDirectory() as tmp:
        # Mod with lua files + TraitFactory but HAS 42/ folder
        mod = _make_mod_with_lua(Path(tmp), lua_content="TraitFactory.addTrait()", has_42=True)
        rule = Rule(id="test", type="structure", severity="warning", since="42.0.0",
                    description="Test", check="file_exists", path="42/media/registries.lua",
                    condition={"has_lua_pattern": "TraitFactory", "not_has_b42_folder": "true"})
        rs = RuleSet(rules=[rule])
        v = PZVersion.parse("42.0.0")
        # has_lua_pattern passes but not_has_b42_folder fails → skip
        assert len(check_mod(mod, rs, v)) == 0


def test_condition_empty_dict():
    """Empty condition dict should apply the rule (no filtering)."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp))
        rule = Rule(id="test", type="structure", severity="warning", since="42.0.0",
                    description="Test", check="dir_exists", path="missing/",
                    condition={})
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.0.0"))
        assert len(findings) == 1  # empty condition → apply


# --- 42.16.0 rule tests ---

def test_b42_16_fire_officer_rename():
    """Mods referencing 'Fire Officer' or 'FireOfficer' should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content='if player:getProfession() == "FireOfficer" then')
        rule = Rule(
            id="b42-16-occupation-fire-officer",
            type="api_rename",
            severity="warning",
            since="42.16.0",
            description="Occupation 'Fire Officer' renamed to 'Firefighter'",
            old_pattern="Fire Officer|FireOfficer",
            regex=True,
            new_name="Firefighter",
            scan="*.lua",
        )
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.0"))
        assert len(findings) == 1
        assert findings[0].rule_id == "b42-16-occupation-fire-officer"


def test_b42_16_fire_officer_rename_display_name():
    """Display name string 'Fire Officer' should also be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content='local name = "Fire Officer"')
        rule = Rule(
            id="b42-16-occupation-fire-officer",
            type="api_rename",
            severity="warning",
            since="42.16.0",
            description="Occupation 'Fire Officer' renamed to 'Firefighter'",
            old_pattern="Fire Officer|FireOfficer",
            regex=True,
            new_name="Firefighter",
            scan="*.lua",
        )
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.0"))
        assert len(findings) == 1


def test_b42_16_angler_rename():
    """Mods referencing the 'Angler' occupation by quoted name should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content='if getProfession() == "Angler" then')
        rule = Rule(
            id="b42-16-occupation-angler",
            type="api_rename",
            severity="warning",
            since="42.16.0",
            description="Occupation 'Angler' renamed to 'Fishing Guide'",
            old_pattern='"Angler"',
            new_name="FishingGuide",
            scan="*.lua",
        )
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.0"))
        assert len(findings) == 1
        assert findings[0].rule_id == "b42-16-occupation-angler"


def test_b42_16_angler_rename_no_false_positive():
    """Unquoted 'Angler' (e.g. fishing variable name) should not trigger."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="local anglerSkill = player:getLevel()")
        rule = Rule(
            id="b42-16-occupation-angler",
            type="api_rename",
            severity="warning",
            since="42.16.0",
            description="Occupation 'Angler' renamed to 'Fishing Guide'",
            old_pattern='"Angler"',
            new_name="FishingGuide",
            scan="*.lua",
        )
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.0"))
        assert len(findings) == 0


def test_b42_16_trait_wilderness_knowledge():
    """Mods referencing WildernessKnowledge trait ID should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content='player:getTraits():contains("WildernessKnowledge")')
        rule = Rule(
            id="b42-16-trait-wilderness-knowledge",
            type="api_rename",
            severity="warning",
            since="42.16.0",
            description="Trait 'Wilderness Knowledge' renamed to 'Bushcrafter'",
            old_pattern="WildernessKnowledge|Wilderness Knowledge",
            regex=True,
            new_name="Bushcrafter",
            scan="*.lua",
        )
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.0"))
        assert len(findings) == 1
        assert findings[0].rule_id == "b42-16-trait-wilderness-knowledge"


def test_b42_16_sandbox_firearms_damage_type():
    """Mods reading FirearmsUseDamageChance sandbox option should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="if SandboxVars.FirearmsUseDamageChance == true then")
        rule = Rule(
            id="b42-16-sandbox-firearms-damage-type",
            type="api_signature",
            severity="warning",
            since="42.16.0",
            description="FirearmsUseDamageChance changed from boolean to integer",
            pattern="FirearmsUseDamageChance",
            scan="*.lua",
        )
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.0"))
        assert len(findings) == 1


def test_b42_16_proclists_warning():
    """Mods using procLists in distribution tables should be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="table.procLists = { {item='Axe'}, {item='Knife'} }")
        rule = Rule(
            id="b42-16-distribution-proclists-weightchance",
            type="deprecated",
            severity="warning",
            since="42.16.0",
            description="procLists entries without weightChance now spawn nothing",
            pattern="procLists",
            scan="*.lua",
            replacement="Add explicit weightChance",
        )
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.0"))
        assert len(findings) == 1


def test_b42_16_lua_filesystem_security():
    """Mods using io.open or os.execute should be flagged on 42.16.3+."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _make_mod_with_lua(Path(tmp), lua_content="local f = io.open('data.txt', 'r')")
        rule = Rule(
            id="b42-16-lua-filesystem-security",
            type="deprecated",
            severity="warning",
            since="42.16.3",
            description="Lua filesystem access restricted by security patch",
            pattern=r"\bio\.open\b|\bos\.execute\b|\bos\.remove\b|\bos\.rename\b",
            regex=True,
            scan="*.lua",
            replacement="Use PZ built-in file APIs",
        )
        # Should trigger on 42.16.3
        findings = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.3"))
        assert len(findings) == 1
        # Should NOT trigger on 42.16.2 (rule not yet active)
        findings_before = check_mod(mod, RuleSet(rules=[rule]), PZVersion.parse("42.16.2"))
        assert len(findings_before) == 0


if __name__ == "__main__":
    test_load_rules()
    test_load_no_comp()
    test_rules_for_version()
    test_check_mod_structure()
    test_check_no_comp()
    test_check_api_removal()
    print("All rule tests passed.")
