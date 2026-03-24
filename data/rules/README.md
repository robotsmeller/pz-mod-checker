# Rule Files

Each JSON file defines breaking changes introduced in a specific PZ version.

## Adding Rules

1. Create `<version>.json` (e.g., `42.5.0.json`)
2. Follow the schema in `.claude/specs/rule-schema.md`
3. Test with `python -m src 42.5.0 --mod path/to/test-mod -v`

## Finding Changes

1. Diff PZ's `media/lua/` between versions
2. Read changelogs at https://pzwiki.net/wiki/Version_history
3. Check Build pages (e.g., https://pzwiki.net/wiki/Build_42)
4. Monitor PZ modding Discord for reported breaks
