# PZ Mod Checker -- Handoff

**Last Updated:** 2026-03-24 (end of Session 3)

## Current State

GUI v2 complete with full audit fixes, accessibility, workshop integration, and test coverage. Ready for distribution (PyInstaller/.exe).

## What's Working

- **Scanner** -- 51 JSON rules covering B42.0 through B42.15, version-keyed filtering
- **Diagnose** -- Parses console.txt, identifies mod errors with MOD attribution, resolves names to IDs
- **Manager** -- Read/write default.txt, enable/disable mods, profiles, backups
- **Workshop** -- Steam API queries with 24h cache, staleness detection, update checking in GUI
- **Bisect** -- Binary search with dependency groups, state persistence, diagnose shortcut
- **CLI** -- 4 subcommands (scan, diagnose, manage, bisect) + --gui flag
- **Web GUI v2** -- Full dashboard at :8642 (see details below)
- **Tests** -- 51 tests, all passing
- **Packaging** -- pyproject.toml, pip install -e . works, JSON rules
- **GitHub** -- Repo at robotsmeller/pz-mod-checker, issues tracked

## GUI v2 (Session 3)

### Global
- **Scope bar**: Active Mods / All Installed / Profile radio buttons (persistent across sessions)
- **Tab descriptions**: each tab explains use case and expected outcomes
- **Footer**: credits (@robotsmeller), GitHub link, inline User Guide, Dev Mode toggle
- **Themed confirm modals** replace all native confirm() dialogs
- **Toast notifications** replace all alert() calls
- **Version check**: header badge when newer GitHub release available
- **Inline User Guide**: fetches from GitHub (versioned tag, falls back to main, then local)

### Scan Tab
- Version dropdown from rule files, auto-detects PZ version, labels like "42.15+ (latest)"
- Severity filter toggles (role="button", aria-pressed, keyboard-accessible)
- Results sorted by severity, paginated (25/page), searchable
- Findings grouped by severity within each mod (breaking expanded, others collapsed)
- Animated +/- indicators (CSS bar collapse)
- Inline Disable buttons, "Disable All Breaking" bulk action
- Workshop badges when update data loaded

### Dev Mode (footer toggle, persists in localStorage)
- Rule IDs on each finding
- Per-mod export: TXT / MD / JSON
- Export All: full scan report to clipboard

### Diagnose Tab
- User-friendly require() failure explanations with fix suggestions
- Inline Disable per mod
- Session info grid

### Mods Tab
- Sort: A-Z, Z-A, Enabled first, Disabled first, Updates first
- Scope-aware filtering
- Check for Updates: queries Steam Workshop, shows badges (update available, stale, B42 OK, updated)
- Toggle switches: role="switch", aria-checked, keyboard-accessible
- Bulk actions scope to filtered/visible list only

### Bisect Tab
- 3-step onboarding guide (single source, rendered dynamically)
- Progress bar with round/suspect/known-good counts

### Security
- XSS eliminated: all onclick handlers use data-attr + event delegation
- No CORS headers (same-origin only)
- try/except on all handlers returns JSON errors
- 400 on bad JSON, 413 on oversized body
- Content-Length limit (1MB)

### Accessibility
- Tab bar: role="tablist", role="tab", aria-selected, aria-controls, role="tabpanel"
- Toggle switches: role="switch", aria-checked, tabindex
- Severity pills: role="button", aria-pressed, keyboard handler
- Docs panel: role="dialog", aria-modal, focus trap, focus restore
- Scope profile select: aria-label
- Severity badges include text labels (brk/wrn/inf)

### Performance
- ThreadingHTTPServer prevents UI freeze during scan
- console.txt parsing cached with mtime check
- discover_mods() cached with mtime-based invalidation
- Workshop API responses cached (24h TTL)

## Open Issues

- #1 -- Crowdsourced mod compatibility data (future)
- #2 -- PyInstaller .exe + pip publish (next priority)
- #3 -- Documentation (ongoing)

## Critical: Rule Quality (discovered end of session 3)

Scanning 258 mods flags 258/258 with issues (100%). Structural rules are too broad:

| Rule | Mods Hit | Problem |
|------|----------|---------|
| `b42-13-registry-required` | 257/258 | Flags ANY mod without registries.lua — should only flag mods with trait/profession code |
| `b42-15-translation-json` | 210/258 | Flags ANY mod without JSON translations — most mods have none |
| `b42-modinfo-versionmin` | 189/258 | Missing versionMin — noisy informational |
| `b42-versioned-folder` | 149/258 | Missing `42/` folder — many B42 mods use root structure |

Pattern-based rules (API removals, renames) are accurate: ISInventoryPane hits 33 mods, transferAll hits 15.

## Next Session: Rule Engineering

### Phase 1: Fix False Positives (do first)
- Tighten structural rules with conditional checks ("if mod does Y, does it have X?")
- Target: <30% of mods flagged (down from 100%)
- This is logic refinement, no web research needed

### Phase 2: Research New Rules
- **Steam News API** (programmatic): `GET https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=108600&maxlength=0&count=100` -- public, no key needed, returns PZ patch notes
- **SteamDB** (manual reference only, DO NOT SCRAPE): https://steamdb.info/app/108600/patchnotes/
- **Secondary**: PZwiki version history, FWolfe modding guide, awesome-b42-resources
- Use extended thinking to synthesize changelog entries into rule candidates
- Cross-reference against existing 51 rules to find gaps

### Phase 3: Validation
- Run refined rules against 258-mod test set
- Verify real issues still caught, false positives eliminated

### After Rules
- Distribution (PyInstaller .exe + pip publish) -- issue #2
- Consider splitting index.html into modules (~1500 lines)

## Session 3 Commits (17)
```
25bdcdd Re-scan after Disable All Breaking Mods
5e52571 Dynamic bisect round estimate based on active mod count
cc708ce Workshop badges link to Steam Workshop pages
fca4d5c Update README, user guide, and HANDOFF for session 3 close
cec8930 Gitignore audit-report.md
db15866 Add .gitignore entries for scroll-analysis-output and .claude/settings
f989bbf Test pass: fix 5 bugs, add 8 unit tests, 51 tests passing
e2c047f Add Workshop update checking to GUI
4ba2a0c Fix medium audit findings #14-#18, update HANDOFF
3da57dd Fix 10 audit findings: XSS, accessibility, UX, performance
9acb87d Global scope bar: Active/All/Profile scoping across all tabs
d9e0c47 Tab descriptions, versioned docs, update checker, sort fix
4e00812 Update GitHub URLs to robotsmeller org
2cb7f30 Add inline user guide, split README into project page + docs
a19efca GUI: dev mode, pagination, animated +/-, footer, mod sorting
1aa04f4 Fix GUI init: split fetches so dropdown/header load independently
05b8a89 GUI polish: 17 improvements from audit feedback
```
