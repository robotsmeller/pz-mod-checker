# PZ Mod Checker Context

```yaml
version: 0.1.0 (pyproject)
status: 82 rules covering B42.0 through B42.20.4, 79 tests passing. Diagnose page labels require() failures with Unbreaker coverage.
created: 2026-03-23
session: 11
last_updated: 2026-09-25
continue_with: Pick between #23 (validate names against the installed game) and #2 (distribution). #23 is the bigger payoff.
blockers: none

arch:
  stack: Python 3.10+ stdlib only, CLI (argparse), JSON rules, localhost web GUI at :8642
  purpose: External pre-launch scanner for PZ mod compatibility
  target: Project Zomboid Build 42.x

identity:
  product: PZ Mod Checker
  what: External compatibility scanner, NOT an in-game mod
  approach: Rule-based (version-keyed PZ changes, not mod blacklists)
```

## To Resume

Session 12. Last code commit `13723cb`. Open issues: #23 (validate every name a mod uses against the installed
game), #2 (PyInstaller .exe + pip publish), #1 (crowdsourced data, backlog).

## How rules work

- One JSON file per PZ version in `data/rules/`, each rule with `since` and an optional `fixed_in`
  (rule stops firing at and above it). Use `fixed_in` when TIS reverses a change: 42.20's
  getFileWriter block (fixed 42.20.1) and 42.20.4's loadstring removal (fixed 42.21.0) both did.
- Players run stable and unstable at once, so the target version decides, never the branch.
- Derive rules by diffing an installed build's `media/lua` against the previous one, not from
  changelogs. Baselines live in `C:\pz-baselines\<version>\` (the Unbreaker project keeps them).
  Java-side changes do not show in a tree diff: read the jar with `javap -p -c -constants`
  (JDK at `C:\Program Files\Java\jdk-25\bin`).
- Pattern rules run on comment-stripped Lua. Translation rules read `translate_root`, which only
  knows `42/` and root layouts, not `common/` or point-release folders like `42.15/`.
- README's rule table is a running total recounted from the rule files; recount it when adding.

## Pending

1. **Mod layout blind spot**: `translate_root`/`lua_root` miss `common/` and `42.x/` folders. Seen
   on 2026-09-25 across installed Workshop mods. Affects every translation rule.
2. **42.19 attribution** of `CharacterCustomisationPanel`/`CommonTemplates` is `speculative`;
   the vanilla mirror's 42.18 commit (`dda81da`) would pin it.

## Session Notes

### Session 11 (2026-09-25): 42.20.2 and 42.20.4 rules, Unbreaker coverage committed
Done from the Unbreaker side, during its 42.21 pass. Added `b42-20-4-loadstring-removed` (fixed_in
42.21.0) and `b42-20-2-gettext-missing-arguments`, a new `gettext_arity` translation check that
compares arguments at each `getText` call with the highest `%N` in the mod's own EN translation.
Severity came from the engine, not the notes: 42.21's `Translator.getText` logs "Missing arguments"
and returns the unformatted text, throwing only in dev mode. Ran it across 207 installed Workshop
mods: 61 calls on placeholder keys, all correct, no findings. Committed the Unbreaker-coverage
diagnose feature that had sat uncommitted since 2026-05-07, minus its "Report to Unbreaker" button
(most UNKNOWN modules are mod-internal and unfixable, so it invited won't-fix issues). README brought
current. Folded `HANDOFF.md` into this file.

### Session 10 (2026-07-30): B42.20 Stable rules, backfilled from a file diff
Added `42.20.0.json` and backfilled `42.19.0.json` by diffing the vanilla Lua tree rather than
reading changelogs, which caught removals no changelog mentions. `ISFarmingCursor` deliberately has
no `replacement` (the Mouse variant shares only 6 of 10 methods). Implemented the
`no_lua_in_media_root` check, which had silently never fired since session 8; it globs `media` and
`*/media` because B42 mods keep media under `42/`, `common/` or a point release.

### Session 9 (2026-05-06): Live triage and B42 structure discovery
PZ B42 requires `mod.info` in BOTH the root and `42/`; a mod missing `42/mod.info` is silently
rejected, not even logged. Added `b42-modinfo-in-versioned-folder` (breaking). Diagnose now catches
`pcall(require, "X")`.
