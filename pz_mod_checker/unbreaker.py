"""Unbreaker coverage data fetcher with local caching.

Fetches vanilla_globals.json from the Unbreaker GitHub repo to determine
which require() failures are covered by Unbreaker. Used by the diagnose
page to label each failure as fixable, unrecoverable, or unknown.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from .workshop import _get_cache_dir


_UNBREAKER_URL = "https://raw.githubusercontent.com/robotsmeller/unbreaker/main/data/vanilla_globals.json"
_CACHE_TTL_HOURS = 24
_TIMEOUT_SECONDS = 10


def _cache_path() -> Path:
    return _get_cache_dir() / "unbreaker_coverage.json"


def fetch_coverage(force: bool = False) -> dict:
    """Fetch Unbreaker's vanilla_globals.json with 24h cache.

    Returns the parsed JSON dict, or an empty stub if fetch and cache both fail.
    Result shape:
        {"version": "...", "redirects": [{"module": ..., "category": ..., "verified": ...}, ...]}
    """
    cache = _cache_path()

    if not force and cache.is_file():
        try:
            wrapped = json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(wrapped, dict):
                fetched_at = wrapped.get("fetched_at", 0)
                if isinstance(fetched_at, (int, float)) and (time.time() - fetched_at) < _CACHE_TTL_HOURS * 3600:
                    payload = wrapped.get("payload")
                    if isinstance(payload, dict):
                        return payload
        except (json.JSONDecodeError, OSError):
            pass

    try:
        req = urllib.request.Request(
            _UNBREAKER_URL,
            headers={"User-Agent": "pz-mod-checker"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Unexpected payload shape")
    except (urllib.error.URLError, json.JSONDecodeError, ValueError, OSError):
        if cache.is_file():
            try:
                wrapped = json.loads(cache.read_text(encoding="utf-8"))
                stale_payload = wrapped.get("payload")
                if isinstance(stale_payload, dict):
                    return stale_payload
            except (json.JSONDecodeError, OSError):
                pass
        return {"version": "unknown", "redirects": []}

    try:
        cache.write_text(
            json.dumps({"fetched_at": time.time(), "payload": payload}),
            encoding="utf-8",
        )
    except OSError:
        pass

    return payload


def coverage_lookup(coverage: dict) -> dict[str, dict]:
    """Build a {module_path: entry} index from a coverage payload."""
    out: dict[str, dict] = {}
    for entry in coverage.get("redirects", []):
        if not isinstance(entry, dict):
            continue
        module = entry.get("module")
        if isinstance(module, str):
            out[module] = entry
    return out


def classify(module: str, lookup: dict[str, dict]) -> str:
    """Classify a require() failure against Unbreaker coverage.

    Returns one of: "fixed", "unrecoverable", "unknown"
    """
    entry = lookup.get(module)
    if entry is None:
        return "unknown"
    if entry.get("category") == "unrecoverable":
        return "unrecoverable"
    if entry.get("verified") is True:
        return "fixed"
    return "unknown"
