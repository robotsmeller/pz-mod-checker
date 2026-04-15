# PZ Mod Checker Context

```yaml
version: 0.2.0
status: Feature complete, ready for distribution
created: 2026-03-23
session: 8
last_updated: 2026-04-15

arch:
  stack: Python 3.10+, CLI (argparse), JSON rules
  purpose: External pre-launch scanner for PZ mod compatibility
  target: Project Zomboid Build 42.x
  coauthor: Claude Opus 4.6 <noreply@anthropic.com>

identity:
  product: PZ Mod Checker
  what: External compatibility scanner, NOT an in-game mod
  approach: Rule-based (version-keyed PZ changes, not mod blacklists)
```

## Session Notes

### Session 7 (2026-04-15): Translation Shim + Rule False Positive Fixes
New translate.py module + Translate GUI tab: scans mods for missing EN keys, generates single stub shim mod, on/off toggle, title-case key conversion. Removed false positive rule b42-removed-transferall (ISInventoryTransferAction still exists in B42). Narrowed b42-13-itemtag-string to only flag string literals in hasTag/containsTag calls.

### Session 6 (2026-04-09): Issue Blitz + Rule Audit
Closed 9 issues. Scan UX: warning/breaking groups auto-expand, enabled/disabled status in scan results (dimmed + badge). Accessibility: keyboard toggles, loading states. DRY refactor: _cached_mod_status(). Workshop outbound links on Mods and Scan pages. Rule audit: 1912 to 1716 findings, tightened patterns, filesystem-security upgraded to breaking.

### Session 5 (2026-04-08): 42.16 Rules + False Positive Audit
Added 42.16.0.json (6 rules: occupation/trait renames, sandbox type change, procLists fix, Lua security). False positive audit on 258-mod install. 2432 to 1912 findings. 73 tests passing.
