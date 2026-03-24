"""Discover mods in Project Zomboid mod directories."""

from __future__ import annotations

import platform
from pathlib import Path

from .mod_info import ModInfo, parse_mod_info


# Common PZ mod locations by platform
def get_default_mod_paths() -> list[Path]:
    """Return default mod directory paths for the current platform."""
    system = platform.system()
    home = Path.home()

    paths: list[Path] = []

    if system == "Windows":
        # User mods
        paths.append(home / "Zomboid" / "mods")
        # Steam Workshop mods (common Steam install locations)
        steam_common = [
            Path("C:/Program Files (x86)/Steam/steamapps/workshop/content/108600"),
            Path("C:/Program Files/Steam/steamapps/workshop/content/108600"),
            home / "Steam" / "steamapps" / "workshop" / "content" / "108600",
        ]
        paths.extend(steam_common)
    elif system == "Linux":
        paths.append(home / "Zomboid" / "mods")
        paths.append(home / ".steam" / "steam" / "steamapps" / "workshop" / "content" / "108600")
        paths.append(home / ".local" / "share" / "Steam" / "steamapps" / "workshop" / "content" / "108600")
    elif system == "Darwin":
        paths.append(home / "Zomboid" / "mods")
        paths.append(home / "Library" / "Application Support" / "Steam" / "steamapps" / "workshop" / "content" / "108600")

    return paths


def discover_mods(mod_dirs: list[Path] | None = None) -> list[ModInfo]:
    """Scan directories for PZ mods, returning parsed ModInfo for each.

    Args:
        mod_dirs: Directories to scan. Uses defaults if None.

    Returns:
        List of ModInfo for each valid mod found.
    """
    if mod_dirs is None:
        mod_dirs = get_default_mod_paths()

    mods: list[ModInfo] = []
    seen_ids: set[str] = set()

    for mod_dir in mod_dirs:
        if not mod_dir.is_dir():
            continue

        for entry in sorted(mod_dir.iterdir()):
            if not entry.is_dir():
                continue

            mod_info = parse_mod_info(entry)
            if mod_info is None:
                continue

            # Deduplicate by mod ID (Workshop may duplicate user mods)
            if mod_info.mod_id in seen_ids:
                continue
            seen_ids.add(mod_info.mod_id)

            mods.append(mod_info)

    return mods


def discover_single_mod(mod_path: Path) -> ModInfo | None:
    """Parse a single mod directory.

    Args:
        mod_path: Path to the mod's root directory.

    Returns:
        ModInfo if valid, None otherwise.
    """
    if not mod_path.is_dir():
        return None
    return parse_mod_info(mod_path)
