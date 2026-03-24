# PZ Mod Checker

External compatibility scanner, crash diagnostics, and mod manager for **Project Zomboid Build 42**.

Scans your mods for known breaking changes, parses crash logs to identify culprits, and lets you enable/disable mods without launching the game. Zero dependencies — runs entirely on Python's standard library.

---

## Quick Start

```bash
# Install
pip install -e .

# Scan your mods against your PZ version
pz-mod-checker scan 42.15.3

# See what crashed last session
pz-mod-checker diagnose

# Find which mod is crashing PZ
pz-mod-checker bisect start

# Launch the web GUI
pz-mod-checker --gui
```

---

## Web GUI

Launch a local dashboard in your browser:

```bash
pz-mod-checker --gui
```

Opens `http://localhost:8642` with a full dashboard featuring:

- **Scan** — Run scans, browse results by mod, filter by severity
- **Diagnose** — One-click crash log analysis, disable erroring mods
- **Mods** — Toggle mods on/off, manage profiles, search/filter
- **Bisect** — Visual binary search walkthrough with progress tracking

All actions available in the GUI call the same API endpoints, which can also be used by other tools:

```
GET  /api/scan?version=42.15.3    # Scan results as JSON
GET  /api/diagnose                 # Last session diagnosis
GET  /api/mods                     # Mod list with status
POST /api/mods/enable              # Enable mods
POST /api/mods/disable             # Disable mods
POST /api/bisect/start             # Begin bisect
GET  /api/profiles                 # List profiles
```

---

## CLI Commands

### `scan` — Check mods for compatibility issues

Scans all installed mods against version-keyed rules covering B42.0 through B42.15.

```bash
pz-mod-checker scan 42.15.3                     # Scan all mods
pz-mod-checker scan 42.15.3 --verbose            # Show file paths and line numbers
pz-mod-checker scan 42.15.3 --severity breaking  # Only show breaking issues
pz-mod-checker scan 42.15.3 --format json        # Machine-readable output
pz-mod-checker scan 42.15.3 --check-workshop     # Include Steam Workshop metadata
pz-mod-checker scan 42.10.0                      # Scan against an older version
```

**Version targeting:** Rules are keyed by the PZ version that introduced each breaking change. Scanning against `42.10.0` applies 25 rules. Scanning against `42.15.3` applies all 51.

**Severity levels:**
- **BREAKING** — Will crash or fail to load
- **WARNING** — May malfunction, needs investigation
- **INFO** — Cosmetic or minor, likely still works

### `diagnose` — Parse crash logs

Reads your last PZ session's `console.txt` and identifies which mods caused errors.

```bash
pz-mod-checker diagnose                   # Parse last session
pz-mod-checker diagnose --auto-disable    # Parse + offer to disable culprits
pz-mod-checker diagnose --format json     # Machine-readable output
pz-mod-checker diagnose --log path/to/console.txt  # Specific log file
```

PZ logs Lua stack traces with `| MOD: <name>` attribution on every frame — this tool reads those to pinpoint exactly which mod caused each error.

### `manage` — Enable/disable mods

Reads and writes `~/Zomboid/mods/default.txt` to control which mods load on next PZ launch. Creates a backup before every change.

```bash
pz-mod-checker manage --list              # Show all mods with enabled/disabled status
pz-mod-checker manage --disable SpnCloth  # Disable a specific mod
pz-mod-checker manage --enable SpnCloth   # Re-enable it
pz-mod-checker manage --disable-breaking  # Disable all mods that crashed last session
pz-mod-checker manage --disable-all       # Disable everything (safe mode)
pz-mod-checker manage --enable-only ModA ModB ModC  # Enable ONLY these mods

# Profiles
pz-mod-checker manage --profile-save "Working"    # Save current mod list
pz-mod-checker manage --profile-load "Working"    # Restore a saved profile
pz-mod-checker manage --profile-list              # List all profiles
```

### `bisect` — Find the crashing mod

Binary search through your mods to identify which one crashes PZ. Finds the culprit in ~8 rounds for 165 mods.

```bash
pz-mod-checker bisect start    # Save backup, split mods, begin
# Launch PZ, test...
pz-mod-checker bisect crash    # PZ crashed — narrow down
# Launch PZ, test...
pz-mod-checker bisect ok       # PZ loaded fine — narrow down
# Repeat until found...
pz-mod-checker bisect status   # Check progress
pz-mod-checker bisect abort    # Give up, restore backup
```

**How it works:**
1. Saves your current mod list as a backup profile
2. Enables half your mods, disables the other half
3. You launch PZ and report whether it crashed or loaded OK
4. Based on your answer, it narrows the suspect set by half
5. Repeats until one mod is identified
6. Restores all mods except the culprit

**Tips:**
- Use `--auto-diagnose` with `crash` to check if the log already names the culprit (can skip remaining rounds)
- Respects mod dependencies — mods that require each other stay together during splits
- State persists between runs — close the terminal, launch PZ, come back later
- Run `bisect abort` at any time to restore your original mod list

---

## How It Works

### Three Detection Layers

