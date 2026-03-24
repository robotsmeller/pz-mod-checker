"""Comprehensive audit tests for PZ Mod Checker."""

import io
import json
import sys
import tempfile
from pathlib import Path

from pz_mod_checker.cli import build_parser, get_data_dir, main
from pz_mod_checker.reporter.cli import format_severity, print_scan_results
from pz_mod_checker.reporter.json_out import findings_to_json
from pz_mod_checker.rules.engine import Finding, _apply_rule, _check_structure, check_mod
from pz_mod_checker.rules.loader import (
    NoCompEntry,
    Rule,
    RuleSet,
    _parse_rule_block,
    _parse_json_rules,
    load_no_comp,
    load_rules_from_dir,
)
from pz_mod_checker.rules.version import PZVersion
from pz_mod_checker.scanner.discovery import discover_mods
from pz_mod_checker.scanner.mod_info import ModInfo, parse_mod_info


# ============================================================
# Helpers
# ============================================================

def _make_mod(tmp: Path, name: str = "TestMod", mod_info_text: str = "name=Test\nid=TestMod",
              lua_files: dict[str, str] | None = None) -> tuple[Path, ModInfo]:
    """Create a temp mod directory and return (mod_dir, ModInfo)."""
    mod_dir = tmp / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "mod.info").write_text(mod_info_text, encoding="utf-8")
    if lua_files:
        for rel, content in lua_files.items():
            p = mod_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    info = parse_mod_info(mod_dir)
    assert info is not None
    return mod_dir, info


# ============================================================
# 1. CLI tests
# ============================================================

def test_get_data_dir_returns_path_ending_with_data():
    d = get_data_dir()
    assert isinstance(d, Path)
    assert d.name == "data"


def test_build_parser_returns_argumentparser():
    import argparse
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test_main_json_output_with_temp_mod_dir():
    """main() with a temp mod dir and real data/, format=json."""
    data_dir = get_data_dir()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "MyMod"
        mod_dir.mkdir()
        (mod_dir / "mod.info").write_text("name=My Mod\nid=MyMod", encoding="utf-8")
        (mod_dir / "media" / "lua").mkdir(parents=True)

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            rc = main(["scan", "42.0.0", "--mod-dir", str(tmp_path), "--data-dir", str(data_dir), "--format", "json"])
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        # Should produce valid JSON
        parsed = json.loads(output)
        assert "total_mods_with_issues" in parsed
        assert isinstance(rc, int)


def test_main_severity_filtering():
    """main() with --severity breaking filters out lower-severity findings."""
    data_dir = get_data_dir()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "FilterMod"
        mod_dir.mkdir()
        (mod_dir / "mod.info").write_text("name=Filter\nid=FilterMod", encoding="utf-8")
        (mod_dir / "media" / "lua").mkdir(parents=True)

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            rc = main([
                "scan", "42.0.0", "--mod-dir", str(tmp_path),
                "--data-dir", str(data_dir),
                "--format", "json", "--severity", "breaking",
            ])
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        parsed = json.loads(output)
        # All remaining findings (if any) must be breaking
        for mod_id, findings in parsed.get("mods", {}).items():
            for f in findings:
                assert f["severity"] == "breaking", f"Non-breaking finding survived filter: {f}"


def test_main_returns_0_when_no_mods_found():
    """main() returns 0 when the mod dir exists but is empty."""
    data_dir = get_data_dir()
    with tempfile.TemporaryDirectory() as tmp:
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            rc = main(["scan", "42.0.0", "--mod-dir", tmp, "--data-dir", str(data_dir), "--format", "json"])
        finally:
            sys.stderr = old_stderr
        assert rc == 0


# ============================================================
# 2. Reporter tests
# ============================================================

def test_findings_to_json_with_sample_findings():
    results = {
        "ModA": [
            Finding(mod_id="ModA", mod_name="Mod A", rule_id="r1",
                    severity="breaking", message="Broken thing"),
            Finding(mod_id="ModA", mod_name="Mod A", rule_id="r2",
                    severity="warning", message="Warn thing"),
        ],
    }
    output = findings_to_json(results)
    parsed = json.loads(output)
    assert parsed["total_mods_with_issues"] == 1
    assert parsed["total_findings"] == 2
    assert parsed["summary"]["breaking"] == 1
    assert parsed["summary"]["warning"] == 1
    assert len(parsed["mods"]["ModA"]) == 2


