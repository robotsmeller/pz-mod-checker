# Rule Schema Specification

## Rule Types

### 1. `structure` — Folder/file existence checks
```yaml
- id: b42-common-folder
  type: structure
  severity: breaking
  since: "42.0.0"
  description: "B42 requires common/ folder in mod root"
  check: dir_exists
  path: "common/"
```

### 2. `api_removal` — Removed Lua functions/classes
```yaml
- id: b42-remove-isinventorypage
  type: api_removal
  severity: breaking
  since: "42.0.0"
  description: "ISInventoryPage removed in B42"
  pattern: "ISInventoryPage"
  scan: "*.lua"
  context: "B41 inventory UI framework replaced"
```

### 3. `api_rename` — Renamed functions/classes
```yaml
- id: b42-rename-getspecificplayer
  type: api_rename
  severity: breaking
  since: "42.1.0"
  description: "getSpecificPlayer renamed to getPlayerByIndex"
  old_pattern: "getSpecificPlayer"
  new_name: "getPlayerByIndex"
  scan: "*.lua"
```

### 4. `api_signature` — Changed function signatures
```yaml
- id: b42-changed-additem-sig
  type: api_signature
  severity: warning
  since: "42.0.0"
  description: "addItem now requires 3 arguments (was 2)"
  pattern: "addItem\\s*\\([^,)]+,[^,)]+\\)"
  regex: true
  scan: "*.lua"
  context: "Third argument (container) now required"
```

### 5. `script_syntax` — Item/recipe script format changes
```yaml
- id: b42-item-script-format
  type: script_syntax
  severity: breaking
  since: "42.0.0"
  description: "Item script format changed in B42"
  pattern: "^\\s*item\\s+\\w+\\s*$"
  regex: true
  scan: "*.txt"
  path: "media/scripts/"
  context: "Item definitions now use new syntax"
```

### 6. `mod_info` — Required mod.info fields or values
```yaml
- id: b42-modinfo-versionmin
  type: mod_info
  severity: warning
  since: "42.0.0"
  description: "mod.info should declare versionMin for B42"
  field: "versionMin"
  check: "exists"
```

### 7. `translation` — Translation file format/encoding changes
```yaml
- id: b42-translation-encoding
  type: translation
  severity: warning
  since: "42.5.0"
  description: "Translation files must be UTF-8"
  scan: "*.txt"
  path: "media/lua/shared/Translate/"
  check: "encoding_utf8"
```

### 8. `deprecated` — Functions that still work but are deprecated
```yaml
- id: b42-deprecated-getworldage
  type: deprecated
  severity: info
  since: "42.2.0"
  description: "getWorldAge() deprecated, use getWorldTime()"
  pattern: "getWorldAge"
  scan: "*.lua"
  replacement: "getWorldTime()"
```

## Rule File Format

Each YAML file covers changes introduced in a specific version:

```yaml
# data/rules/42.0.0.yaml
version: "42.0.0"
release_date: "2024-11-01"
summary: "Major B42 release - crafting overhaul, item system rewrite"
source: "https://pzwiki.net/wiki/Build_42"

changes:
  - id: unique-rule-id
    type: structure|api_removal|api_rename|api_signature|script_syntax|mod_info|translation|deprecated
    severity: breaking|warning|info
    since: "42.0.0"
    description: "Human-readable description"
    # Type-specific fields follow...
```

## no-comp.txt Format

For mods that can't be detected by code analysis:

```
# Known incompatible mods
# Format: mod_id|max_compatible_version|reason
# Lines starting with # are comments

Arsenal26ForBuild41|41.78.16|Hardcoded B41 UI framework references
SuperbSurvivors|41.78.16|Uses removed NPC pathfinding internals
```

## Severity Decision Matrix

| Condition | Severity |
|-----------|----------|
| Mod will crash/fail to load | breaking |
| Mod may malfunction silently | warning |
| Deprecated but still functional | info |
| Structural missing but may work | warning |
| Known incompatible (no-comp.txt) | breaking |