| Layer | When | What |
|-------|------|------|
| **Rule Engine** | Pre-launch (static) | 51 version-keyed rules checking for removed APIs, renamed functions, structural issues |
| **Workshop API** | Pre-launch (network) | Optional Steam Workshop metadata — update timestamps, B42 tags |
| **Log Parser** | Post-launch (forensic) | Actual runtime errors from `console.txt` with mod attribution |

### Rule Coverage

| PZ Version | Rules | Key Changes |
|------------|-------|-------------|
| 42.0.0 | 13 | Inventory UI removal, crafting overhaul, mod structure |
| 42.8.0 | 20 | Biome rewrite, blacksmithing items removed |
| 42.9.0 | 24 | Body location renames |
| 42.10.0 | 25 | OnCreate signature change |
| 42.12.0 | 28 | Explosion API migration |
| 42.13.0 | 40 | Registry system, CharacterStat refactoring |
| 42.14.0 | 48 | .223 ammo removal, fluid container changes |
| 42.15.3 | 51 | JSON translations, game mode renames |

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows** | Full support | Primary development platform. Auto-detects Steam and Zomboid paths. |
| **Linux** | Full support | Detects `~/.steam/` and `~/Zomboid/` paths. |
| **macOS** | Full support | Detects `~/Library/Application Support/Steam/` paths. |

All features work cross-platform: scanning, diagnosing, mod management, bisect, and the web GUI. The tool uses `pathlib` throughout for platform-safe path handling. ANSI colors auto-disable when output is piped or on unsupported terminals.

---

## File Locations

The tool auto-detects these paths:

| File | Location | Purpose |
|------|----------|---------|
| Mod list | `~/Zomboid/mods/default.txt` | Which mods are enabled |
| Crash log | `~/Zomboid/console.txt` | Last session's log (overwritten each launch) |
| Profiles | `~/Zomboid/Lua/pz_modlist_settings.cfg` | Saved mod profiles |
| User mods | `~/Zomboid/mods/` | Locally installed mods |
| Workshop mods | `Steam/steamapps/workshop/content/108600/` | Steam Workshop mods |
| Bisect state | `~/Zomboid/.pz-mod-checker/bisect_state.json` | Bisect progress |
| Workshop cache | Platform cache dir | Cached Steam API responses (24h TTL) |

---

## Installation

### From source (requires Python 3.10+)

```bash
git clone https://github.com/rob-kingsbury/pz-mod-checker.git
cd pz-mod-checker
pip install -e .
pz-mod-checker scan 42.15.3
```

### From pip (coming soon)

```bash
pip install pz-mod-checker
```

### Standalone .exe (coming soon)

Download from [GitHub Releases](https://github.com/rob-kingsbury/pz-mod-checker/releases) — no Python required. Double-click to launch the web GUI.

---

## JSON API

When running the web GUI (`--gui`), all endpoints are available at `http://localhost:8642`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scan?version=42.15.3` | Scan all mods against a version |
| GET | `/api/diagnose` | Parse last session's crash log |
| GET | `/api/mods` | List all mods with enabled/disabled status |
| POST | `/api/mods/enable` | Enable mods `{"mod_ids": [...]}` |
| POST | `/api/mods/disable` | Disable mods `{"mod_ids": [...]}` |
| POST | `/api/mods/disable-breaking` | Disable mods that caused errors |
| GET | `/api/profiles` | List saved profiles |
| POST | `/api/profile/save` | Save current mod list `{"name": "..."}` |
| POST | `/api/profile/load` | Load a profile `{"name": "..."}` |
| GET | `/api/bisect/status` | Get bisect session state |
| POST | `/api/bisect/start` | Start a new bisect |
| POST | `/api/bisect/crash` | Report PZ crashed |
| POST | `/api/bisect/ok` | Report PZ loaded OK |
| POST | `/api/bisect/abort` | Abort bisect, restore backup |
| GET | `/api/version` | Tool version |

All endpoints return JSON. Any program that can make HTTP requests can use the API.

---

## Contributing Rules

Rules are defined in JSON files under `data/rules/`. Each rule describes a breaking change introduced in a specific PZ version:

```json
{
  "id": "b42-13-fear-removed",
  "type": "api_removal",
  "severity": "breaking",
  "since": "42.13.0",
  "description": "Legacy Fear stat removed",
  "pattern": "getFear\\b|setFear\\b",
  "regex": true,
  "scan": "*.lua",
  "context": "Fear stat removed entirely in 42.13"
}
```

To add a rule: edit the appropriate version file, test with `pz-mod-checker scan <version>`, and submit a PR.

---

## Architecture

```
pz_mod_checker/
    cli.py          # CLI entry point with subcommands
    paths.py        # Shared path utilities
    scanner/        # Mod discovery, file traversal, mod.info parsing
    rules/          # Rule engine, JSON loader, version comparison
    reporter/       # Output formatting (CLI, JSON)
    diagnose.py     # Log parser for console.txt
    manager.py      # Mod enable/disable, profiles
    workshop.py     # Steam Workshop API queries
    bisect.py       # Binary search for crashing mod
    gui/            # Localhost web dashboard
        server.py   # HTTP server + JSON API
        static/     # HTML + Tailwind CSS frontend
data/
    rules/          # Version-keyed rule definitions (JSON)
    no-comp.txt     # Known incompatible mod IDs
```

Zero external dependencies. Python 3.10+ stdlib only.