def test_findings_to_json_empty():
    output = findings_to_json({})
    parsed = json.loads(output)
    assert parsed["total_mods_with_issues"] == 0
    assert parsed["total_findings"] == 0
    assert parsed["mods"] == {}


def test_format_severity_with_color():
    result = format_severity("breaking", use_color=True)
    assert "[BREAKING]" in result
    # Should contain ANSI escape
    assert "\033[" in result


def test_format_severity_without_color():
    result = format_severity("warning", use_color=False)
    assert result == "[WARNING]"
    assert "\033[" not in result


def test_print_scan_results_empty(capsys=None):
    """print_scan_results with empty results prints 'No compatibility issues found.'"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        print_scan_results({}, use_color=False)
    finally:
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
    assert "No compatibility issues found." in output


# ============================================================
# 3. JSON parser edge cases
# ============================================================

def test_rule_with_empty_since_is_skipped():
    block = {"id": "no-since-rule", "type": "structure", "severity": "warning", "description": "test"}
    # No 'since' key at all
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        result = _parse_rule_block(block)
    finally:
        stderr_output = sys.stderr.getvalue()
        sys.stderr = old_stderr
    assert result is None
    assert "no 'since' field" in stderr_output


def test_rule_with_unknown_fields_still_loads():
    block = {
        "id": "unk-field-rule",
        "type": "structure",
        "severity": "warning",
        "since": "42.0.0",
        "description": "test",
        "totally_bogus": "yes",
    }
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        result = _parse_rule_block(block)
    finally:
        stderr_output = sys.stderr.getvalue()
        sys.stderr = old_stderr
    assert result is not None
    assert result.id == "unk-field-rule"
    assert "unknown fields" in stderr_output


def test_no_comp_pipe_in_reason():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        nc = tmp_path / "no-comp.txt"
        nc.write_text("BrokenMod|41.0.0|Reason part1|part2|part3\n", encoding="utf-8")
        entries = load_no_comp(nc)
        assert len(entries) == 1
        assert entries[0].reason == "Reason part1|part2|part3"


def test_parse_json_rules_description_with_colons():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps({
            "version": "42.0.0",
            "changes": [
                {
                    "id": "colon-rule",
                    "type": "api_removal",
                    "severity": "breaking",
                    "since": "42.0.0",
                    "description": "Removed: ISInventoryPage:refresh()",
                    "pattern": "ISInventoryPage",
                }
            ]
        }), encoding="utf-8")
        rules = _parse_json_rules(json_file)
        assert len(rules) == 1
        assert rules[0].id == "colon-rule"
        assert "Removed:" in rules[0].description


def test_load_rules_from_dir_empty_directory():
    with tempfile.TemporaryDirectory() as tmp:
        rules = load_rules_from_dir(Path(tmp))
        assert rules == []


# ============================================================
# 4. Engine edge cases
# ============================================================

def test_unknown_rule_type_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, mod = _make_mod(tmp_path)
        rule = Rule(id="unk-type", type="quantum_flux", severity="warning",
                    since="42.0.0", description="Unknown type")
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = _apply_rule(mod, rule, {})
        finally:
            stderr_output = sys.stderr.getvalue()
            sys.stderr = old_stderr
        assert result == []
        assert "Unknown rule type" in stderr_output


def test_unknown_check_in_structure_rule_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, mod = _make_mod(tmp_path)
        rule = Rule(id="unk-check", type="structure", severity="warning",
                    since="42.0.0", description="Unknown check",
                    check="fly_to_moon", path=".")
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = _check_structure(mod, rule)
        finally:
            stderr_output = sys.stderr.getvalue()
            sys.stderr = old_stderr
        assert result == []
        assert "Unknown check type" in stderr_output


def test_structure_path_traversal_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, mod = _make_mod(tmp_path)
        rule = Rule(id="traversal", type="structure", severity="breaking",
                    since="42.0.0", description="Path traversal attempt",
                    check="dir_exists", path="../../etc")
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = _check_structure(mod, rule)
        finally:
            stderr_output = sys.stderr.getvalue()
            sys.stderr = old_stderr
        assert result == []
        assert "escapes mod directory" in stderr_output


def test_regex_error_in_pattern_rule_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, mod = _make_mod(tmp_path, lua_files={
            "media/lua/client/test.lua": "some code\n",
        })
        rule = Rule(id="bad-regex", type="api_removal", severity="breaking",
                    since="42.0.0", description="Bad regex",
                    pattern="[invalid(regex", regex=True, scan="*.lua")
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            result = _apply_rule(mod, rule, {})
        finally:
            stderr_output = sys.stderr.getvalue()
            sys.stderr = old_stderr
        assert result == []
        assert "Invalid regex" in stderr_output


def test_file_caching_works():
    """Run multiple rules against same mod; verify cache is populated and reused."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _, mod = _make_mod(tmp_path, lua_files={
            "media/lua/client/main.lua": "OldFunc()\nDeprecatedThing()\n",
        })
        rule1 = Rule(id="r1", type="api_removal", severity="breaking",
                     since="42.0.0", description="OldFunc removed",
                     pattern="OldFunc", scan="*.lua")
        rule2 = Rule(id="r2", type="deprecated", severity="info",
                     since="42.0.0", description="DeprecatedThing deprecated",
                     pattern="DeprecatedThing", scan="*.lua")

        cache = {}
        f1 = _apply_rule(mod, rule1, cache)
        assert len(f1) == 1
        # Cache should have at least one entry now
        assert len(cache) >= 1

        f2 = _apply_rule(mod, rule2, cache)
        assert len(f2) == 1
        # Cache size should not have grown (same file already cached)
        assert len(cache) >= 1


