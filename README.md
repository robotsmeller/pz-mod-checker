# PZ Mod Checker

External compatibility scanner, crash diagnostics, and mod manager for **Project Zomboid Build 42**.

Scans your mods for known breaking changes, parses crash logs to identify culprits, checks Steam Workshop for updates, generates translation stubs for missing EN keys, and lets you enable/disable mods without launching the game. Zero dependencies -- runs entirely on Python's standard library.

**[User Guide](docs/user-guide.md)** | **[Download](https://github.com/robotsmeller/pz-mod-checker/releases)** | **[Steam Workshop: @robotsmeller](https://steamcommunity.com/id/robotsmeller)**

---

## Quick Start

```bash
# Install
pip install -e .

# Launch the web GUI (recommended)
pz-mod-checker --gui

# Or use the CLI
pz-mod-checker scan 42.15.3
pz-mod-checker diagnose
pz-mod-checker bisect start
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Scan** | 81 version-keyed rules covering B42.0 through B42.20.4. Severity filters, pagination, search, inline disable buttons. Sorted by severity (breaking first). |
| **Diagnose** | Parses `console.txt` crash logs with mod attribution. Catches `require("X")`, `require "X"`, and `pcall(require, "X")` patterns. Plain-language explanations for `require()` failures with fix suggestions and TXT/MD/JSON export. |
| **Mod Manager** | Toggle mods on/off, search, sort (A-Z, enabled, updates), bulk actions, Workshop update checking with staleness badges. |
| **Bisect** | Binary search to find the crashing mod. ~8 rounds for 200 mods. Personalized round estimate in GUI. |
| **Workshop** | Queries Steam Workshop API to detect outdated mods, stale pre-B42 mods, and available updates. 24h cache. |
| **Translate** | Scans mods for missing EN translation keys, generates a single stub shim mod with title-cased strings. On/off toggle in GUI. |
| **Web GUI** | Localhost dashboard at `:8642`. Dark theme with PZ green accents, multiple tabs, global scope bar, JSON API. |
| **Dev Mode** | Rule IDs on findings, export per-mod or full reports as TXT/MD/JSON. Aimed at mod developers. |
| **Scope Bar** | Global Active/All/Profile selector that controls which mods every tab operates on. Persists across sessions. |
| **Inline Docs** | User guide loads from GitHub (versioned), renders in-app. Update notice when newer version available. |
| **Accessibility** | ARIA roles on tabs/toggles/pills, keyboard navigation, focus traps, themed confirm modals. |

---

## Installation

### From source (Python 3.10+)

```bash
git clone https://github.com/robotsmeller/pz-mod-checker.git
cd pz-mod-checker
pip install -e .
```

### Standalone .exe (coming soon)

Download from [GitHub Releases](https://github.com/robotsmeller/pz-mod-checker/releases) -- no Python required. Double-click to launch the web GUI.

### From pip (coming soon)

```bash
pip install pz-mod-checker
```

---

## Rule Coverage

| PZ Version | Rules | Key Changes |
|------------|-------|-------------|
| 42.0.0 | 19 | Inventory UI removal, crafting overhaul, mod structure |
| 42.5.0 | 20 | ISSearchManager removed |
| 42.8.0 | 27 | Biome rewrite, blacksmithing items removed |
| 42.9.0 | 31 | Body location renames |
| 42.10.0 | 32 | OnCreate signature change |
| 42.12.0 | 36 | Explosion API migration |
| 42.13.0 | 52 | Registry system, CharacterStat refactoring |
| 42.14.0 | 60 | .223 ammo removal, fluid container changes |
| 42.15.0 | 63 | JSON translations, game mode renames |
| 42.16.0 | 69 | Occupation/trait renames, sandbox type changes |
| 42.17.0 | 71 | MapRemotePlayerVisibility, VHS skill tapes |
| 42.18.0 | 74 | Model prefix rules, safehouse option rename |
| 42.19.0 | 76 | CharacterCustomisationPanel and CommonTemplates removed |
| 42.20.0 | 80 | ISFarmingCursor removed, getFileWriter extension whitelist (fixed in 42.20.1) |
| 42.20.4 | 81 | loadstring/loadstream removed (back in 42.21) |

Rules is the running total added up to that version, counted from the current rule files. Rules with `fixed_in` stop firing at that version.

---

## JSON API

When running the web GUI (`--gui`), all endpoints are available at `http://localhost:8642`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scan?version=42.15.0&scope=active` | Scan mods (scope: active, all, or profile name) |
| GET | `/api/diagnose` | Parse last session's crash log |
| GET | `/api/mods` | List all mods with status |
| POST | `/api/mods/enable` | Enable mods `{"mod_ids": [...]}` |
| POST | `/api/mods/disable` | Disable mods `{"mod_ids": [...]}` |
| POST | `/api/mods/disable-breaking` | Disable mods that caused errors |
| POST | `/api/mods/disable-scan-breaking` | Disable mods with breaking scan findings |
| GET | `/api/profiles` | List saved profiles (includes mod_ids) |
| POST | `/api/profile/save` | Save current mod list `{"name": "..."}` |
| POST | `/api/profile/load` | Load a profile `{"name": "..."}` |
| GET | `/api/bisect/status` | Get bisect session state |
| POST | `/api/bisect/start` | Start a new bisect |
| POST | `/api/bisect/crash` | Report PZ crashed |
| POST | `/api/bisect/ok` | Report PZ loaded OK |
| POST | `/api/bisect/abort` | Abort bisect, restore backup |
| GET | `/api/version` | Tool version, PZ version, mod counts |
| GET | `/api/versions` | Available PZ versions from rule files (newest first) |
| GET | `/api/workshop/check` | Check Steam Workshop for mod updates and staleness |
| GET | `/api/docs` | Local user guide (markdown) |

---

## Contributing Rules

Rules live in `data/rules/*.json`. Each describes a breaking change in a specific PZ version:

```json
{
  "id": "b42-13-fear-removed",
  "type": "api_removal",
  "severity": "breaking",
  "since": "42.13.0",
  "description": "Legacy Fear stat removed",
  "pattern": "getFear\\b|setFear\\b",
  "regex": true,
  "scan": "*.lua"
}
```

To add a rule: edit the appropriate version file, test with `pz-mod-checker scan <version>`, and submit a PR.

---

## Roadmap

- [x] Scanner with 81 version-keyed rules
- [x] Crash log diagnostics with mod attribution
- [x] Mod manager with profiles
- [x] Bisect (binary search for crashing mod)
- [x] Web GUI v2 with dev mode, scope bar, accessibility
- [x] Workshop update and staleness checking
- [x] Inline versioned user guide
- [ ] PyInstaller .exe distribution ([#2](https://github.com/robotsmeller/pz-mod-checker/issues/2))
- [ ] pip publish to PyPI
- [ ] Crowdsourced mod compatibility data ([#1](https://github.com/robotsmeller/pz-mod-checker/issues/1))

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
    workshop.py     # Steam Workshop API queries + cache
    bisect.py       # Binary search for crashing mod
    gui/            # Localhost web dashboard
        server.py   # ThreadingHTTPServer + JSON API
        static/     # HTML + Tailwind CSS + marked.js frontend
data/
    rules/          # Version-keyed rule definitions (JSON)
    no-comp.txt     # Known incompatible mod IDs
docs/
    user-guide.md   # User guide (also shown in-app)
tests/
    78 tests        # pytest suite
```

Zero external dependencies. Python 3.10+ stdlib only.

---

## License

MIT
