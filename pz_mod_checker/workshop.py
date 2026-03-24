"""Steam Workshop API module for enriching scan results with update metadata."""

from __future__ import annotations

import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .scanner.mod_info import ModInfo


_API_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
_BATCH_SIZE = 50  # Conservative batch size
_TIMEOUT_SECONDS = 15
_MAX_RETRIES = 2
_RETRY_DELAY = 2.0
_CACHE_TTL_HOURS = 24
_B42_RELEASE_EPOCH = 1730419200  # 2024-11-01 00:00:00 UTC


@dataclass
class WorkshopMetadata:
    """Parsed metadata for a Workshop item."""

    file_id: str
    title: str
    time_updated: int  # Unix epoch
    tags: list[str] = field(default_factory=list)
    file_size: int = 0
    description_snippet: str = ""  # First 200 chars
    result: int = 1  # Steam API result code (1 = success)


@dataclass
class Suggestion:
    """A workshop-derived suggestion for a mod.

    Suggestions are advisory — they enrich scan results, not replace them.
    Kept separate from Finding to avoid conflating code analysis with metadata hints.
    """

    mod_id: str
    mod_name: str
    workshop_id: str
    reason: str       # "not_updated_since_b42", "claims_b42_support", "updated_post_b42", "api_error"
    confidence: str   # "high", "medium", "low"
    detail: str       # Human-readable explanation
    last_updated: str  # ISO date string or "unknown"
    action: str       # "investigate", "likely_ok", "no_data"


# ---------------------------------------------------------------------------
# Workshop ID extraction
# ---------------------------------------------------------------------------

def extract_workshop_id(mod: ModInfo) -> str | None:
    """Extract Steam Workshop ID from a mod's filesystem path.

    Workshop mods live under: steamapps/workshop/content/108600/<workshop_id>/
    The mod directory may be directly under <workshop_id>/ or under
    <workshop_id>/mods/<ModName>/.
    """
    parts = mod.path.parts
    for i, part in enumerate(parts):
        if part == "108600" and i + 1 < len(parts) and parts[i + 1].isdigit():
            return parts[i + 1]
    return None


# ---------------------------------------------------------------------------
# API communication
# ---------------------------------------------------------------------------

def get_workshop_details(
    file_ids: list[str],
    timeout: int = _TIMEOUT_SECONDS,
) -> list[WorkshopMetadata]:
    """Query Steam Workshop API for mod metadata.

    Handles batching for large ID lists. Returns metadata for every ID that
    the API responded to (check result field for per-item success).
    """
    results: list[WorkshopMetadata] = []

    for batch_start in range(0, len(file_ids), _BATCH_SIZE):
        batch = file_ids[batch_start:batch_start + _BATCH_SIZE]
        batch_results = _fetch_batch(batch, timeout)
        results.extend(batch_results)

    return results


