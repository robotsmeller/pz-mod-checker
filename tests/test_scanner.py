"""Tests for mod scanner (discovery, mod_info parsing, lua reading)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scanner.mod_info import ModInfo, parse_mod_info
from src.scanner.lua_reader import search_files, SearchHit, find_lua_files
from src.scanner.discovery import discover_single_mod


def _create_test_mod(tmp: Path, mod_info_content: str, lua_files: dict[str, str] | None = None) -> Path:
    """Create a temporary mod directory for testing."""
    mod_dir = tmp / "TestMod"
    mod_dir.mkdir(parents=True)

    (mod_dir / "mod.info").write_text(mod_info_content, encoding="utf-8")

    if lua_files:
        for rel_path, content in lua_files.items():
            file_path = mod_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    return mod_dir


def test_parse_mod_info():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = _create_test_mod(tmp_path, """
name=Test Mod
id=TestMod
description=A test mod
modversion=1.0.0
versionMin=42.0.0
require=OtherMod,AnotherMod
url=https://example.com
""")

        info = parse_mod_info(mod_dir)
        assert info is not None
        assert info.mod_id == "TestMod"
        assert info.name == "Test Mod"
        assert info.mod_version == "1.0.0"
        assert info.version_min == "42.0.0"
        assert info.require == ["OtherMod", "AnotherMod"]


def test_parse_mod_info_missing():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = tmp_path / "EmptyMod"
        mod_dir.mkdir()
        info = parse_mod_info(mod_dir)
        assert info is None


def test_b42_folder_detection():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = _create_test_mod(tmp_path, "name=Test\nid=Test")
        assert not ModInfo(mod_id="t", name="t", path=mod_dir).has_b42_folder
        assert not ModInfo(mod_id="t", name="t", path=mod_dir).has_common_folder

        (mod_dir / "42").mkdir()
        (mod_dir / "common").mkdir()
        info = parse_mod_info(mod_dir)
        assert info.has_b42_folder
        assert info.has_common_folder


def test_search_lua_files():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = _create_test_mod(tmp_path, "name=Test\nid=Test", {
            "media/lua/client/main.lua": """
local function doStuff()
    ISInventoryPage:refreshContainer()
    local player = getSpecificPlayer(0)
end
""",
            "media/lua/shared/utils.lua": """
function getHelper()
    return true
end
""",
        })

        lua_files = find_lua_files(mod_dir / "media" / "lua")
        assert len(lua_files) == 2

        hits = search_files(lua_files, "ISInventoryPage")
        assert len(hits) == 1
        assert hits[0].line_number == 3
        assert "ISInventoryPage" in hits[0].line_text

        hits2 = search_files(lua_files, "getSpecificPlayer")
        assert len(hits2) == 1


def test_discover_single_mod():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod_dir = _create_test_mod(tmp_path, "name=Test\nid=TestSingle")
        info = discover_single_mod(mod_dir)
        assert info is not None
        assert info.mod_id == "TestSingle"


if __name__ == "__main__":
    test_parse_mod_info()
    test_parse_mod_info_missing()
    test_b42_folder_detection()
    test_search_lua_files()
    test_discover_single_mod()
    print("All scanner tests passed.")
