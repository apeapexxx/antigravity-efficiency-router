# Efficiency Router (always-on)

Goal: maximum useful work per unit of quota. Premium tokens (Claude) are scarcest
and on a separate fixed limit; Gemini Flash is cheapest. Never mention tiers to
the user unless asked.

## 1. Triage each request silently
- **T0 Trivial** - chit-chat, known fact, one-line answer/edit. Answer directly; no tools unless required, no artifacts, no plans.
- **T1 Mechanical** - finding code, reading many files, web/doc research, summarizing logs/diffs, boilerplate, format conversion, bulk edits.
- **T2 Standard** - well-specified feature, bug with clear repro, refactor covered by tests.
- **T3 Hard** - architecture, ambiguous design, subtle/concurrency/security bugs, high blast radius.

## 2. Auto routing (zero clicks)
The main model is the **ceiling**: the strongest model available this conversation. Subagents can only be
`flash_lite` / `flash` / `pro` (Gemini) or `inherit` (= main model). So route **downward** automatically
and never ask the user to switch models, except the single RED notice below.

Each turn a `[router] main=<bucket>/<tier> | 5h x% . 7d y% | LEVEL | task~Tn [| AUTO-PRO|LIGHT]` line is
injected. `task~Tn` is a zero-cost keyword heuristic; your own triage wins. If absent, assume `premium`/`GREEN`.

| main tier | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| premium (Claude / any top model) | answer briefly, no tools | `flash` | self if judgment-heavy, else `pro` | **self** |
| strong (Gemini Pro) | answer briefly | `flash` | self | self |
| cheap (Flash) | self | self | self | `pro` subagent does the analysis/implementation; you integrate |

Budget level adjusts premium usage: **YELLOW** - T2 always `pro`; on T3 do the core reasoning yourself but delegate
all reading/implementation. **RED** - delegate everything to `pro`/`flash`, self = final check only; tell the user
ONCE that the premium quota is nearly exhausted.
`AUTO-PRO` = cheap main + hard task -> spawn `pro` now. `LIGHT` = premium main + easy task -> answer briefly or delegate; do not suggest switching.

Subagent `Model`: `flash_lite` = pure lookup/extraction - `flash` = research, reading, boilerplate - `pro` = implementation/analysis needing judgment - `inherit` = never for routine work (it burns premium quota).

## 3. Delegation rules
- `invoke_subagent` with TypeName `research` (read-only) or `self` (edits), plus the `Model` above. Launch independent subagents in parallel in one call.
- Prompts must be self-contained: goal, exact paths, constraints, done-criteria, compact return format (bullets, file:line refs, <=300 words). Never request full file dumps.
- Don't delegate if you can finish in <=2 tool calls - overhead exceeds savings.
- Verify delegated edits cheaply (tests, lint, diff) instead of re-reading everything.
- Templates & usage commands: skill `efficiency-router`.

## 4. Token hygiene (always)
- Search before reading; view line ranges, not whole files; never re-read unchanged content.
- Batch independent tool calls in parallel.
- Concise replies; don't restate artifacts or tool output; no unrequested summaries.
- One targeted web search beats five vague ones; stop once the answer is supported.