def _fetch_batch(file_ids: list[str], timeout: int) -> list[WorkshopMetadata]:
    """Fetch a single batch of Workshop details with retry logic."""
    data = f"itemcount={len(file_ids)}"
    for i, fid in enumerate(file_ids):
        data += f"&publishedfileids[{i}]={fid}"

    for attempt in range(_MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(_API_URL, data=data.encode(), method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(10 * 1024 * 1024)  # 10 MB cap
                parsed = json.loads(body)
                return _parse_response(parsed)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
            print(
                f"Warning: Steam API error {e.code} for batch starting at {file_ids[0]}",
                file=sys.stderr,
            )
            return []
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY)
                continue
            print(f"Warning: Could not reach Steam API: {e}", file=sys.stderr)
            return []
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Invalid response from Steam API: {e}", file=sys.stderr)
            return []

    return []


def _parse_response(data: dict) -> list[WorkshopMetadata]:
    """Parse API JSON response into WorkshopMetadata list.

    Defensively validates every field — the Steam API is not strongly typed.
    """
    details = data.get("response", {}).get("publishedfiledetails", [])
    if not isinstance(details, list):
        return []

    results: list[WorkshopMetadata] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        try:
            result_code = int(item.get("result", -1))
            desc = str(item.get("description", ""))
            raw_tags = item.get("tags", [])
            tags = (
                [str(t.get("tag", "")) for t in raw_tags[:50] if isinstance(t, dict)]
                if isinstance(raw_tags, list)
                else []
            )
            results.append(WorkshopMetadata(
                file_id=str(item.get("publishedfileid", "")),
                title=str(item.get("title", ""))[:500],
                time_updated=int(item.get("time_updated", 0)),
                tags=tags,
                file_size=int(item.get("file_size", 0)),
                description_snippet=desc[:200],
                result=result_code,
            ))
        except (TypeError, ValueError):
            continue

    return results


# ---------------------------------------------------------------------------
# Local JSON cache
# ---------------------------------------------------------------------------

def _get_cache_dir() -> Path:
    """Return platform-appropriate cache directory, creating it if needed."""
    system = platform.system()
    match system:
        case "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        case "Darwin":
            base = Path.home() / "Library" / "Caches"
        case _:
            base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

    cache_dir = base / "pz-mod-checker"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cache_path() -> Path:
    """Return path to the workshop cache file."""
    return _get_cache_dir() / "workshop_cache.json"


def load_cache() -> dict[str, WorkshopMetadata]:
    """Load cached Workshop metadata. Returns empty dict if no cache or expired."""
    cache_path = _get_cache_path()
    if not cache_path.is_file():
        return {}

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict) or data.get("version") != 1:
        return {}

    fetched_at = data.get("fetched_at", 0)
    if not isinstance(fetched_at, (int, float)):
        return {}

    ttl_seconds = data.get("ttl_hours", _CACHE_TTL_HOURS) * 3600
    if time.time() - fetched_at > ttl_seconds:
        return {}  # Expired

    raw_entries = data.get("entries", {})
    if not isinstance(raw_entries, dict):
        return {}

    entries: dict[str, WorkshopMetadata] = {}
    for fid, meta in raw_entries.items():
        if not isinstance(meta, dict):
            continue
        try:
            entries[str(fid)] = WorkshopMetadata(
                file_id=str(fid),
                title=str(meta.get("title", "")),
                time_updated=int(meta.get("time_updated", 0)),
                tags=list(meta.get("tags", [])),
                file_size=int(meta.get("file_size", 0)),
                description_snippet=str(meta.get("description_snippet", "")),
                result=int(meta.get("result", 1)),
            )
        except (TypeError, ValueError):
            continue

    return entries


