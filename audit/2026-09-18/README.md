# Audit run 2026-09-18

Goal: understand why the pure HTML+CSS GPT-2 effort plateaued, where bytes / wall-clock /
memory actually go, and which atomic optimization would propagate furthest.

Every subagent writes two files here:

- `<id>-<slug>.md`      the report (findings with evidence citations)
- `<id>-<slug>.log.md`  append-only process log: every file opened / command run, one line each,
                        with why, in order. This is how the orchestrator audits the agent.

Agents are read-only with respect to the rest of the repo and ~/.codex.

## Index (2026-09-18 run)

Start with `SYNTHESIS.md`. Then:

| Report | What it covers |
|---|---|
| S0–S7-sessions-*.md | Codex session digests, Aug 24 – Sep 18 (S0 = Mar–Jul, empty: project began Aug 24) |
| E1–E6-experiments-*.md | Catalog of all 451 entries under experiments/, by mechanism family, with verdicts |
| C1-cost-model.md | Structural cost model of the TinyStories pipeline (bytes re-evaluated per stage) |
| C2-demo-cost-model.md | Structural cost model of the 12-layer GPT-2 demo (where state lives, dirtied bytes per pass) |
| P1-profile.md | Chromium trace of the TinyStories page (97.5 % style; shipped page cannot generate) |
| P2-trace.md | Passive Chromium trace of the 12-layer demo (40.7 s/token; per-pass element histogram) |
| M1-microbench.md + M1-microbench/ | 81 isolated Blink style-cost benchmarks: the per-element / per-byte law, what stops the cascade, passes per boundary, retained animations |

Each `<id>.log.md` beside a report lists every file opened and command run by that agent.
