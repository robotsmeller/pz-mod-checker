"""PZ mod enable/disable manager — read, write, and manage mod lists and profiles."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .scanner.discovery import discover_mods


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ModList:
    """Parsed mod list from default.txt."""

    mods: list[str]
    maps: list[str] = field(default_factory=list)
    version: int = 1


@dataclass
class Profile:
    """A named mod profile/preset."""

    name: str
    mod_ids: list[str]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_zomboid_dir() -> Path:
    """Return the Zomboid user directory."""
    return Path.home() / "Zomboid"


def get_default_txt_path(zomboid_dir: Path | None = None) -> Path:
    """Return the path to default.txt (active mod list)."""
    if zomboid_dir is None:
        zomboid_dir = get_zomboid_dir()
    return zomboid_dir / "mods" / "default.txt"


def get_profiles_path(zomboid_dir: Path | None = None) -> Path:
    """Return the path to pz_modlist_settings.cfg (profiles)."""
    if zomboid_dir is None:
        zomboid_dir = get_zomboid_dir()
    return zomboid_dir / "Lua" / "pz_modlist_settings.cfg"


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_mod_list(path: Path | None = None) -> Path:
    """Create a timestamped backup of default.txt. Returns the backup path."""
    if path is None:
        path = get_default_txt_path()
    if not path.is_file():
        raise FileNotFoundError(f"Cannot backup: {path} does not exist")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def read_mod_list(path: Path | None = None) -> ModList:
    """Parse default.txt into a ModList."""
    if path is None:
        path = get_default_txt_path()
    if not path.is_file():
        return ModList(mods=[])

    text = path.read_text(encoding="utf-8", errors="replace")
    mods: list[str] = []
    maps: list[str] = []
    version = 1
    in_mods = False
    in_maps = False

    for line in text.splitlines():
        stripped = line.strip()

        # Parse VERSION line
        if stripped.startswith("VERSION"):
            _, _, ver_part = stripped.partition("=")
            ver_part = ver_part.strip().rstrip(",")
            if ver_part.isdigit():
                version = int(ver_part)
            continue

        if stripped == "mods":
            in_mods = True
            in_maps = False
            continue
        if stripped == "maps":
            in_maps = True
            in_mods = False
            continue
        if stripped == "{":
            continue
        if stripped == "}":
            in_mods = False
            in_maps = False
            continue

        if stripped.startswith("mod = "):
            mod_id = stripped[6:]  # After "mod = "
            if mod_id.endswith(","):
                mod_id = mod_id[:-1]
            if in_mods:
                mods.append(mod_id)
            elif in_maps:
                maps.append(mod_id)

    return ModList(mods=mods, maps=maps, version=version)


def read_profiles(path: Path | None = None) -> list[Profile]:
    """Parse pz_modlist_settings.cfg into profiles."""
    if path is None:
        path = get_profiles_path()
    if not path.is_file():
        return []

    profiles: list[Profile] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, _, ids_str = line.partition(":")
        mod_ids = [mid for mid in ids_str.split(";") if mid]
        profiles.append(Profile(name=name, mod_ids=mod_ids))
    return profiles


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def write_mod_list(mod_list: ModList, path: Path | None = None) -> None:
    """Write a ModList to default.txt format.

    Creates a timestamped backup before overwriting an existing file.
    """
    if path is None:
        path = get_default_txt_path()

    # Always backup first
    if path.is_file():
        backup_mod_list(path)

    lines = [f"VERSION = {mod_list.version},", "", "mods", "{"]
    for mod_id in mod_list.mods:
        lines.append(f"    mod = {mod_id},")
    lines.append("}")
    lines.append("")
    lines.append("maps")
    lines.append("{")
    for map_id in mod_list.maps:
        lines.append(f"    mod = {map_id},")
    lines.append("}")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_profiles(profiles: list[Profile], path: Path | None = None) -> None:
    """Write profiles to pz_modlist_settings.cfg.

    Creates parent directories if needed.
    """
    if path is None:
        path = get_profiles_path()

    lines: list[str] = []
    for profile in profiles:
        ids_str = ";".join(profile.mod_ids)
        if ids_str:
            ids_str += ";"
        lines.append(f"{profile.name}:{ids_str}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def enable_mods(mod_ids: list[str], path: Path | None = None) -> ModList:
    """Enable specific mods (add to default.txt if not already present).

    Returns the updated ModList.
    """
    mod_list = read_mod_list(path)
    existing = set(mod_list.mods)
    for mod_id in mod_ids:
        if mod_id not in existing:
            mod_list.mods.append(mod_id)
            existing.add(mod_id)
    write_mod_list(mod_list, path)
    return mod_list


def disable_mods(mod_ids: list[str], path: Path | None = None) -> ModList:
    """Disable specific mods (remove from default.txt).

    Returns the updated ModList.
    """
    mod_list = read_mod_list(path)
    remove = set(mod_ids)
    mod_list.mods = [m for m in mod_list.mods if m not in remove]
    write_mod_list(mod_list, path)
    return mod_list


def enable_only(mod_ids: list[str], path: Path | None = None) -> ModList:
    """Enable ONLY the specified mods, disabling everything else.

    Preserves maps. Returns the updated ModList.
    """
    mod_list = read_mod_list(path)
    mod_list.mods = list(mod_ids)
    write_mod_list(mod_list, path)
    return mod_list


def save_profile(
    name: str,
    mod_list: ModList | None = None,
    zomboid_dir: Path | None = None,
) -> None:
    """Save the current mod list (or a provided one) as a named profile."""
    if mod_list is None:
        mod_list = read_mod_list(get_default_txt_path(zomboid_dir))

    profiles_path = get_profiles_path(zomboid_dir)
    profiles = read_profiles(profiles_path)

    # Replace existing profile with the same name, or append
    replaced = False
    for i, profile in enumerate(profiles):
        if profile.name == name:
            profiles[i] = Profile(name=name, mod_ids=list(mod_list.mods))
            replaced = True
            break
    if not replaced:
        profiles.append(Profile(name=name, mod_ids=list(mod_list.mods)))

    write_profiles(profiles, profiles_path)


def load_profile(name: str, zomboid_dir: Path | None = None) -> ModList:
    """Load a named profile and apply it to default.txt.

    Raises KeyError if the profile does not exist.
    Returns the loaded ModList.
    """
    profiles = read_profiles(get_profiles_path(zomboid_dir))
    for profile in profiles:
        if profile.name == name:
            mod_list_path = get_default_txt_path(zomboid_dir)
            # Read existing to preserve maps and version
            existing = read_mod_list(mod_list_path)
            existing.mods = list(profile.mod_ids)
            write_mod_list(existing, mod_list_path)
            return existing
    raise KeyError(f"Profile not found: {name!r}")


def list_profiles(zomboid_dir: Path | None = None) -> list[Profile]:
    """List all saved profiles."""
    return read_profiles(get_profiles_path(zomboid_dir))


def get_mod_status(
    zomboid_dir: Path | None = None,
    mod_dirs: list[Path] | None = None,
) -> list[dict]:
    """Get status of all discovered mods (enabled/disabled).

    Cross-references discovered mods with default.txt.

    Returns:
        List of dicts with keys: mod_id, name, enabled, path.
    """
    mod_list = read_mod_list(get_default_txt_path(zomboid_dir))
    enabled_ids = set(mod_list.mods)

    discovered = discover_mods(mod_dirs)

    results: list[dict] = []
    for mod in discovered:
        results.append({
            "mod_id": mod.mod_id,
            "name": mod.name,
            "enabled": mod.mod_id in enabled_ids,
            "path": str(mod.path),
        })
    return results
