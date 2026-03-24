"""Localhost web server for PZ Mod Checker GUI."""

from __future__ import annotations

import json
import sys
import traceback
import webbrowser
from dataclasses import asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from threading import Timer
from urllib.parse import urlparse, parse_qs

_STATIC_DIR = Path(__file__).parent / "static"
_PORT = 8642
_MAX_BODY = 1_048_576  # 1 MB


def _get_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data"


# Cache for discover_mods() — avoids redundant filesystem traversals
_mod_cache: dict = {"mtime": 0.0, "mods": []}


def _cached_discover_mods() -> list:
    """Return discovered mods, cached with mtime-based invalidation."""
    from ..scanner.discovery import discover_mods, get_default_mod_paths

    # Check newest mtime across all mod directories
    newest = 0.0
    for d in get_default_mod_paths():
        if d.is_dir():
            try:
                newest = max(newest, d.stat().st_mtime)
            except OSError:
                pass

    if newest != _mod_cache["mtime"] or not _mod_cache["mods"]:
        _mod_cache["mods"] = discover_mods()
        _mod_cache["mtime"] = newest

    return _mod_cache["mods"]


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class PZModCheckerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the PZ Mod Checker GUI."""

    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode("utf-8"))

    def _send_static(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        suffix = path.suffix.lower()
        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        ct = content_types.get(suffix, "application/octet-stream")
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def _read_body(self) -> dict | None:
        """Read and parse JSON body. Returns None on error (response already sent)."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        if length > _MAX_BODY:
            self._send_json({"error": "Request body too large"}, 413)
            return None
        body = self.rfile.read(length)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, 400)
            return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._send_static(_STATIC_DIR / "index.html")
            return

        try:
            if path == "/api/scan":
                self._handle_scan(params)
            elif path == "/api/diagnose":
                self._handle_diagnose()
            elif path == "/api/mods":
                self._handle_mods()
            elif path == "/api/profiles":
                self._handle_profiles()
            elif path == "/api/bisect/status":
                self._handle_bisect_status()
            elif path == "/api/version":
                self._handle_version()
            elif path == "/api/versions":
                self._handle_versions()
            elif path == "/api/docs":
                self._handle_docs()
            elif path == "/api/workshop/check":
                self._handle_workshop_check()
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        if body is None:
            return  # error already sent

        try:
            if path == "/api/mods/enable":
                self._handle_mods_enable(body)
            elif path == "/api/mods/disable":
                self._handle_mods_disable(body)
            elif path == "/api/mods/disable-breaking":
                self._handle_disable_breaking()
            elif path == "/api/mods/disable-scan-breaking":
                self._handle_disable_scan_breaking(body)
            elif path == "/api/profile/save":
                self._handle_profile_save(body)
            elif path == "/api/profile/load":
                self._handle_profile_load(body)
            elif path == "/api/mods/delete":
                self._handle_mods_delete(body)
            elif path == "/api/bisect/start":
                self._handle_bisect_start()
            elif path == "/api/bisect/crash":
                self._handle_bisect_crash()
            elif path == "/api/bisect/ok":
                self._handle_bisect_ok()
            elif path == "/api/bisect/abort":
                self._handle_bisect_abort()
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # --- API Handlers ---

    # Cache for console.txt parsing (avoid re-parsing MBs on every refreshHeader)
    _console_cache: dict = {"mtime": 0, "pz_version": "unknown", "session_date": ""}

    def _get_console_info(self) -> tuple[str, str]:
        from ..diagnose import get_console_log, parse_console_log
        try:
            log_path = get_console_log()
            if not log_path.is_file():
                return "unknown", ""
            mtime = log_path.stat().st_mtime
            cache = PZModCheckerHandler._console_cache
            if mtime != cache["mtime"]:
                diagnosis = parse_console_log(log_path)
                cache["mtime"] = mtime
                cache["pz_version"] = diagnosis.pz_version or "unknown"
                cache["session_date"] = diagnosis.session_start
            return cache["pz_version"], cache["session_date"]
        except Exception:
            return "unknown", ""

    def _handle_version(self) -> None:
        from .. import __version__
        from ..manager import get_mod_status
        pz_version, session_date = self._get_console_info()

        active_mods = 0
        total_mods = 0
        try:
            statuses = get_mod_status()
            total_mods = len(statuses)
            active_mods = sum(1 for m in statuses if m["enabled"])
        except Exception:
            pass

        self._send_json({
            "tool_version": __version__,
            "pz_version": pz_version,
            "last_session": session_date,
            "active_mods": active_mods,
            "total_mods": total_mods,
        })

    def _handle_versions(self) -> None:
        """Return available PZ versions from rule files, newest first."""
        from ..rules.version import PZVersion

        rules_dir = _get_data_dir() / "rules"
        versions = []
        if rules_dir.is_dir():
            for f in rules_dir.glob("*.json"):
                versions.append(f.stem)
        versions.sort(key=lambda v: PZVersion.parse(v), reverse=True)
        self._send_json({"versions": versions})

    def _handle_docs(self) -> None:
        """Serve the local user guide markdown."""
        docs_path = Path(__file__).resolve().parent.parent.parent / "docs" / "user-guide.md"
        if not docs_path.is_file():
            self._send_json({"error": "User guide not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.end_headers()
        self.wfile.write(docs_path.read_bytes())

    def _handle_workshop_check(self) -> None:
        """Check Workshop for mod update status."""
        from ..workshop import check_workshop_updates, extract_workshop_id

        mods = _cached_discover_mods()
        suggestions, metadata = check_workshop_updates(mods)

        # Build response keyed by mod_id for easy client-side lookup
        by_mod: dict[str, dict] = {}
        for s in suggestions:
            by_mod[s.mod_id] = {
                "reason": s.reason,
                "confidence": s.confidence,
                "detail": s.detail,
                "last_updated": s.last_updated,
                "action": s.action,
                "workshop_id": s.workshop_id,
            }

        # Also compute local file age for comparison
        for mod in mods:
            wid = extract_workshop_id(mod)
            if not wid or mod.mod_id not in by_mod:
                continue
            meta = metadata.get(wid)
            if meta and meta.time_updated > 0:
                # Check if local mod files are older than Workshop update
                try:
                    local_mtime = mod.path.stat().st_mtime
                    by_mod[mod.mod_id]["workshop_updated"] = meta.time_updated
                    by_mod[mod.mod_id]["local_mtime"] = int(local_mtime)
                    by_mod[mod.mod_id]["has_update"] = meta.time_updated > local_mtime
                except OSError:
                    pass

        self._send_json({
            "total_checked": len(by_mod),
            "total_with_updates": sum(1 for v in by_mod.values() if v.get("has_update")),
            "total_stale": sum(1 for v in by_mod.values() if v.get("reason") == "not_updated_since_b42"),
            "mods": by_mod,
        })

    def _handle_scan(self, params: dict) -> None:
        from ..manager import read_mod_list
        from ..rules.engine import check_all_mods
        from ..rules.loader import load_ruleset
        from ..rules.version import PZVersion

        version = params.get("version", ["42.15.3"])[0]
        scope = params.get("scope", ["active"])[0]  # active, all, or profile name
        target = PZVersion.parse(version)

        ruleset = load_ruleset(_get_data_dir())
        all_mods = _cached_discover_mods()

        if scope == "all":
            mods = all_mods
        elif scope == "active":
            try:
                mod_list = read_mod_list()
                active_ids = set(mod_list.mods)
                mods = [m for m in all_mods if m.mod_id in active_ids]
            except Exception:
                mods = all_mods
        else:
            # Scope is a profile name
            try:
                from ..manager import list_profiles
                profiles = {p.name: set(p.mod_ids) for p in list_profiles()}
                profile_ids = profiles.get(scope, set())
                mods = [m for m in all_mods if m.mod_id in profile_ids] if profile_ids else all_mods
            except Exception:
                mods = all_mods

        if not mods:
            self._send_json({"total_mods": 0, "total_findings": 0, "mods": {}})
            return

        results = check_all_mods(mods, ruleset, target)

        output = {
            "total_mods": len(mods),
            "total_mods_with_issues": len(results),
            "total_findings": sum(len(f) for f in results.values()),
            "summary": {
                "breaking": sum(
                    1 for fs in results.values() for f in fs if f.severity == "breaking"
                ),
                "warning": sum(
                    1 for fs in results.values() for f in fs if f.severity == "warning"
                ),
                "info": sum(
                    1 for fs in results.values() for f in fs if f.severity == "info"
                ),
            },
            "mods": {
                mod_id: [asdict(f) for f in findings]
                for mod_id, findings in sorted(results.items())
            },
        }
        self._send_json(output)

    def _handle_diagnose(self) -> None:
        from ..diagnose import (
            build_name_to_id_map,
            get_console_log,
            parse_console_log,
            resolve_mod_names,
        )

        log_path = get_console_log()
        if not log_path.is_file():
            self._send_json({"error": "console.txt not found"}, 404)
            return

        diagnosis = parse_console_log(log_path)
        name_to_id = build_name_to_id_map()
        resolve_mod_names(diagnosis, name_to_id)
        self._send_json(asdict(diagnosis))

    def _handle_mods(self) -> None:
        from ..manager import get_mod_status
        statuses = get_mod_status()
        self._send_json({"mods": statuses})

    def _handle_mods_enable(self, body: dict) -> None:
        from ..manager import enable_mods
        mod_ids = body.get("mod_ids", [])
        if not mod_ids:
            self._send_json({"error": "mod_ids required"}, 400)
            return
        mod_list = enable_mods(mod_ids)
        self._send_json({"total_active": len(mod_list.mods), "enabled": mod_ids})

    def _handle_mods_disable(self, body: dict) -> None:
        from ..manager import disable_mods
        mod_ids = body.get("mod_ids", [])
        if not mod_ids:
            self._send_json({"error": "mod_ids required"}, 400)
            return
        mod_list = disable_mods(mod_ids)
        self._send_json({"total_active": len(mod_list.mods), "disabled": mod_ids})

    def _handle_disable_breaking(self) -> None:
        from ..diagnose import (
            build_name_to_id_map,
            get_console_log,
            parse_console_log,
            resolve_mod_names,
        )
        from ..manager import disable_mods

        log_path = get_console_log()
        if not log_path.is_file():
            self._send_json({"error": "console.txt not found"}, 404)
            return

        diagnosis = parse_console_log(log_path)
        name_to_id = build_name_to_id_map()
        resolve_mod_names(diagnosis, name_to_id)

        to_disable = list({e.mod_id for e in diagnosis.mod_errors if e.mod_id})
        if not to_disable:
            self._send_json({"message": "No breaking mods found", "disabled": []})
            return

        mod_list = disable_mods(to_disable)
        self._send_json({"total_active": len(mod_list.mods), "disabled": to_disable})

    def _handle_disable_scan_breaking(self, body: dict) -> None:
        """Disable mods with breaking scan findings."""
        from ..manager import disable_mods
        mod_ids = body.get("mod_ids", [])
        if not mod_ids:
            self._send_json({"error": "mod_ids required"}, 400)
            return
        mod_list = disable_mods(mod_ids)
        self._send_json({"total_active": len(mod_list.mods), "disabled": mod_ids})

    def _handle_mods_delete(self, body: dict) -> None:
        """Delete a mod's folder from disk."""
        from ..manager import delete_mod
        mod_id = body.get("mod_id", "")
        if not mod_id:
            self._send_json({"error": "mod_id required"}, 400)
            return
        try:
            deleted_path = delete_mod(mod_id)
            if deleted_path:
                self._send_json({"deleted": mod_id, "path": str(deleted_path)})
            else:
                self._send_json({"error": f"Mod not found: {mod_id}"}, 404)
        except PermissionError as e:
            self._send_json({"error": f"Cannot delete: {e}"}, 403)

    def _handle_profiles(self) -> None:
        from ..manager import list_profiles
        profiles = list_profiles()
        self._send_json({
            "profiles": [
                {"name": p.name, "mod_count": len(p.mod_ids), "mod_ids": p.mod_ids}
                for p in profiles
            ]
        })

    def _handle_profile_save(self, body: dict) -> None:
        from ..manager import save_profile
        name = body.get("name", "")
        if not name:
            self._send_json({"error": "name required"}, 400)
            return
        save_profile(name)
        self._send_json({"saved": name})

    def _handle_profile_load(self, body: dict) -> None:
        from ..manager import load_profile
        name = body.get("name", "")
        if not name:
            self._send_json({"error": "name required"}, 400)
            return
        try:
            mod_list = load_profile(name)
            self._send_json({"loaded": name, "total_active": len(mod_list.mods)})
        except KeyError:
            self._send_json({"error": f"Profile '{name}' not found"}, 404)

    def _handle_bisect_status(self) -> None:
        from ..bisect import bisect_status
        state = bisect_status()
        if state is None:
            self._send_json({"active": False})
            return
        self._send_json({"active": True, **asdict(state)})

    def _handle_bisect_start(self) -> None:
        from ..bisect import bisect_start
        try:
            state = bisect_start()
            self._send_json(asdict(state))
        except RuntimeError as e:
            self._send_json({"error": str(e)}, 400)

    def _handle_bisect_crash(self) -> None:
        from ..bisect import bisect_report_crash
        try:
            state = bisect_report_crash(auto_diagnose=True)
            self._send_json(asdict(state))
        except RuntimeError as e:
            self._send_json({"error": str(e)}, 400)

    def _handle_bisect_ok(self) -> None:
        from ..bisect import bisect_report_ok
        try:
            state = bisect_report_ok()
            self._send_json(asdict(state))
        except RuntimeError as e:
            self._send_json({"error": str(e)}, 400)

    def _handle_bisect_abort(self) -> None:
        from ..bisect import bisect_abort
        bisect_abort()
        self._send_json({"aborted": True})


def start_server(port: int = _PORT, open_browser: bool = True) -> None:
    """Start the GUI server."""
    server = ThreadingHTTPServer(("127.0.0.1", port), PZModCheckerHandler)
    url = f"http://localhost:{port}"
    print(f"PZ Mod Checker GUI running at {url}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
