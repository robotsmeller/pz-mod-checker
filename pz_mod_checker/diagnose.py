"""Parse Project Zomboid console.txt logs and diagnose mod errors."""

from __future__ import annotations

import platform
import re
from dataclasses import dataclass, field
from pathlib import Path

from .scanner.discovery import discover_mods
from .scanner.mod_info import ModInfo


# ---------------------------------------------------------------------------
# Regex patterns for log parsing
# ---------------------------------------------------------------------------

# First line: session timestamp
_SESSION_START_RE = re.compile(r"t:(\d+)>\s+(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})")

# PZ version string — must start at beginning or after "> " to avoid java.specification.version etc.
_VERSION_RE = re.compile(r">\s*version=(\d+\.\d+\.\d+)\s")

# Mod loading line: LOG  : Mod   f:0, t:NNNNN> loading <mod_id>
# Mod IDs can contain spaces, brackets, slashes — capture everything after "loading "
_MOD_LOAD_RE = re.compile(r":\s*Mod\s+.*>\s*loading\s+(.+)$")

# Texturepack loading (used to detect first vs second load phase)
_TEXTUREPACK_RE = re.compile(r"texturepack:\s*loading", re.IGNORECASE)

# Error message from KahluaThread
_ERROR_MSG_RE = re.compile(
    r"(ERROR|SEVERE)\s*:\s*General\s+.*KahluaThread\.flushErrorMessage\s*>\s*(.*)"
)

# Stack trace delimiter
_STACK_TRACE_DELIM = "STACK TRACE"
_STACK_SEPARATOR = "-" * 10  # At least 10 dashes

# Stack frame with MOD attribution
_FRAME_RE = re.compile(
    r"function:\s+(.+?)\s+--\s+file:\s+(\S+)\s+line\s+#\s+(\d+)\s+\|\s+MOD:\s+(.+)"
)

# Require failure
_REQUIRE_FAIL_RE = re.compile(
    r"WARN\s*:\s*Lua\s+.*require\(\"([^\"]+)\"\)\s+failed"
)

# Timestamp extraction from any log line
_TIMESTAMP_RE = re.compile(r"t:(\d+)>")

# Java exception
_JAVA_EXCEPTION_RE = re.compile(
    r"(ERROR|SEVERE)\s*:.*ExceptionLogger\.logException\s*>\s*Exception\s+thrown"
)

# Severe runtime error
_SEVERE_RE = re.compile(r"SEVERE:\s+(.*)")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StackFrame:
    """A single frame in a Lua stack trace."""

    function_name: str
    file_name: str
    line_number: int
    mod_name: str  # Display name from | MOD: xxx


@dataclass
class ModError:
    """An error attributed to a specific mod."""

    mod_name: str        # Display name (from stack trace)
    mod_id: str | None   # Resolved mod ID (from mod.info lookup)
    error_message: str
    stack_frames: list[StackFrame] = field(default_factory=list)
    severity: str = "error"  # error, severe, warning
    timestamp_ms: int = 0


@dataclass
class RequireFailure:
    """A failed require() call."""

    module_path: str     # e.g., "ISUI/ISInventoryPaneContextMenu"
    timestamp_ms: int = 0


@dataclass
class SessionDiagnosis:
    """Complete diagnosis of a PZ session from logs."""

    session_start: str   # Human-readable timestamp
    pz_version: str
    mods_loaded: list[str]  # Mod IDs in load order
    mod_errors: list[ModError] = field(default_factory=list)
    require_failures: list[RequireFailure] = field(default_factory=list)
    error_count_by_mod: dict[str, int] = field(default_factory=dict)  # mod_name -> count


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def get_zomboid_dir() -> Path:
    """Return the Zomboid user directory for the current platform."""
    # All platforms use ~/Zomboid
    return Path.home() / "Zomboid"


def get_console_log(zomboid_dir: Path | None = None) -> Path:
    """Return path to console.txt."""
    if zomboid_dir is None:
        zomboid_dir = get_zomboid_dir()
    return zomboid_dir / "console.txt"


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _extract_timestamp(line: str) -> int:
    """Extract timestamp_ms from a log line, or 0 if not found."""
    m = _TIMESTAMP_RE.search(line)
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# Log parser
# ---------------------------------------------------------------------------

