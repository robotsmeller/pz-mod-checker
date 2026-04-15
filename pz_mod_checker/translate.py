"""Translation shim generator — finds mods with missing EN translation keys and generates stub files."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .paths import get_zomboid_dir
from .scanner.discovery import discover_mods

SHIM_MOD_ID = "pzmc_translation_shim"
SHIM_MOD_NAME = "PZ Mod Checker - Translation Stubs"
_SHIM_DESCRIPTION = (
    "Auto-generated stub translations by PZ Mod Checker. "
    "Provides placeholder EN strings for mods missing translation files. "
    "Regenerate this via the Translate tab in the PZ Mod Checker GUI."
)

_GET_TEXT_RE = re.compile(r'getText(?:OrNull)?\s*\(\s*["\']([^"\']+)["\']')
_KEY_RE = re.compile(r'^\s*(\w+)\s*=\s*"', re.MULTILINE)

_KEY_PREFIXES = [
    "IGUI_", "UI_", "Sandbox_", "Challenge_", "Tooltip_",
    "ContextMenu_", "ItemName_", "DisplayName_", "Moodle_",
]


@dataclass
class TranslationGap:
    mod_id: str
    mod_name: str
    workshop_id: str | None
    missing_keys: list[str]
    has_any_translation: bool
    total_keys: int


def key_to_string(key: str) -> str:
    """Convert a translation key to a human-readable placeholder string.

    Examples:
      UI_SomeMod_OpenWindow  -> "Open Window"
      IGUI_Sandbox_SpawnRate -> "Spawn Rate"
    """
    # Strip known type prefixes
    for prefix in _KEY_PREFIXES:
        if key.startswith(prefix):
            key = key[len(prefix):]
            break

    # Strip mod-specific prefix (first segment if it looks like a mod name)
    parts = key.split("_", 1)
    if len(parts) == 2 and 2 <= len(parts[0]) <= 25 and parts[0][0].isupper():
        key = parts[1]

    # Split on underscores and camelCase boundaries
    key = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', key)
    key = re.sub(r'([a-z\d])([A-Z])', r'\1 \2', key)
    key = key.replace('_', ' ')

    return ' '.join(w.capitalize() for w in key.split() if w)


def scan_translation_gaps(
    include_no_translation: bool = True,
    include_partial: bool = True,
) -> list[TranslationGap]:
    """Scan all installed mods for missing EN translation keys.

    Args:
        include_no_translation: Include mods with no Translate folder at all.
        include_partial: Include mods that have some translations but are missing keys.

    Returns:
        List of TranslationGap sorted by missing key count descending.
    """
    mods = discover_mods()
    gaps: list[TranslationGap] = []

    for mod in mods:
        # Skip the shim itself
        if mod.mod_id == SHIM_MOD_ID:
            continue

        gap = _check_mod(mod.path, mod.mod_id, mod.name, include_no_translation, include_partial)
        if gap is not None:
            gaps.append(gap)

    gaps.sort(key=lambda g: len(g.missing_keys), reverse=True)
    return gaps


def _check_mod(
    mod_root: Path,
    mod_id: str,
    mod_name: str,
    include_no_translation: bool,
    include_partial: bool,
) -> TranslationGap | None:
    """Check a single mod root for missing translation keys. Returns None if no gaps."""
    lua_files = list(mod_root.rglob("*.lua"))
    if not lua_files:
        return None

    all_keys: set[str] = set()
    for lua_file in lua_files:
        try:
            content = lua_file.read_text(encoding="utf-8", errors="ignore")
            all_keys.update(_GET_TEXT_RE.findall(content))
        except OSError:
            pass

    if not all_keys:
        return None

    existing_keys: set[str] = set()
    has_translation = False
    for translate_dir in mod_root.rglob("Translate"):
        en_dir = translate_dir / "EN"
        if en_dir.is_dir():
            txt_files = list(en_dir.glob("*.txt"))
            if txt_files:
                has_translation = True
                for txt in txt_files:
                    try:
                        content = txt.read_text(encoding="utf-8", errors="ignore")
                        existing_keys.update(_KEY_RE.findall(content))
                    except OSError:
                        pass

    missing = sorted(all_keys - existing_keys)
    if not missing:
        return None

    if not has_translation and not include_no_translation:
        return None
    if has_translation and not include_partial:
        return None

    # Resolve workshop ID from path
    workshop_id: str | None = None
    parts = mod_root.parts
    for i, part in enumerate(parts):
        if part == "108600" and i + 1 < len(parts):
            candidate = parts[i + 1]
            if candidate.isdigit():
                workshop_id = candidate
                break

    return TranslationGap(
        mod_id=mod_id,
        mod_name=mod_name,
        workshop_id=workshop_id,
        missing_keys=missing,
        has_any_translation=has_translation,
        total_keys=len(all_keys),
    )


def shim_path(zomboid_dir: Path | None = None) -> Path:
    """Return the path to the shim mod folder."""
    return (zomboid_dir or get_zomboid_dir()) / "mods" / SHIM_MOD_ID


def get_shim_status(zomboid_dir: Path | None = None) -> dict:
    """Return current status of the shim mod."""
    from .manager import get_default_txt_path, read_mod_list

    path = shim_path(zomboid_dir)
    exists = path.is_dir()
    key_count = 0

    if exists:
        txt = path / "media" / "lua" / "shared" / "Translate" / "EN" / "PZMC_Stubs_EN.txt"
        if txt.is_file():
            try:
                content = txt.read_text(encoding="utf-8", errors="ignore")
                key_count = len(_KEY_RE.findall(content))
            except OSError:
                pass

    try:
        mod_list = read_mod_list(get_default_txt_path(zomboid_dir))
        enabled = SHIM_MOD_ID in mod_list.mods
    except Exception:
        enabled = False

    return {
        "exists": exists,
        "enabled": enabled,
        "key_count": key_count,
        "path": str(path),
    }


def generate_shim(
    gaps: list[TranslationGap],
    key_format: str = "title_case",
    zomboid_dir: Path | None = None,
) -> dict:
    """Generate (or update) the translation shim mod.

    Args:
        gaps: List of TranslationGap from scan_translation_gaps().
        key_format: "title_case" converts key names; "raw" uses the raw key as value.
        zomboid_dir: Override for ~/Zomboid directory.

    Returns:
        Dict with path, key_count, mod_count.
    """
    base = shim_path(zomboid_dir)
    base.mkdir(parents=True, exist_ok=True)

    mod_info_path = base / "mod.info"
    mod_info_path.write_text(
        f"name={SHIM_MOD_NAME}\n"
        f"id={SHIM_MOD_ID}\n"
        f"description={_SHIM_DESCRIPTION}\n"
        f"versionMin=42.0.0\n"
        f"modversion=1.0\n",
        encoding="utf-8",
    )

    translate_dir = base / "media" / "lua" / "shared" / "Translate" / "EN"
    translate_dir.mkdir(parents=True, exist_ok=True)

    lines = ["VERSION = 1,", "EN = {"]
    total_keys = 0

    for gap in gaps:
        if not gap.missing_keys:
            continue
        lines.append(f"    -- [{gap.mod_name}]")
        for key in gap.missing_keys:
            value = key_to_string(key) if key_format == "title_case" else key
            value = value.replace('"', '\\"')
            lines.append(f'    {key} = "{value}",')
            total_keys += 1
        lines.append("")

    lines.append("}")

    txt_path = translate_dir / "PZMC_Stubs_EN.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "path": str(base),
        "key_count": total_keys,
        "mod_count": len([g for g in gaps if g.missing_keys]),
    }


def remove_shim(zomboid_dir: Path | None = None) -> None:
    """Remove the shim mod folder from disk and disable it in default.txt."""
    from .manager import disable_mods

    disable_mods([SHIM_MOD_ID])
    path = shim_path(zomboid_dir)
    if path.is_dir():
        shutil.rmtree(path)