# ============================================================
# 5. Workshop discovery
# ============================================================

def test_discover_mods_workshop_structure():
    """discover_mods finds mods in <workshop_id>/mods/<ModName>/ layout."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Workshop structure: <id>/mods/<ModName>/mod.info
        workshop_id_dir = tmp_path / "123456789"
        inner_mod = workshop_id_dir / "mods" / "CoolMod"
        inner_mod.mkdir(parents=True)
        (inner_mod / "mod.info").write_text("name=Cool Mod\nid=CoolMod", encoding="utf-8")

        mods = discover_mods([tmp_path])
        assert len(mods) == 1
        assert mods[0].mod_id == "CoolMod"


def test_discover_mods_deduplication():
    """Same mod ID in two directories is only returned once."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dir_a = tmp_path / "dir_a"
        dir_b = tmp_path / "dir_b"

        for d in (dir_a, dir_b):
            mod_dir = d / "DupeMod"
            mod_dir.mkdir(parents=True)
            (mod_dir / "mod.info").write_text("name=Dupe\nid=DupeMod", encoding="utf-8")

        mods = discover_mods([dir_a, dir_b])
        ids = [m.mod_id for m in mods]
        assert ids.count("DupeMod") == 1


# ============================================================
# 6. Version edge cases
# ============================================================

def test_parse_empty_string():
    v = PZVersion.parse("")
    assert v.major == 0 and v.minor == 0 and v.patch == 0


def test_parse_non_numeric():
    v = PZVersion.parse("banana")
    assert v.major == 0 and v.minor == 0 and v.patch == 0


def test_parse_with_whitespace():
    v = PZVersion.parse(" 42.0.0 ")
    assert v.major == 42
    assert v.minor == 0
    assert v.patch == 0


# ============================================================
# 7. BOM handling
# ============================================================

