# PZ Mod Checker Context

```yaml
version: 0.1.0
status: Initial development
created: 2026-03-23

arch:
  stack: Python 3.10+, CLI (argparse), YAML rules
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
