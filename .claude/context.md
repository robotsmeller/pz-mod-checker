# PZ Mod Checker Context

```yaml
version: 0.2.0
status: Feature complete, pre-distribution
created: 2026-03-23

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

### Session 1 (2026-03-23)
- Initial project creation
- Architecture: external Python CLI tool
- Rule engine: YAML-based, version-keyed breaking change definitions
- Supplement: no-comp.txt for known incompatible mod IDs
- Scanner: full filesystem traversal of mod directories
- Reporter: CLI table, JSON, HTML output formats

### Session 2 (2026-03-23)
- Diagnose (console.txt parser), Manager (default.txt read/write)
- Bisect (binary search for problem mods)
- CLI subcommands: scan, diagnose, manage, bisect
- Web GUI v1 at :8642

### Session 3 (2026-03-24)
- GUI v2: scope bar, tab descriptions, dev mode, pagination, accessibility
- Workshop integration: Steam API queries, update checking, badges
- Themed modals, toast notifications, inline user guide
- 51 rules, 51 tests, full audit fixes

### Session 4 (2026-03-24)
- Rule quality: false positives 100% → 30% (condition system)
- 6 new rules from Steam API + forum research (57 total)
- Engine: _make_finding helper, confidence field, rule groups
- GUI/CLI: group-first rendering, confidence badges, Morgan UI spec
- 65 tests (14 new condition tests)
- Closed 9 GitHub issues
