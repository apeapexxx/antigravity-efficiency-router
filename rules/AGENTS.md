# Efficiency Router (always-on)

Goal: maximum useful work per unit of quota. Premium tokens (Claude) are scarcest
and on a separate fixed limit; Gemini Flash is cheapest. Never mention tiers to
the user unless asked.

## 1. Triage each request silently
- **T0 Trivial** - chit-chat, known fact, one-line answer/edit. Answer directly; no tools unless required, no artifacts, no plans.
- **T1 Mechanical** - finding code, reading many files, web/doc research, summarizing logs/diffs, boilerplate, format conversion, bulk edits.
- **T2 Standard** - well-specified feature, bug with clear repro, refactor covered by tests.
- **T3 Hard** - architecture, ambiguous design, subtle/concurrency/security bugs, high blast radius.

## 2. Routing matrix
Each turn a `[router] main=<bucket>/<tier> | 5h x% . 7d y% | LEVEL | task~Tn [| ESCALATE?|DOWNSHIFT-OK]`
line is injected. `task~Tn` is a zero-cost keyword heuristic; your own triage wins.
If absent, assume `premium` / `GREEN`.

| main tier | GREEN | YELLOW | RED |
|---|---|---|---|
| premium (Claude) | T1 -> `flash`; T2-T3 self | T1 -> `flash`, T2 -> `pro`; self = plan + review; terse | Delegate all execution; self = final check only. Tell the user ONCE to switch the main model to Gemini. |
| strong (Gemini Pro) | T1 -> `flash`; T2-T3 self | same, terse | same; suggest Flash for T0-T1 |
| cheap (Flash) | T0-T2 self; T3: get a `pro` subagent analysis before committing | same | same |

Subagent `Model`: `flash_lite` = pure lookup/extraction - `flash` = research, reading, boilerplate - `pro` = implementation/analysis needing judgment - `inherit` = only when the main model is truly required.

### Fully Autonomous Mode (Zero-touch)
- **T3 on cheap main (Flash)**: **DO NOT interrupt the user or ask them to switch models.** Immediately spawn a `pro` subagent via `invoke_subagent` (`Model: "pro"`, `TypeName: "research"` for architecture/analysis or `TypeName: "self"` for implementation). Let `pro` solve the hard problem, receive its synthesis, and present the final answer seamlessly.
- **Claude as main**: If the user chose Claude manually, Claude handles T2-T3 directly and delegates T1 to `flash` subagents.
- Never prompt the user to manually flip dropdowns unless they explicitly ask for Claude.

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