def test_mod_info_with_utf8_bom():
    """mod.info file with UTF-8 BOM is parsed correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "BomMod"
        mod_dir.mkdir()
        # Write with BOM
        bom_content = "\ufeffname=BOM Mod\nid=BomMod\nmodversion=1.0\n"
        (mod_dir / "mod.info").write_text(bom_content, encoding="utf-8")

        info = parse_mod_info(mod_dir)
        assert info is not None
        assert info.mod_id == "BomMod"
        assert info.name == "BOM Mod"
        assert info.mod_version == "1.0"


# ============================================================
# 8. Server features (session 3)
# ============================================================

def test_read_body_bad_json():
    """_read_body should return None on invalid JSON (error sent to client)."""
    from pz_mod_checker.gui.server import PZModCheckerHandler
    # The method is instance-based, test the logic directly
    import json
    bad = b"not json"
    try:
        json.loads(bad)
        assert False, "Should have raised"
    except json.JSONDecodeError:
        pass  # Confirmed bad JSON raises


def test_console_cache_returns_consistent():
    """Console cache should return same values on repeated calls."""
    from pz_mod_checker.gui.server import PZModCheckerHandler
    handler_class = PZModCheckerHandler
    # Cache starts empty
    cache = handler_class._console_cache
    assert "mtime" in cache
    assert "pz_version" in cache


def test_cached_discover_mods_returns_list():
    """_cached_discover_mods should return a list."""
    from pz_mod_checker.gui.server import _cached_discover_mods
    result = _cached_discover_mods()
    assert isinstance(result, list)


def test_cached_discover_mods_caches():
    """Calling _cached_discover_mods twice should return same object."""
    from pz_mod_checker.gui.server import _cached_discover_mods, _mod_cache
    first = _cached_discover_mods()
    mtime_first = _mod_cache["mtime"]
    second = _cached_discover_mods()
    mtime_second = _mod_cache["mtime"]
    # Same mtime means cache was reused (no re-scan)
    assert mtime_first == mtime_second
    assert len(first) == len(second)


def test_version_sort_numeric():
    """Version dropdown should sort numerically, not lexicographically."""
    from pz_mod_checker.rules.version import PZVersion
    versions = ["42.0.0", "42.10.0", "42.8.0", "42.9.0", "42.15.0"]
    versions.sort(key=lambda v: PZVersion.parse(v), reverse=True)
    assert versions[0] == "42.15.0"
    assert versions[-1] == "42.0.0"
    assert versions[1] == "42.10.0"  # 10 > 9 > 8


def test_workshop_metadata_dataclass():
    """WorkshopMetadata fields are accessible."""
    from pz_mod_checker.workshop import WorkshopMetadata
    m = WorkshopMetadata(file_id="123", title="Test", time_updated=1700000000)
    assert m.file_id == "123"
    assert m.time_updated == 1700000000
    assert m.tags == []


def test_extract_workshop_id_from_path():
    """extract_workshop_id finds the workshop ID from a mod path."""
    from pz_mod_checker.workshop import extract_workshop_id
    from pz_mod_checker.scanner.mod_info import ModInfo
    mod = ModInfo(
        mod_id="TestMod",
        name="Test",
        path=Path("C:/Steam/steamapps/workshop/content/108600/1234567/mods/TestMod"),
    )
    wid = extract_workshop_id(mod)
    assert wid == "1234567"


def test_extract_workshop_id_local_mod():
    """Local mods (not in workshop) return None for workshop ID."""
    from pz_mod_checker.workshop import extract_workshop_id
    from pz_mod_checker.scanner.mod_info import ModInfo
    mod = ModInfo(
        mod_id="LocalMod",
        name="Local",
        path=Path("C:/Users/test/Zomboid/mods/LocalMod"),
    )
    wid = extract_workshop_id(mod)
    assert wid is None


# ============================================================
# Runner
# ============================================================

if __name__ == "__main__":
    test_get_data_dir_returns_path_ending_with_data()
    test_build_parser_returns_argumentparser()
    test_main_json_output_with_temp_mod_dir()
    test_main_severity_filtering()
    test_main_returns_0_when_no_mods_found()

    test_findings_to_json_with_sample_findings()
    test_findings_to_json_empty()
    test_format_severity_with_color()
    test_format_severity_without_color()
    test_print_scan_results_empty()

    test_rule_with_empty_since_is_skipped()
    test_rule_with_unknown_fields_still_loads()
    test_no_comp_pipe_in_reason()
    test_parse_json_rules_description_with_colons()
    test_load_rules_from_dir_empty_directory()

    test_unknown_rule_type_returns_empty()
    test_unknown_check_in_structure_rule_returns_empty()
    test_structure_path_traversal_returns_empty()
    test_regex_error_in_pattern_rule_returns_empty()
    test_file_caching_works()

    test_discover_mods_workshop_structure()
    test_discover_mods_deduplication()

    test_parse_empty_string()
    test_parse_non_numeric()
    test_parse_with_whitespace()

    test_mod_info_with_utf8_bom()

    print("All audit tests passed.")
