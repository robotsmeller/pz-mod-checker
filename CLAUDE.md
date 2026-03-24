# PZ Mod Checker

External pre-launch compatibility scanner for Project Zomboid Build 42 mods.

## Communication Style

Facts only. No fluff. Research before answering. Disagree when wrong.

---

## SESSION START (REQUIRED)

Before ANY work, use `/session-start` skill OR manually:

1. **Read context files:**
   - `c:\xampp\htdocs\pz-mod-checker\HANDOFF.md` - Current state
   - `c:\xampp\htdocs\pz-mod-checker\.claude\context.md` - Session history

2. **Check GitHub Issues:**
   ```bash
   gh issue list --state open --limit 10
   ```

3. **Output confirmation:**
   ```
   PZ Mod Checker ready. [X] open issues.
   Continue with: [current task]
   ```

---

## PROJECT INFO

| Property | Value |
|----------|-------|
| Folder | `c:\xampp\htdocs\pz-mod-checker` |
| Tech | Python 3.10+, CLI (argparse) |
| Purpose | Scan PZ mods for B42 compatibility issues |
| Target | Project Zomboid Build 42.x |

## Architecture

Two-layer system:

1. **Rule Engine** (`src/rules/`) — Version-keyed breaking change definitions
2. **Scanner** (`src/scanner/`) — Reads mod files, applies rules, reports findings
3. **Reporter** (`src/reporter/`) — Formats output (CLI, JSON, HTML)
4. **Data** (`data/`) — Rule definitions, known incompatibles

### Key Design Decisions

- **Rules describe PZ changes, not mod IDs.** Rules are version-keyed facts about what changed in PZ (removed functions, renamed classes, structural requirements). Any mod is checked against all applicable rules for the target version.
- **no-comp.txt** supplements rules with known-incompatible mod IDs for cases that can't be detected by code analysis (behavioral changes, runtime issues).
- **External tool, not a PZ mod.** Runs before PZ launches. Full filesystem access. Can read all mod source files.

## File Layout

| Path | Purpose |
|------|---------|
| `src/scanner/` | Mod discovery, file traversal, mod.info parsing |
| `src/rules/` | Rule engine, rule loader, version comparison |
| `src/reporter/` | Output formatting (CLI table, JSON, HTML) |
| `data/rules/` | YAML rule definitions by version |
| `data/no-comp.txt` | Known incompatible mod IDs |
| `tests/` | Pytest test suite |

## Development Rules

1. **Python 3.10+** — Use match/case, type hints, pathlib
2. **No external deps for core** — stdlib only for scanner/rules. Optional deps for fancy output.
3. **Rules are YAML** — Human-editable, version-controlled
4. **Test everything** — pytest, each rule type needs test coverage
5. **CLI first** — argparse, clean exit codes, machine-readable output option

## PZ Reference

- PZ mods live in: `C:\Users\<user>\Zomboid\mods\` and Steam Workshop folders
- Game Lua source: `<PZ install>/media/lua/`
- mod.info fields: name, id, modversion, versionMin, versionMax, require, url
- B42 requires: `42/` subfolder + `common/` folder in mod structure
- PZ version: readable from game files or config

## Key Resources (Stable URLs)

- PZwiki Modding: https://pzwiki.net/wiki/Modding
- PZwiki Lua API: https://pzwiki.net/wiki/Lua_(API)
- PZwiki Version History: https://pzwiki.net/wiki/Version_history
- PZwiki Build 42: https://pzwiki.net/wiki/Build_42
- FWolfe Modding Guide: https://github.com/FWolfe/Zomboid-Modding-Guide
- Awesome B42 Resources: https://github.com/JBD-Mods/awesome-project-zomboid-build42-resources

@.claude/rules/code-architecture.md
@.claude/context.md
