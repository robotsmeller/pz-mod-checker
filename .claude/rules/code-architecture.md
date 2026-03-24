# Code Architecture Rules

## Principles

- **Stdlib only** for core functionality. No pip dependencies required to scan.
- **Pathlib everywhere** — never use os.path string manipulation
- **Type hints** on all function signatures
- **Dataclasses** for structured data (rules, findings, mod info)
- **Match/case** for version comparison and rule type dispatch

## Structure

```
src/
  scanner/       # Mod discovery and file reading
    __init__.py
    discovery.py   # Find mods in directories
    mod_info.py    # Parse mod.info files
    lua_reader.py  # Read and search Lua source files
  rules/         # Rule engine
    __init__.py
    loader.py      # Load YAML rule definitions
    engine.py      # Apply rules to scanned mods
    version.py     # Version parsing and comparison
  reporter/      # Output formatting
    __init__.py
    cli.py         # Terminal table output
    json_out.py    # Machine-readable JSON
  cli.py         # Main entry point, argparse
data/
  rules/         # YAML rule files by version
    42.0.0.yaml
    42.1.0.yaml
  no-comp.txt    # Known incompatible mod IDs
tests/
  test_scanner.py
  test_rules.py
  test_version.py
  fixtures/      # Test mod structures
```

## Patterns

### Rule Definition (YAML)
```yaml
version: "42.0.0"
changes:
  - id: structure-common-folder
    type: structure
    severity: breaking
    description: "B42 requires common/ folder in mod root"
    check: dir_exists
    path: common/
```

### Finding (dataclass)
```python
@dataclass
class Finding:
    mod_id: str
    mod_name: str
    rule_id: str
    severity: str  # breaking, warning, info
    message: str
    file_path: str | None
    line_number: int | None
```

### Severity Levels
- **breaking** — Will crash or fail to load
- **warning** — May malfunction, needs investigation
- **info** — Cosmetic or minor, likely still works