def parse_console_log(log_path: Path) -> SessionDiagnosis:
    """Parse a PZ console.txt and extract mod errors.

    Args:
        log_path: Path to the console.txt file.

    Returns:
        SessionDiagnosis with all extracted information.

    Raises:
        FileNotFoundError: If log_path does not exist.
    """
    if not log_path.is_file():
        raise FileNotFoundError(f"Console log not found: {log_path}")

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise FileNotFoundError(f"Cannot read console log: {e}") from e

    lines = text.splitlines()
    if not lines:
        return SessionDiagnosis(session_start="", pz_version="", mods_loaded=[])

    # 1. Session start from first line
    session_start = ""
    m = _SESSION_START_RE.search(lines[0])
    if m:
        session_start = m.group(2)

    # 2. PZ version — scan until found
    pz_version = ""
    for line in lines:
        m = _VERSION_RE.search(line)
        if m:
            pz_version = m.group(1)
            break

    # 3. Mod load order — multi-phase detection
    #    PZ loads mods in multiple phases. The main mod loading phase is the
    #    largest cluster of "loading" lines. We detect clusters by looking for
    #    gaps of 200+ lines between loading lines, then pick the biggest cluster.
    all_mod_loads: list[tuple[int, str]] = []  # (line_index, mod_id)

    for i, line in enumerate(lines):
        m = _MOD_LOAD_RE.search(line)
        if m:
            all_mod_loads.append((i, m.group(1).strip()))

    # Split into clusters based on large gaps between load lines
    _CLUSTER_GAP = 200  # Lines between clusters
    clusters: list[list[tuple[int, str]]] = []
    current_cluster: list[tuple[int, str]] = []
    for load in all_mod_loads:
        if current_cluster and load[0] - current_cluster[-1][0] > _CLUSTER_GAP:
            clusters.append(current_cluster)
            current_cluster = []
        current_cluster.append(load)
    if current_cluster:
        clusters.append(current_cluster)

    # The main loading phase is the largest cluster
    if clusters:
        main_cluster = max(clusters, key=len)
        mods_loaded = [mod_id for _, mod_id in main_cluster]
    else:
        mods_loaded = []

    # 4. Parse errors and stack traces
    mod_errors: list[ModError] = []
    require_failures: list[RequireFailure] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for require failures
        m = _REQUIRE_FAIL_RE.search(line)
        if m:
            require_failures.append(RequireFailure(
                module_path=m.group(1),
                timestamp_ms=_extract_timestamp(line),
            ))
            i += 1
            continue

        # Check for KahluaThread error messages
        m = _ERROR_MSG_RE.search(line)
        if m:
            severity_str = m.group(1).lower()
            error_msg = m.group(2).strip()

            # Skip the "dumping Lua stack trace" meta-message
            if "dumping Lua stack trace" in error_msg:
                # Look ahead for the actual stack trace
                frames = _parse_stack_trace(lines, i + 1)
                if frames:
                    # Find the most recent non-stack-trace error message
                    # by looking backwards from this line
                    real_msg = _find_preceding_error_message(lines, i)
                    mod_name = frames[0].mod_name
                    mod_errors.append(ModError(
                        mod_name=mod_name,
                        mod_id=None,
                        error_message=real_msg,
                        stack_frames=frames,
                        severity=_map_severity(severity_str),
                        timestamp_ms=_extract_timestamp(line),
                    ))
                i += 1
                continue

            # Standalone error message (not "dumping" — could be the actual
            # error text like "attempted index: unhideModel of non-table: null")
            # These get picked up by _find_preceding_error_message when
            # a stack trace follows. Skip standalone collection here to
            # avoid duplicates — they'll be captured when the stack dump line
            # appears.
            i += 1
            continue

        # Check for Java exceptions
        m = _JAVA_EXCEPTION_RE.search(line)
        if m:
            # Collect the exception text from following lines
            exception_lines: list[str] = []
            j = i + 1
            while j < len(lines) and (
                lines[j].startswith("\tat ")
                or lines[j].startswith("Caused by:")
                or lines[j].strip().startswith("at ")
                or (exception_lines and not lines[j].strip())
            ):
                exception_lines.append(lines[j].rstrip())
                j += 1
            # Java exceptions don't have MOD attribution — store as general
            if exception_lines:
                mod_errors.append(ModError(
                    mod_name="[Java]",
                    mod_id=None,
                    error_message="Java exception: " + (
                        exception_lines[0].strip() if exception_lines else "unknown"
                    ),
                    stack_frames=[],
                    severity="severe",
                    timestamp_ms=_extract_timestamp(line),
                ))
            i = j
            continue

        i += 1

    # 5. Build error_count_by_mod
    error_count_by_mod: dict[str, int] = {}
    for error in mod_errors:
        error_count_by_mod[error.mod_name] = (
            error_count_by_mod.get(error.mod_name, 0) + 1
        )

    return SessionDiagnosis(
        session_start=session_start,
        pz_version=pz_version,
        mods_loaded=mods_loaded,
        mod_errors=mod_errors,
        require_failures=require_failures,
        error_count_by_mod=error_count_by_mod,
    )


