"""Parse Project Zomboid mod.info files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModInfo:
    """Parsed mod.info data."""

    mod_id: str
    name: str
    path: Path
    mod_version: str = ""
    version_min: str = ""
    version_max: str = ""
    require: list[str] = field(default_factory=list)
    description: str = ""
    url: str = ""
    poster: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def has_b42_folder(self) -> bool:
        return (self.path / "42").is_dir()

    @property
    def has_common_folder(self) -> bool:
        return (self.path / "common").is_dir()

    @property
    def lua_root(self) -> Path:
        """Return the best Lua root: prefer 42/media/lua, fall back to media/lua."""
        b42_lua = self.path / "42" / "media" / "lua"
        if b42_lua.is_dir():
            return b42_lua
        return self.path / "media" / "lua"

    @property
    def script_root(self) -> Path:
        """Return the scripts directory."""
        b42_scripts = self.path / "42" / "media" / "scripts"
        if b42_scripts.is_dir():
            return b42_scripts
        return self.path / "media" / "scripts"

    @property
    def translate_root(self) -> Path:
        """Return the translation directory."""
        b42_tr = self.path / "42" / "media" / "lua" / "shared" / "Translate"
        if b42_tr.is_dir():
            return b42_tr
        return self.path / "media" / "lua" / "shared" / "Translate"


def parse_mod_info(mod_dir: Path) -> ModInfo | None:
    """Parse a mod.info file from a mod directory.

    Checks both root mod.info and 42/mod.info (B42 structure).
    Returns None if no valid mod.info found.
    """
    # Prefer 42/mod.info for B42 mods
    candidates = [mod_dir / "42" / "mod.info", mod_dir / "mod.info"]

    for info_path in candidates:
        if info_path.is_file():
            return _parse_file(info_path, mod_dir)

    return None


def _parse_file(info_path: Path, mod_dir: Path) -> ModInfo:
    """Parse a single mod.info file into a ModInfo dataclass."""
    raw: dict[str, str] = {}

    text = info_path.read_text(encoding="utf-8-sig", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            raw[key.strip()] = value.strip()

    require_str = raw.get("require", "")
    require_list = [r.strip() for r in require_str.split(",") if r.strip()] if require_str else []

    return ModInfo(
        mod_id=raw.get("id", mod_dir.name),
        name=raw.get("name", mod_dir.name),
        path=mod_dir,
        mod_version=raw.get("modversion", ""),
        version_min=raw.get("versionMin", ""),
        version_max=raw.get("versionMax", ""),
        require=require_list,
        description=raw.get("description", ""),
        url=raw.get("url", ""),
        poster=raw.get("poster", ""),
        raw=raw,
    )
