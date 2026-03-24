---
name: session-start
description: Load all project context files and display current state at session start
disable-model-invocation: true
---

# Session Start

Initialize a new PZ Mod Checker session by loading all required context.

## Step 1: Load Context Files

Read these files (in parallel):

1. `c:\xampp\htdocs\pz-mod-checker\HANDOFF.md` - Current state, what's next
2. `c:\xampp\htdocs\pz-mod-checker\.claude\context.md` - Session history

## Step 2: Check GitHub Issues

```bash
gh issue list --state open --limit 10
```

## Step 3: Verify Environment

```bash
git status
python --version
```

## Step 4: Output Session Summary

```
================================================================================
PZ MOD CHECKER SESSION [N+1] READY
================================================================================

Status: [from context.md]
Last Session: [N] - [focus]

OPEN ISSUES ([count])
| #  | Title                              | Priority |
|----|------------------------------------|---------|

CONTINUE WITH: [next step from HANDOFF.md]
================================================================================
```

## Step 5: Await Instructions