def _find_preceding_error_message(lines: list[str], dump_line_idx: int) -> str:
    """Look backwards from a 'dumping Lua stack trace' line to find the actual error.

    The real error message is typically 1-3 lines before the dump line,
    also from KahluaThread.flushErrorMessage but without 'dumping'.
    """
    search_start = max(0, dump_line_idx - 5)
    for i in range(dump_line_idx - 1, search_start - 1, -1):
        m = _ERROR_MSG_RE.search(lines[i])
        if m:
            msg = m.group(2).strip()
            if "dumping Lua stack trace" not in msg:
                return msg
    return "Unknown error"


def _parse_stack_trace(lines: list[str], start_idx: int) -> list[StackFrame]:
    """Parse a Lua stack trace starting near start_idx.

    Looks for the STACK TRACE delimiter and then parses frames.
    """
    frames: list[StackFrame] = []
    i = start_idx

    # Skip to the STACK TRACE header (may be preceded by separator dashes)
    found_header = False
    scan_limit = min(start_idx + 10, len(lines))
    while i < scan_limit:
        stripped = lines[i].strip()
        if _STACK_TRACE_DELIM in stripped:
            found_header = True
            i += 1
            break
        if stripped.startswith("-") and len(stripped) >= 10:
            # Separator line, skip
            i += 1
            continue
        i += 1

    if not found_header:
        return frames

    # Skip the closing separator after "STACK TRACE"
    if i < len(lines) and lines[i].strip().startswith("-"):
        i += 1

    # Parse frame lines until we hit a non-frame line
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        m = _FRAME_RE.match(line)
        if m:
            frames.append(StackFrame(
                function_name=m.group(1).strip(),
                file_name=m.group(2).strip(),
                line_number=int(m.group(3)),
                mod_name=m.group(4).strip(),
            ))
            i += 1
            continue

        # Stack frames can also be without MOD attribution — skip those
        if line.startswith("function:"):
            i += 1
            continue

        # End of stack trace (hit a separator or different line)
        if line.startswith("-") and len(line) >= 10:
            break
        # Any other content means end of stack trace
        break

    return frames


def _map_severity(level: str) -> str:
    """Map PZ log level to our severity."""
    match level:
        case "severe":
            return "severe"
        case "error":
            return "error"
        case "warn":
            return "warning"
        case _:
            return "error"


# ---------------------------------------------------------------------------
# Mod name resolution
# ---------------------------------------------------------------------------

def build_name_to_id_map(mod_dirs: list[Path] | None = None) -> dict[str, str]:
    """Build a mod display name -> mod ID mapping by reading all mod.info files.

    Args:
        mod_dirs: Directories to scan. Uses defaults if None.

    Returns:
        Dict mapping display name to mod ID.
    """
    mods = discover_mods(mod_dirs)
    return {mod.name: mod.mod_id for mod in mods}


def resolve_mod_names(
    diagnosis: SessionDiagnosis,
    name_to_id: dict[str, str],
) -> None:
    """Resolve mod display names to mod IDs using a name->id mapping.

    Mutates the diagnosis in place, setting mod_id on each ModError
    where the display name matches.
    """
    for error in diagnosis.mod_errors:
        if error.mod_name in name_to_id:
            error.mod_id = name_to_id[error.mod_name]


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def diagnose_last_session(
    zomboid_dir: Path | None = None,
    mod_dirs: list[Path] | None = None,
) -> SessionDiagnosis:
    """Full diagnosis: parse logs + resolve mod names.

    Args:
        zomboid_dir: Zomboid user directory (for console.txt).
        mod_dirs: Mod directories to scan for name resolution.

    Returns:
        SessionDiagnosis with resolved mod IDs where possible.

    Raises:
        FileNotFoundError: If console.txt does not exist.
    """
    log_path = get_console_log(zomboid_dir)
    if not log_path.is_file():
        raise FileNotFoundError(f"Console log not found: {log_path}")

    diagnosis = parse_console_log(log_path)

    # Resolve display names to mod IDs
    name_to_id = build_name_to_id_map(mod_dirs)
    resolve_mod_names(diagnosis, name_to_id)

    return diagnosis
