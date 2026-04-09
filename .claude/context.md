# PZ Mod Checker Context

```yaml
version: 0.2.0
status: Feature complete, ready for distribution
created: 2026-03-23
session: 7
last_updated: 2026-04-09

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

### Session 6 (2026-04-09): Issue Blitz + Rule Audit
Closed 9 issues. Scan UX: warning/breaking groups auto-expand, enabled/disabled status in scan results (dimmed + badge). Accessibility: keyboard toggles, loading states. DRY refactor: _cached_mod_status(). Workshop outbound links on Mods and Scan pages. Rule audit: 1912 to 1716 findings, tightened patterns, filesystem-security upgraded to breaking.

### Session 5 (2026-04-08): 42.16 Rules + False Positive Audit
Added 42.16.0.json (6 rules: occupation/trait renames, sandbox type change, procLists fix, Lua security). False positive audit on 258-mod install. 2432 to 1912 findings. 73 tests passing.

### Session 4 (2026-03-24): Rule Quality + Engine + GUI Polish
Rule quality: false positives 100% to 30% via condition system. 6 new rules, confidence/group fields. GUI: group-first rendering, SVG icons, sort/filter. Closed 9 issues, created 4 new.
