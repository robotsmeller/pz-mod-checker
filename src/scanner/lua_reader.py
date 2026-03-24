"""Read and search Lua source files within mods."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchHit:
    """A pattern match within a file."""

    file_path: Path
    line_number: int
    line_text: str
    pattern: str


def find_lua_files(root: Path) -> list[Path]:
    """Recursively find all .lua files under a directory."""
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.lua"))


def find_script_files(root: Path) -> list[Path]:
    """Recursively find all .txt script files under a directory."""
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.txt"))


def find_translation_files(root: Path) -> list[Path]:
    """Find translation files in the Translate directory."""
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.txt"))


def search_files(
    files: list[Path],
    pattern: str,
    is_regex: bool = False,
) -> list[SearchHit]:
    """Search a list of files for a pattern.

    Args:
        files: Files to search.
        pattern: String or regex pattern to find.
        is_regex: If True, treat pattern as regex.

    Returns:
        List of SearchHit for each match.
    """
    hits: list[SearchHit] = []
    compiled = re.compile(pattern) if is_regex else None

    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        for line_num, line in enumerate(text.splitlines(), start=1):
            matched = False
            if compiled is not None:
                matched = bool(compiled.search(line))
            else:
                matched = pattern in line

            if matched:
                hits.append(SearchHit(
                    file_path=file_path,
                    line_number=line_num,
                    line_text=line.strip(),
                    pattern=pattern,
                ))

    return hits


def check_file_encoding(file_path: Path) -> str:
    """Check if a file is valid UTF-8. Returns 'utf-8' or 'unknown'."""
    try:
        file_path.read_text(encoding="utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "unknown"