def save_cache(entries: dict[str, WorkshopMetadata]) -> None:
    """Save Workshop metadata to local JSON cache."""
    data = {
        "version": 1,
        "fetched_at": int(time.time()),
        "ttl_hours": _CACHE_TTL_HOURS,
        "entries": {
            fid: {
                "title": meta.title,
                "time_updated": meta.time_updated,
                "tags": meta.tags,
                "file_size": meta.file_size,
                "description_snippet": meta.description_snippet,
                "result": meta.result,
            }
            for fid, meta in entries.items()
        },
    }
    try:
        cache_path = _get_cache_path()
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"Warning: Could not write workshop cache: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def _classify_mod(
    mod: ModInfo,
    meta: WorkshopMetadata,
    workshop_id: str,
) -> Suggestion:
    """Classify a single mod based on Workshop metadata."""
    last_updated_str = datetime.fromtimestamp(
        meta.time_updated, tz=timezone.utc,
    ).strftime("%Y-%m-%d")
    updated_since_b42 = meta.time_updated > _B42_RELEASE_EPOCH

    # Check for B42 keywords in tags and description
    b42_tags = any("42" in tag.lower() or "b42" in tag.lower() for tag in meta.tags)
    b42_in_desc = (
        "build 42" in meta.description_snippet.lower()
        or "b42" in meta.description_snippet.lower()
    )
    claims_b42 = b42_tags or b42_in_desc

    if updated_since_b42 and claims_b42:
        return Suggestion(
            mod_id=mod.mod_id,
            mod_name=mod.name,
            workshop_id=workshop_id,
            reason="claims_b42_support",
            confidence="high",
            detail=f"Updated {last_updated_str}, claims B42 support",
            last_updated=last_updated_str,
            action="likely_ok",
        )
    elif updated_since_b42:
        return Suggestion(
            mod_id=mod.mod_id,
            mod_name=mod.name,
            workshop_id=workshop_id,
            reason="updated_post_b42",
            confidence="medium",
            detail=f"Updated {last_updated_str} (after B42 release), no B42 tags",
            last_updated=last_updated_str,
            action="likely_ok",
        )
    else:
        return Suggestion(
            mod_id=mod.mod_id,
            mod_name=mod.name,
            workshop_id=workshop_id,
            reason="not_updated_since_b42",
            confidence="medium",
            detail=f"Last updated {last_updated_str} (before B42 release)",
            last_updated=last_updated_str,
            action="investigate",
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def check_workshop_updates(
    mods: list[ModInfo],
    use_cache: bool = True,
    timeout: int = _TIMEOUT_SECONDS,
) -> tuple[list[Suggestion], dict[str, WorkshopMetadata]]:
    """Check Workshop for mod update status.

    Returns a tuple of (suggestions, metadata_by_workshop_id).
    Suggestions are advisory — they enrich scan results, not replace them.
    """
    # 1. Extract workshop IDs, deduplicate
    id_to_mods: dict[str, list[ModInfo]] = {}
    skipped = 0
    for mod in mods:
        wid = extract_workshop_id(mod)
        if wid:
            id_to_mods.setdefault(wid, []).append(mod)
        else:
            skipped += 1

    if not id_to_mods:
        print(
            f"Workshop check: no Workshop mods found ({skipped} local mods skipped).",
            file=sys.stderr,
        )
        return [], {}

    # 2. Load cache, find IDs needing fresh fetch
    all_metadata: dict[str, WorkshopMetadata] = {}
    ids_to_fetch: list[str] = list(id_to_mods.keys())

    if use_cache:
        cached = load_cache()
        for wid in list(ids_to_fetch):
            if wid in cached:
                all_metadata[wid] = cached[wid]
                ids_to_fetch.remove(wid)

    # 3. Fetch remaining from API
    if ids_to_fetch:
        print(
            f"Querying Steam Workshop for {len(ids_to_fetch)} mods...",
            file=sys.stderr,
        )
        fetched = get_workshop_details(ids_to_fetch, timeout)
        for meta in fetched:
            all_metadata[meta.file_id] = meta

        # Update cache with all data (cached + fresh)
        if use_cache:
            save_cache(all_metadata)

    # 4. Generate suggestions
    suggestions: list[Suggestion] = []
    api_errors = 0

    for wid, mod_list in id_to_mods.items():
        meta = all_metadata.get(wid)
        if meta is None or meta.result != 1:
            api_errors += 1
            for mod in mod_list:
                suggestions.append(Suggestion(
                    mod_id=mod.mod_id,
                    mod_name=mod.name,
                    workshop_id=wid,
                    reason="api_error",
                    confidence="low",
                    detail="Could not retrieve Workshop data (deleted, private, or API error)",
                    last_updated="unknown",
                    action="no_data",
                ))
            continue

        for mod in mod_list:
            suggestions.append(_classify_mod(mod, meta, wid))

    # 5. Summary
    checked = len(id_to_mods)
    total = len(mods)
    print(
        f"Workshop check: {checked} of {total} mods checked "
        f"({skipped} local, {api_errors} API errors).",
        file=sys.stderr,
    )

    return suggestions, all_metadata
