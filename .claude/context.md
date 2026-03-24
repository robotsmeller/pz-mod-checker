# PZ Mod Checker Context

```yaml
version: 0.2.0
status: Feature complete, UX polish needed before distribution
created: 2026-03-23
session: 5
last_updated: 2026-03-24

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

### Session 4 (2026-03-24): Rule Quality + Engine + GUI Polish
Rule quality: false positives 100% → 30% via condition system. 6 new rules, confidence/group fields, _make_finding helper. GUI: group-first rendering, SVG icons, disable/delete everywhere, workshop label precision, scan sort/filter. Closed 9 issues, created 4 new (#19-22).

### Session 3 (2026-03-24): GUI v2 + Workshop
GUI v2: scope bar, accessibility, dev mode, pagination, workshop integration. Themed modals, toasts, inline user guide. 51 rules, 51 tests.

### Session 2 (2026-03-23): Core Features
Diagnose, Manager, Bisect, CLI subcommands, Web GUI v1.
