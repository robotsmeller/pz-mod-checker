# PZ Mod Checker -- Handoff

**Last Updated:** 2026-03-24 (end of Session 4)

## Current State

Rule quality overhaul complete. False positives reduced from 100% to 30% of mods flagged (breaking/warning). New condition system, 6 new rules, confidence/group metadata, GUI/CLI group rendering. 65 tests passing.

## What's Working

- **Scanner** -- 57 JSON rules covering B42.0 through B42.15, version-keyed filtering
- **Rule Engine** -- Conditional rules (8 condition types, AND logic), confidence levels, rule groups
- **Diagnose** -- Parses console.txt, identifies mod errors with MOD attribution, resolves names to IDs
- **Manager** -- Read/write default.txt, enable/disable mods, profiles, backups
- **Workshop** -- Steam API queries with 24h cache, staleness detection, update checking in GUI
- **Bisect** -- Binary search with dependency groups, state persistence, diagnose shortcut
- **CLI** -- 4 subcommands (scan, diagnose, manage, bisect) + --gui flag, grouped output
- **Web GUI v2** -- Full dashboard at :8642, group-first finding rendering, confidence badges
- **Tests** -- 65 tests, all passing (14 new condition tests)
- **Packaging** -- pyproject.toml, pip install -e . works, JSON rules
- **GitHub** -- Repo at robotsmeller/pz-mod-checker, 1 open issue (#9)

## Session 4 Summary

### Rule Quality (Phase 1)
False positive reduction for structural rules:

| Rule | Before | After | Change |
|------|--------|-------|--------|
| `b42-13-registry-required` | 257 mods | 8 mods | -97% (condition: has TraitFactory/ProfessionFactory) |
| `b42-15-translation-json` | 210 mods | 0 mods | -100% (condition: has old .txt translations) |
| `b42-modinfo-versionmin` | 189 mods | 66 mods | -65% (condition: has 42/ folder) |
| `b42-versioned-folder` | 149 mods | 20 mods | -87% (condition: has versionMin + no common/) |
| `b42-common-folder` | 83 mods (warn) | 72 mods (info) | downgraded + condition |
| `b42-getspecificplayer` | 46 mods (warn) | 46 mods (info) | downgraded to info |
| **Breaking/warning total** | **258/258 (100%)** | **78/258 (30%)** | **-70%** |

Key insight from 42.15 patch notes: only ONE of `common/` or `42/` folder is required, not both.

### New Rules (Phase 2)
6 new rules from Steam News API + Indie Stone forum research:

| Rule | Version | Mods Hit | Severity |
|------|---------|----------|----------|
| `b42-removed-isinventorypanecontextmenu` | 42.0 | 28 | breaking |
| `b42-12-vehiclemechanics-ui` | 42.12 | 12 | warning |
| `b42-13-moodletype-register` | 42.13 | 5 | warning |
| `b42-13-bodylocation-setexclusive` | 42.13 | 4 | warning |
| `b42-13-weaponcategory-register` | 42.13 | 2 | warning |
| `b42-5-issearchmanager-removed` | 42.5 | 0 | breaking |

Also added 42.5.0.json rule file (new version coverage).

### Engine Improvements (Phase 3)
1. **Condition system** -- 8 condition types with AND logic, evaluated before rule application
2. **`_make_finding` helper** -- centralized Finding construction (was 6 separate sites)
3. **Confidence field** -- `certain` (48 rules), `likely` (6), `speculative` (3)
4. **Group field** -- 10 rule groups: inventory-ui-rewrite, crafting-overhaul, registry-system, character-stat-refactor, ammo-rework, blacksmithing-items, body-location-renames, crushed-ore-removal, mod-structure, gamemode-renames
5. **GUI group rendering** -- group-first with max-severity badge, breaking expanded
6. **CLI group rendering** -- collapsed lines in non-verbose, expanded in verbose
7. **Confidence badges** -- displayed in GUI and CLI, speculative findings dimmed

### Test Coverage
14 new condition tests:
- 8 condition types × pass/fail
- AND composition test
- Invalid regex fallback test
- Empty condition test

## Open Issues

- #9 -- No loading state on disable/enable — double-click fires twice (from Session 3)

## Architecture

### Condition System
Rules can have a `condition` dict that must pass before the rule is applied. Conditions AND together.

| Condition | Effect |
|-----------|--------|
| `has_lua_pattern` | Mod's Lua files contain regex match |
| `has_files_in_dir` + `file_glob` | Directory contains matching files |
| `has_lua_files` | Mod has any .lua files |
| `has_content_dir` | Mod has root media/lua or media/scripts |
| `has_b42_folder` / `not_has_b42_folder` | Mod has/doesn't have 42/ folder |
| `not_has_common_folder` | Mod doesn't have common/ folder |
| `has_version_min` | mod.info declares versionMin |

### Finding Pipeline
`Rule` → `_make_finding(mod, rule, **overrides)` → `Finding` → reporters

Both `confidence` and `group` flow from Rule through Finding to JSON/GUI/CLI automatically via `dataclasses.asdict()`.

### Rule Groups
Groups collapse related findings in GUI (details/summary) and CLI (single line in non-verbose). Max severity of group members shown as the group badge.

## Next Session

### Priority: Distribution (Issue #2)
- PyInstaller .exe packaging
- pip publish to PyPI
- Consider splitting index.html into modules (~1600 lines)

### Optional: Further Rule Refinement
- `b42-14-revolver-ammo-changed` (7 mods, 314 hits) -- `Bullets45` pattern may be too broad
- Research B42.1-42.4 and 42.6-42.7 patch notes (no rule files for these yet)
- Crowdsourced mod compatibility data (Issue #1)

### Technical Debt
- Workshop module uses `confidence` with `high/medium/low` vocabulary vs rule engine `certain/likely/speculative` — consider harmonizing
- Confidence filtering in GUI (currently display-only)

## Session 4 Commits
```
d7a0381 GUI/CLI: group-first rendering, confidence badges
cd8dd86 Add confidence/group fields, extract _make_finding helper
8938fc9 Add 14 condition tests covering all 8 condition types
```
Plus earlier session 4 commits (rule quality + new rules):
```
[from earlier in session]
Condition system, false positive fixes, 6 new rules, closed 9 issues
```
