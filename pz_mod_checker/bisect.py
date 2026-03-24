"""Binary-search mod bisect — find which mod crashes Project Zomboid."""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .manager import (
    ModList,
    get_default_txt_path,
    get_zomboid_dir,
    load_profile,
    read_mod_list,
    save_profile,
    write_mod_list,
)
from .scanner.discovery import discover_mods


# ---------------------------------------------------------------------------
# State dataclass
# ---------------------------------------------------------------------------

@dataclass
class BisectState:
    """Persistent state for a mod bisect session."""

    schema_version: int
    original_mods: list[str]
    maps: list[str]
    mod_list_version: int
    suspects: list[str]
    known_good: list[str]
    known_bad: list[str]
    current_enabled: list[str]
    round_number: int
    max_rounds: int
    status: str  # "awaiting_result", "complete", "inconclusive", "aborted"
    created_at: str
    backup_profile: str
    pid: int


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _get_state_path(zomboid_dir: Path | None = None) -> Path:
    """Return path to bisect_state.json, creating parent dir if needed."""
    zdir = zomboid_dir or get_zomboid_dir()
    state_dir = zdir / ".pz-mod-checker"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "bisect_state.json"


def save_state(state: BisectState, zomboid_dir: Path | None = None) -> None:
    """Save bisect state to JSON."""
    path = _get_state_path(zomboid_dir)
    data = asdict(state)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_state(zomboid_dir: Path | None = None) -> BisectState | None:
    """Load bisect state. Returns None if no state file or corrupted."""
    path = _get_state_path(zomboid_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return BisectState(
            schema_version=data["schema_version"],
            original_mods=data["original_mods"],
            maps=data["maps"],
            mod_list_version=data["mod_list_version"],
            suspects=data["suspects"],
            known_good=data["known_good"],
            known_bad=data["known_bad"],
            current_enabled=data["current_enabled"],
            round_number=data["round_number"],
            max_rounds=data["max_rounds"],
            status=data["status"],
            created_at=data["created_at"],
            backup_profile=data["backup_profile"],
            pid=data["pid"],
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def has_active_bisect(zomboid_dir: Path | None = None) -> bool:
    """Check if there's an active bisect session."""
    state = load_state(zomboid_dir)
    return state is not None and state.status == "awaiting_result"


# ---------------------------------------------------------------------------
# Dependency groups (union-find)
# ---------------------------------------------------------------------------

def _build_dependency_groups(
    mod_ids: list[str],
    mod_dirs: list[Path] | None = None,
) -> list[list[str]]:
    """Build dependency groups using union-find on require fields.

    Returns list of groups. Each group is a list of mod IDs that must
    stay together during bisect partitioning. Mods with no dependencies
    are singleton groups.
    """
    mods = discover_mods(mod_dirs)
    mod_map = {m.mod_id: m for m in mods}
    active_set = set(mod_ids)

    # Union-find
    parent: dict[str, str] = {mid: mid for mid in mod_ids}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Union mods with their dependencies (both directions)
    for mid in mod_ids:
        info = mod_map.get(mid)
        if info and info.require:
            for dep in info.require:
                if dep in active_set:
                    union(mid, dep)

    # Collect groups preserving original order within each group
    groups: dict[str, list[str]] = {}
    for mid in mod_ids:
        root = find(mid)
        groups.setdefault(root, []).append(mid)

    return list(groups.values())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_and_validate(zomboid_dir: Path | None = None) -> BisectState:
    """Load state and validate it's in awaiting_result status."""
    zdir = zomboid_dir or get_zomboid_dir()
    state = load_state(zdir)

    if state is None:
        raise RuntimeError(
            "No active bisect session. Use 'bisect start' to begin."
        )
    if state.status != "awaiting_result":
        raise RuntimeError(
            f"Bisect is in '{state.status}' state. "
            "Start a new one with 'bisect start'."
        )

    # Validate default.txt matches what we wrote
    actual = read_mod_list(get_default_txt_path(zdir))
    if set(actual.mods) != set(state.current_enabled):
        print(
            "Warning: default.txt was modified since last bisect round.",
            file=sys.stderr,
        )
        print(
            f"  Expected {len(state.current_enabled)} mods, "
            f"found {len(actual.mods)}.",
            file=sys.stderr,
        )

    return state


def _next_round(
    state: BisectState,
    zomboid_dir: Path,
    mod_dirs: list[Path] | None = None,
) -> BisectState:
    """Split suspects and write next test set."""
    # Build dependency groups for remaining suspects only
    groups = _build_dependency_groups(state.suspects, mod_dirs)

    # Split groups in half
    mid = len(groups) // 2
    if mid == 0:
        mid = 1  # Ensure at least one group in test set

    test_groups = groups[:mid]
    test_mods = [mod_id for g in test_groups for mod_id in g]

    # Enable: known_good + test_mods (known_good must stay enabled so
    # the game can actually run — they are confirmed non-crashing)
    enabled = state.known_good + test_mods

    state.current_enabled = enabled
    state.round_number += 1
    state.pid = os.getpid()

    # Write default.txt
    mod_list = ModList(
        mods=enabled, maps=state.maps, version=state.mod_list_version,
    )
    write_mod_list(mod_list, get_default_txt_path(zomboid_dir))

    save_state(state, zomboid_dir)
    return state


def _complete_bisect(
    state: BisectState,
    culprit: str,
    zomboid_dir: Path,
) -> BisectState:
    """Mark bisect as complete with a found culprit."""
    state.known_bad.append(culprit)
    state.suspects = [m for m in state.suspects if m != culprit]
    state.status = "complete"

    # Restore all original mods except known_bad
    bad_set = set(state.known_bad)
    restored = [m for m in state.original_mods if m not in bad_set]
    mod_list = ModList(
        mods=restored, maps=state.maps, version=state.mod_list_version,
    )
    write_mod_list(mod_list, get_default_txt_path(zomboid_dir))

    save_state(state, zomboid_dir)
    return state


def _mark_inconclusive(
    state: BisectState,
    zomboid_dir: Path,
    reason: str,
) -> BisectState:
    """Mark bisect as inconclusive and restore original mods."""
    state.status = "inconclusive"
    print(f"Bisect inconclusive: {reason}", file=sys.stderr)

    # Restore original mods
    mod_list = ModList(
        mods=state.original_mods,
        maps=state.maps,
        version=state.mod_list_version,
    )
    write_mod_list(mod_list, get_default_txt_path(zomboid_dir))

    save_state(state, zomboid_dir)
    return state


def _try_diagnose_shortcut(
    state: BisectState,
    zomboid_dir: Path,
    mod_dirs: list[Path] | None = None,
) -> str | None:
    """Try to identify culprit from console.txt logs.

    Returns the mod ID if exactly one suspect appears in error logs,
    otherwise None.
    """
    # Late import to avoid circular dependency at module level
    from .diagnose import (
        build_name_to_id_map,
        get_console_log,
        parse_console_log,
        resolve_mod_names,
    )

    log_path = get_console_log(zomboid_dir)
    if not log_path.is_file():
        return None

    try:
        diagnosis = parse_console_log(log_path)
        name_to_id = build_name_to_id_map(mod_dirs)
        resolve_mod_names(diagnosis, name_to_id)
    except Exception:
        return None

    # Only shortcut if exactly one suspect mod appears in errors
    blamed_ids = {e.mod_id for e in diagnosis.mod_errors if e.mod_id}
    suspects = set(state.suspects)
    overlap = blamed_ids & suspects

    if len(overlap) == 1:
        culprit = overlap.pop()
        print(
            f"Diagnose shortcut: console.txt identifies "
            f"'{culprit}' as the culprit.",
            file=sys.stderr,
        )
        return culprit

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def bisect_start(
    zomboid_dir: Path | None = None,
    mod_dirs: list[Path] | None = None,
) -> BisectState:
    """Start a new bisect session.

    1. Check no active bisect exists
    2. Read current mod list from default.txt
    3. Save backup profile "_bisect_backup"
    4. Build dependency groups from require fields
    5. Split groups into two halves
    6. Enable first half as test set, write default.txt
    7. Save state as "awaiting_result"

    Raises:
        RuntimeError: If a bisect is already active, or no mods to bisect.
    """
    zdir = zomboid_dir or get_zomboid_dir()

    # Check for existing bisect
    existing = load_state(zdir)
    if existing and existing.status == "awaiting_result":
        raise RuntimeError(
            "Bisect already in progress. Use 'bisect abort' to cancel, "
            "or 'bisect crash/ok' to continue."
        )

    mod_list = read_mod_list(get_default_txt_path(zdir))

    if len(mod_list.mods) == 0:
        raise RuntimeError("No active mods to bisect.")

    if len(mod_list.mods) == 1:
        raise RuntimeError(
            f"Only 1 mod active ({mod_list.mods[0]}). "
            "Disable it manually to test."
        )

    # Save backup profile
    save_profile("_bisect_backup", mod_list=mod_list, zomboid_dir=zdir)

    # Build dependency groups
    groups = _build_dependency_groups(mod_list.mods, mod_dirs)

    # Warn if largest group is > 50% of total
    largest = max(len(g) for g in groups)
    if largest > len(mod_list.mods) // 2:
        print(
            f"Warning: Largest dependency group has {largest} mods "
            f"({largest * 100 // len(mod_list.mods)}% of total). "
            "Bisect efficiency reduced.",
            file=sys.stderr,
        )

    # Max rounds: ceil(log2(num_groups)) + 1 safety margin
    max_rounds = math.ceil(math.log2(max(len(groups), 1))) + 1

    # Split groups into two halves
    mid = len(groups) // 2
    if mid == 0:
        mid = 1
    first_half_groups = groups[:mid]
    test_mods = [mod_id for g in first_half_groups for mod_id in g]

    # Write default.txt with only the test set (no known_good yet)
    new_mod_list = ModList(
        mods=test_mods, maps=mod_list.maps, version=mod_list.version,
    )
    write_mod_list(new_mod_list, get_default_txt_path(zdir))

    state = BisectState(
        schema_version=1,
        original_mods=mod_list.mods,
        maps=mod_list.maps,
        mod_list_version=mod_list.version,
        suspects=mod_list.mods.copy(),
        known_good=[],
        known_bad=[],
        current_enabled=test_mods,
        round_number=1,
        max_rounds=max_rounds,
        status="awaiting_result",
        created_at=datetime.now(timezone.utc).isoformat(),
        backup_profile="_bisect_backup",
        pid=os.getpid(),
    )
    save_state(state, zdir)
    return state


def bisect_report_crash(
    zomboid_dir: Path | None = None,
    mod_dirs: list[Path] | None = None,
    auto_diagnose: bool = False,
) -> BisectState:
    """Report that PZ crashed with the current test set.

    The culprit is among the currently enabled mods (minus known_good).
    Narrows suspects to that intersection, then splits for the next round.

    Args:
        zomboid_dir: Zomboid user directory.
        mod_dirs: Mod directories for dependency group building.
        auto_diagnose: If True, attempt to shortcut via console.txt parsing.

    Raises:
        RuntimeError: If no active bisect session.
    """
    zdir = zomboid_dir or get_zomboid_dir()
    state = _load_and_validate(zdir)

    # Diagnose shortcut — try to identify culprit from logs
    if auto_diagnose:
        culprit = _try_diagnose_shortcut(state, zdir, mod_dirs)
        if culprit:
            return _complete_bisect(state, culprit, zdir)

    # Culprit is among currently enabled mods that are still suspects
    good_set = set(state.known_good)
    bad_set = set(state.known_bad)
    enabled_set = set(state.current_enabled)

    new_suspects = [
        m for m in state.current_enabled
        if m not in good_set and m not in bad_set
    ]

    # Everything that was a suspect but NOT enabled is now known good
    newly_good = [
        m for m in state.suspects
        if m not in enabled_set and m not in good_set
    ]
    state.known_good.extend(newly_good)
    state.suspects = new_suspects

    # Terminal conditions
    if len(state.suspects) == 0:
        return _mark_inconclusive(
            state, zdir, "No suspects remaining after crash report.",
        )
    if len(state.suspects) == 1:
        return _complete_bisect(state, state.suspects[0], zdir)

    # Guard against exceeding max rounds
    if state.round_number >= state.max_rounds + 5:
        return _mark_inconclusive(
            state, zdir,
            f"Exceeded {state.max_rounds + 5} rounds. "
            "Possible intermittent crash or multi-mod interaction.",
        )

    return _next_round(state, zdir, mod_dirs)


def bisect_report_ok(
    zomboid_dir: Path | None = None,
    mod_dirs: list[Path] | None = None,
) -> BisectState:
    """Report that PZ loaded OK with the current test set.

    The culprit is NOT among the currently enabled mods. Moves enabled
    mods to known_good and narrows suspects.

    Args:
        zomboid_dir: Zomboid user directory.
        mod_dirs: Mod directories for dependency group building.

    Raises:
        RuntimeError: If no active bisect session.
    """
    zdir = zomboid_dir or get_zomboid_dir()
    state = _load_and_validate(zdir)

    # Mods that were enabled and didn't crash are good
    good_set = set(state.known_good)
    bad_set = set(state.known_bad)
    newly_good = [
        m for m in state.current_enabled
        if m not in good_set and m not in bad_set
    ]
    state.known_good.extend(newly_good)

    # Remove known_good from suspects
    updated_good_set = set(state.known_good)
    state.suspects = [m for m in state.suspects if m not in updated_good_set]

    # Terminal conditions
    if len(state.suspects) == 0:
        return _mark_inconclusive(
            state, zdir,
            "No suspects remaining. "
            "Crash may be intermittent or environmental.",
        )
    if len(state.suspects) == 1:
        return _complete_bisect(state, state.suspects[0], zdir)

    # Guard against exceeding max rounds
    if state.round_number >= state.max_rounds + 5:
        return _mark_inconclusive(
            state, zdir,
            f"Exceeded {state.max_rounds + 5} rounds. "
            "Possible intermittent crash or multi-mod interaction.",
        )

    return _next_round(state, zdir, mod_dirs)


def bisect_abort(zomboid_dir: Path | None = None) -> None:
    """Abort bisect session and restore the original mod list.

    Restores from the backup profile first, falling back to
    original_mods stored in state if the profile is missing.
    Safe to call even with no active session (no-op).
    """
    zdir = zomboid_dir or get_zomboid_dir()
    state = load_state(zdir)

    if state is not None:
        # Try restoring from backup profile
        if state.backup_profile:
            try:
                load_profile(state.backup_profile, zomboid_dir=zdir)
            except KeyError:
                # Backup profile missing — fall back to state data
                if state.original_mods:
                    mod_list = ModList(
                        mods=state.original_mods,
                        maps=state.maps,
                        version=state.mod_list_version,
                    )
                    write_mod_list(mod_list, get_default_txt_path(zdir))
        elif state.original_mods:
            mod_list = ModList(
                mods=state.original_mods,
                maps=state.maps,
                version=state.mod_list_version,
            )
            write_mod_list(mod_list, get_default_txt_path(zdir))

    # Delete state file
    state_path = _get_state_path(zdir)
    if state_path.is_file():
        state_path.unlink()

    print("Bisect aborted. Original mod list restored.", file=sys.stderr)


def bisect_status(zomboid_dir: Path | None = None) -> BisectState | None:
    """Get current bisect status. Returns None if no session exists."""
    return load_state(zomboid_dir)
