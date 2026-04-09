# PZ Mod Checker Context

```yaml
version: 0.2.0
status: Feature complete, UX polish needed before distribution
created: 2026-03-23
session: 6
last_updated: 2026-04-08

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

### Session 5 (2026-04-08): 42.16 Rules + False Positive Audit
Added 42.16.0.json (6 rules covering occupation/trait renames, sandbox type change, procLists fix, Lua security patch). False positive audit on 258-mod real install: removed bogus getSpecificPlayer rule, tightened 223 ammo pattern, fixed revolver word boundary, downgraded FirePower severity. 2432 → 1912 findings. 73 tests passing.

### Session 4 (2026-03-24): Rule Quality + Engine + GUI Polish
Rule quality: false positives 100% → 30% via condition system. 6 new rules, confidence/group fields, _make_finding helper. GUI: group-first rendering, SVG icons, disable/delete everywhere, workshop label precision, scan sort/filter. Closed 9 issues, created 4 new (#19-22).

### Session 3 (2026-03-24): GUI v2 + Workshop
GUI v2: scope bar, accessibility, dev mode, pagination, workshop integration. Themed modals, toasts, inline user guide. 51 rules, 51 tests.
