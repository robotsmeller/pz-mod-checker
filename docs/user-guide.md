# PZ Mod Checker User Guide

External compatibility scanner, crash diagnostics, and mod manager for **Project Zomboid Build 42**.

---

## Getting Started

### Web GUI (recommended)

```bash
pz-mod-checker --gui
```

Opens a dashboard at `http://localhost:8642` with four tabs: **Scan**, **Diagnose**, **Mods**, and **Bisect**.

### Command Line

```bash
pz-mod-checker scan 42.15.3      # Scan mods for compatibility issues
pz-mod-checker diagnose           # Parse last session's crash log
pz-mod-checker manage --list      # Show all mods with status
pz-mod-checker bisect start       # Find which mod is crashing PZ
```

---

## Scan

Checks your mods against version-keyed rules covering B42.0 through B42.15. Each rule describes a breaking change introduced in a specific PZ version.

### Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| **BREAKING** | Will crash or fail to load | Disable or update the mod |
| **WARNING** | May malfunction, needs investigation | Check if the mod has a B42 update |
| **INFO** | Cosmetic or minor, likely still works | Low priority, fix if you can |

### GUI

- **Version dropdown** auto-detects your PZ version and shows available rule sets
- **Scope** lets you scan only active mods or all installed mods
- **Severity filters** toggle which findings are shown
- **Search** filters results by mod name or ID
- **Pagination** shows 25 mods per page
- **Disable buttons** let you disable breaking mods without switching tabs

### CLI

```bash
pz-mod-checker scan 42.15.3                     # Scan all mods
pz-mod-checker scan 42.15.3 --verbose            # Show file paths and line numbers
pz-mod-checker scan 42.15.3 --severity breaking  # Only show breaking issues
pz-mod-checker scan 42.15.3 --format json        # Machine-readable output
pz-mod-checker scan 42.15.3 --check-workshop     # Include Steam Workshop metadata
pz-mod-checker scan 42.10.0                      # Scan against an older version
```

---

## Diagnose

Reads your last PZ session's `console.txt` and identifies which mods caused errors.

PZ logs Lua stack traces with `| MOD: <name>` attribution on every frame -- this tool reads those to pinpoint exactly which mod caused each error.

### What "Missing require() modules" Means

If you see require failures, it means mods tried to load Lua modules that don't exist. This usually means:
- The mod uses features removed or renamed in Build 42
- The mod depends on another mod that isn't installed

**Fix:** Check if each mod has a B42-compatible update on the Workshop. If not, disable it.

### CLI

```bash
pz-mod-checker diagnose                   # Parse last session
pz-mod-checker diagnose --auto-disable    # Parse + offer to disable culprits
pz-mod-checker diagnose --format json     # Machine-readable output
pz-mod-checker diagnose --log path/to/console.txt  # Specific log file
```

---

## Mod Manager

Toggle mods on/off without launching PZ. Reads and writes `~/Zomboid/mods/default.txt`. Creates a backup before every change.

### GUI

- **Search** and **sort** (A-Z, Z-A, Enabled first, Disabled first, Updates first)
- **Toggle switches** to enable/disable individual mods
- **Bulk actions**: Enable All, Disable All
- **Check for Updates**: Queries Steam Workshop to detect mods with newer versions or stale mods not updated since B42. Shows badges: "update available", "stale", "B42 OK", "updated"
- **Profiles**: Save and load named mod configurations (via global scope bar)

### CLI

```bash
pz-mod-checker manage --list              # Show all mods with status
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

---

## Bisect

Binary search through your mods to identify which one crashes PZ. Finds the culprit in ~8 rounds for 165 mods.

### How It Works

1. **Start** -- saves your current mod list and enables half your mods
2. **Launch PZ** -- test whether it crashes or loads OK
3. **Report** -- click "PZ Crashed" or "PZ Loaded OK"
4. **Repeat** -- the tool narrows the suspect set by half each round
5. **Found** -- the culprit mod is identified and disabled, all others restored

### Tips

- Uses auto-diagnose on crash to check if the log already names the culprit (can skip rounds)
- Respects mod dependencies -- mods that require each other stay together during splits
- State persists between runs -- close the terminal, launch PZ, come back later
- Run abort at any time to restore your original mod list

### CLI

```bash
pz-mod-checker bisect start    # Save backup, split mods, begin
pz-mod-checker bisect crash    # PZ crashed -- narrow down
pz-mod-checker bisect ok       # PZ loaded fine -- narrow down
pz-mod-checker bisect status   # Check progress
pz-mod-checker bisect abort    # Give up, restore backup
```

---

## Dev Mode

Toggle **Dev Mode** in the footer to enable features for mod developers:

- **Rule IDs** shown on each finding (e.g. `b42-13-fear-removed`)
- **Export buttons** per mod: Copy as TXT, Markdown, or JSON
- **Export All**: Copy the entire scan report to clipboard
- Share reports with other modders or paste into GitHub issues

---

## File Locations

The tool auto-detects these paths:

| File | Location | Purpose |
|------|----------|---------|
| Mod list | `~/Zomboid/mods/default.txt` | Which mods are enabled |
| Crash log | `~/Zomboid/console.txt` | Last session's log |
| Profiles | `~/Zomboid/Lua/pz_modlist_settings.cfg` | Saved mod profiles |
| User mods | `~/Zomboid/mods/` | Locally installed mods |
| Workshop mods | `Steam/steamapps/workshop/content/108600/` | Steam Workshop mods |
| Bisect state | `~/Zomboid/.pz-mod-checker/bisect_state.json` | Bisect progress |

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows** | Full support | Primary development platform |
| **Linux** | Full support | Detects `~/.steam/` and `~/Zomboid/` |
| **macOS** | Full support | Detects `~/Library/Application Support/Steam/` |

---

## Installation

### From source (Python 3.10+)

```bash
git clone https://github.com/robotsmeller/pz-mod-checker.git
cd pz-mod-checker
pip install -e .
pz-mod-checker --gui
```

### From pip (coming soon)

```bash
pip install pz-mod-checker
```

### Standalone .exe (coming soon)

Download from [GitHub Releases](https://github.com/robotsmeller/pz-mod-checker/releases) -- no Python required.
