---
name: efficiency-router
description: >-
  Use when the user asks about Antigravity usage, quota, limits, or budget status;
  when they report hitting a usage limit (calibrate budgets); or when composing a
  subagent delegation prompt under the efficiency router rules and you want the
  standard templates.
---

# Efficiency Router

Plugin root: `~/.gemini/config/plugins/efficiency-router/`
CLI: `python ~/.gemini/config/plugins/efficiency-router/scripts/router.py <cmd>`

## Usage commands

| Situation | Command |
|---|---|
| User asks "how much have I used?" / "사용량 보여줘" | `dashboard "<artifact_dir>/router_dashboard.html"` then reply with `<agent-embed src="file:///<artifact_dir>/router_dashboard.html"></agent-embed>` (forward slashes). Add at most 2 lines of commentary. |
| Text-only quick check | `status` |
| User says they just hit a limit | `calibrate <bucket> 5h` (or `7d` for the weekly cap) |
| Status shows unmapped model names | `alias "<raw name>" <claude\|gemini_pro\|gemini_flash>` |
| Manually set a budget | `set <bucket> <5h\|7d> <tokens>` |
| Start fresh | `reset` |

Numbers are **estimates** (transcript size / 4 + overhead per call). Say so when
reporting. Calibration makes the levels match real limits; recommend it the first
time the user hits a limit.

After `calibrate`, briefly tell the user the new budget and that YELLOW/RED will
now trigger at 60%/85% of it.

## Delegation templates

Read-only research (`TypeName: research`, `Model: flash`):
```
Goal: <one sentence>.
Scope: <paths / URLs>. Do not modify files.
Find: <specific questions>.
Return (<=250 words): bullets with file:line refs; "NOT FOUND" if absent. No code dumps beyond 10-line snippets.
```

Implementation (`TypeName: self`, `Model: pro`, or `flash` for boilerplate):
```
Goal: <behavior to achieve>.
Files: <exact paths>. Do not touch: <paths>.
Constraints: <style, APIs, compat>.
Done when: <tests/commands that must pass>.
Return: list of changed files + one line each, test output summary, open issues.
```

Second opinion for a cheap main model (`TypeName: research`, `Model: pro`):
```
Problem: <summary + key code refs>.
Options considered: <A/B>.
Return: recommended option, top 3 risks, what to verify. <=200 words.
```

## Main-model advice for the user
The agent cannot switch its own main model; only the user can (model dropdown).
Recommend a switch only when it clearly pays off:
- RED on Claude -> switch to Gemini Pro (or Flash for routine work).
- Long session of T0/T1 work on Claude -> suggest Flash.
- Hard T3 problem while on Flash -> suggest Claude / Gemini Pro for that conversation.
