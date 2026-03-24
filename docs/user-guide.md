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

## Global Scope Bar

At the top of every page, the **scope bar** controls which mods all tabs operate on:

- **Active Mods** -- only mods enabled in your default.txt (default)
- **All Installed** -- every mod on disk, including disabled ones
- **Profile** -- a saved profile's mod list

The scope persists across sessions. Changing scope immediately re-renders the current tab.

**Save profiles** using the input field on the right side of the scope bar. Profiles store your current mod list so you can quickly switch configurations.

---

## Scan

Pre-launch check. Scans mod files for code patterns that break in your PZ version. Use this **before** launching PZ to catch issues early.

### Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| **BREAKING** | Will crash or fail to load | Disable or update the mod |
| **WARNING** | May malfunction, needs investigation | Check if the mod has a B42 update |
| **INFO** | Cosmetic or minor, likely still works | Low priority, fix if you can |

### GUI Features

- **Version dropdown** -- auto-detects your PZ version, shows rule sets labeled like "42.15+ (latest)"
- **Severity filter pills** -- click to toggle which severities are shown (keyboard-accessible)
- **Search** -- filter results by mod name or ID
- **Pagination** -- 25 mods per page with First/Prev/Next/Last controls
- **Results sorted by severity** -- breaking mods appear first
- **Findings grouped within each mod** -- breaking findings expanded, warnings and info collapsed
- **Inline Disable buttons** -- disable a mod directly from scan results
- **"Disable All Breaking"** -- bulk-disable all mods with breaking findings
- **Workshop badges** -- when you run "Check for Updates" on the Mods tab, scan results show "update on Workshop", "not updated for B42", or "B42 OK" badges

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

Post-crash forensics. Parses your last PZ session's **console.txt** to identify which mods caused errors. Best used **after** PZ crashes or misbehaves.

PZ logs Lua stack traces with `| MOD: <name>` attribution on every frame -- this tool reads those to pinpoint exactly which mod caused each error.

### What "Missing require() modules" Means

If you see require failures, it means mods tried to load Lua modules that don't exist. This usually means:
- The mod uses features removed or renamed in Build 42
- The mod depends on another mod that isn't installed

**Fix:** Check if each mod has a B42-compatible update on the Workshop. If not, disable it.

### GUI Features

- **Error cards** grouped by mod, sorted by error count
- **Inline Disable buttons** per mod
- **"Disable All Erroring Mods"** bulk action
- **Plain-language explanations** for require failures with fix suggestions

### CLI

```bash
pz-mod-checker diagnose                   # Parse last session
pz-mod-checker diagnose --auto-disable    # Parse + offer to disable culprits
pz-mod-checker diagnose --format json     # Machine-readable output
pz-mod-checker diagnose --log path/to/console.txt  # Specific log file
```

---

## Mod Manager

Enable or disable mods without launching PZ. Changes are written to **default.txt** and take effect on next PZ launch. Creates a backup before every change.

### GUI Features

- **Search** by name or ID
- **Sort**: A-Z, Z-A, Enabled first, Disabled first, Updates available first
- **Toggle switches** to enable/disable individual mods (keyboard-accessible)
- **Bulk actions**: Enable All, Disable All (operates on visible/filtered mods only)
- **Check for Updates**: Queries Steam Workshop to detect mods with newer versions. Shows badges:
  - **update available** (amber) -- Workshop version is newer than your local files
  - **stale** (red) -- mod hasn't been updated since B42 release
  - **B42 OK** (green) -- claims B42 support and updated recently
  - **updated** (gray) -- updated post-B42 but no explicit B42 tags
- Workshop last-updated date shown under each mod ID

### CLI

```bash
pz-mod-checker manage --list              # Show all mods with status
pz-mod-checker manage --disable SpnCloth  # Disable a specific mod
pz-mod-checker manage --enable SpnCloth   # Re-enable it
pz-mod-checker manage --disable-breaking  # Disable all mods that crashed last session
pz-mod-checker manage --disable-all       # Disable everything (safe mode)
pz-mod-checker manage --enable-only ModA ModB ModC  # Enable ONLY these mods

# Profiles (also accessible via scope bar in GUI)
pz-mod-checker manage --profile-save "Working"    # Save current mod list
pz-mod-checker manage --profile-load "Working"    # Restore a saved profile
pz-mod-checker manage --profile-list              # List all profiles
```

---

## Bisect

Crash isolation. Binary search through your mods to find the one crashing PZ. Rounds needed = log2(mod count) -- roughly **8 rounds for 200 mods**, 7 for 100, 5 for 30. The GUI shows a personalized estimate based on your active mod count. Your original mod list is restored when done.

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

- **Rule IDs** shown on each finding (e.g. `b42-13-fear-removed`) -- useful for reporting false positives or understanding what changed
- **Export buttons** per mod: Copy as TXT (for Discord/forums), Markdown (for GitHub issues), or JSON (for tooling/CI)
- **Export All**: Copy the entire scan report to clipboard in any format
- Share reports with other modders or paste into GitHub issues

Dev mode persists across sessions (stored in browser localStorage).

---

## Inline User Guide

Click **User Guide** in the footer to open this documentation inside the app. The guide is fetched from GitHub:

1. First tries the version-tagged release (e.g. `v0.1.0`) for an exact match
2. Falls back to the `main` branch (latest)
3. Falls back to the local bundled copy if offline

The loaded version is shown at the top of the panel. If a newer version of PZ Mod Checker is available, a link is shown in the header and in the docs panel.

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
| Workshop cache | Platform cache directory | Cached Steam API responses (24h TTL) |

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
