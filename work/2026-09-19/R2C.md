# R2C — hoist per-axis arithmetic out of consumer `font-variation-settings` lists

Agent R2C, 2026-09-19. Base = `work/2026-09-19/F4/tools` (F2+F5+F4, the `combined` bundle). Tools copy: `work/2026-09-19/R2C/tools`
(+ `experiments`, `data`, `global-projection-assets -> ../F2/…`, `assets -> ../F4/assets` symlinks). Bundles: `work/2026-09-19/bundles/R2C`
(all hoists) and `bundles/R2C-qonly` (`R2C_HOIST_STAGES=0`: query + embedding hoists only; offline-verified, not Chrome-run, no READY).
Log: `R2C.log.md`. Nothing under repo `tools/` or `experiments/` was edited; no commits.

## 1. Inventory of every `font-variation-settings` list in `bundles/combined` (`R2C/inventory.py`, `inventory-combined.json`)

Cost model: M1 MB5 (SYNTHESIS §8.3) per declaration = 0.72 µs floor + 0.19 µs per `var()` + ≈3.4 µs per 16 typed-calc terms (≈0.43 µs for a
2-term quotient). "Restyles/token" from the combined trace histogram (`bench/combined.md`): the four stage subtrees are the 3,089 / 2,934 /
784-element passes (≈16 per token each, ≈1.3 per layer: gate opening + each landing chunk of the upstream consumer); the attention side-branch
(`.fvs-query` + banks + 96 score glyphs) is the 126-element pass (16/token); the V-glyph subtree is the 6,919-element pass (16/token).

| hop (element) | elements | entries | per-entry shape | var()+calc per element | est. µs per restyle (MB5) | restyles / token | est. ms / token |
|---|---:|---:|---|---:|---:|---:|---:|
| `.shared-qkv` (LN1 out → QKV shard fonts) | 1 | 768 | `"A000" calc(var(--n1-000) / var(--range-qkv))` | 1,536 + 768 | ≈620 | 16 | ≈10 |
| `.shared-attn` (ctx → attn-proj shards) | 1 | 768 | `calc(var(--ctx-i) / var(--range-attn))` | 1,536 + 768 | ≈620 | 16 | ≈10 |
| `.shared-fc` (LN2 out → fc shards) | 1 | 768 | `calc(var(--n2-i) / var(--range-fc))` | 1,536 + 768 | ≈620 | 16 | ≈10 |
| `.shared-proj` (hidden → 12 global-axis proj shards) | 1 | 3,072 | `calc(var(--hidden-i) / var(--range-proj))` | 6,144 + 3,072 | ≈2,500 | 16 | ≈40 |
| `.fvs-score-H-S` (score glyphs) | 96 | 2 → 832 after substitution | `var(--fr-k-S)` (768 numeric, F4) + `var(--fvs-query-H)` = 64 × `calc(var(--qkv-i) / var(--fqs-H))` re-parsed PER GLYPH | 2 + 64 calc | ≈190 × 96 ≈ 18,000 | 16 | ≈290 |
| `.fvs-v-H-S` (V glyphs) | 6,144 | 2 → 769 | `var(--fr-v-S)` (numeric) + `"P000" var(--fw-H-S)` — already var-only (F2) | 2 + 0 | MPC-shared (96 groups) | 16 | — |
| `.embedding-source` | 1 | 2 | `round(down,calc(var(--token) / 256),1)`, `mod(var(--token),256)` | 2 + 1 | ≈2 | 1 | 0 |
| `.full-head`, `.head-fine` | 1 + 257 | 1 | `var(--head-fvs)` (F4 hoisted; 768 pre-rounded integers) | 1 + 0 | — | 1.4 | — |
| `.core-reset`, `.head-isolation`, `.position-embedding`, `.font-witness` | — | — | `normal` | 0 | — | — | — |

Findings from the inventory:
1. The combined bundle has NO `round(calc(var()))` list left (F4 already hoisted the head's); the remaining arithmetic is one 2-term quotient
   per axis (`value / dynamic range`), where `--range-kind` = `max(.000001, abs(var(--in-0)), …, abs(var(--in-767))) * 1.001` is declared on the
   SAME element as the list and depends on the whole input vector — so the quotient cannot be folded into the input's own expression
   (`--n1-i`, `--ctx-i`, `--hidden-i`), it can only be moved to a separate typed declaration.
2. The publisher of every stage input (`.shared-ln1/ln2`, the bridge / fc consumers) is an ANCESTOR of the list element and is restyled in
   exactly the same passes (an inherited custom-property change dirties the whole subtree, M1 MB2a). Hoisting therefore does not change how
   often the quotients are evaluated for the four stage lists; it changes only the FORM (768 typed declarations + a var()-only list instead of
   768 calc() entries inside one declaration). At MB5 rates that is a wash or a small loss: 768 × (0.72 + 0.81) + 768 × 0.19 ≈ 1.3 ms vs ≈0.62 ms.
3. The one population where a hoist removes work is `--fvs-query-H`: its 64 quotients were substituted as `calc(a / b)` tokens into 8 score
   glyphs per head (one per slot) and re-parsed on each — 6,144 calc parses per attention restyle, replaced by 768 typed declarations.
4. Summing the table, ALL list arithmetic in `combined` is ≈0.36 s/token at MB5 rates (≈1.2 % of 30.3 s). The 7.7 s / 316 µs-per-element of
   the 100–999-element passes is therefore NOT list arithmetic. What those passes contain: the 126-element pass = 96 score glyphs each with
   a UNIQUE 832-axis `font-variation-settings` (its own slot's K list + its head's Q list) → 96 distinct Font instances resolved per pass;
   the 357 / 484 / 485-element passes (≈250 ms each, 0.7 ms/element!) and the 784-element pass (132 ms) are 768-carrier stages whose
   `i.metric` carriers each hold a unique inline `view-timeline` (no MPC sharing, timeline bookkeeping per carrier). That is round-2 target 2/4
   territory (frames, timelines), not this fix.
5. No `@function` call remains (`--gelu` is defined once, never invoked) and no `var()`-of-constant exists on the list-carrying elements
   (step 3 of the brief: nothing to do).

## 2. What was hoisted (flag `R2C_HOIST_FVS`, default ON; sub-flags `R2C_HOIST_STAGES` / `R2C_HOIST_QUERY` / `R2C_HOIST_EMBEDDING`)

| population | file:line (`work/2026-09-19/R2C/tools`) | change |
|---|---|---|
| helper | `r2c_hoist.py` (new) | flags; `hoist_settings()` rewrites every `"TAG" calc(var(a) / var(b))` entry to `"TAG" var(--fq-…)` and returns the matched expression VERBATIM as the declaration text (raises if any entry does not match); `private_regs()` registers each name once as `<number>` `inherits:false`; `lift_stage_rules()` keeps one copy of the layer-identical stage rules outside the `@container runtime style(--layer:L)` blocks |
| 4 stage lists | `build_hybrid_twelve_block.py:137-155` (`settings()` hoists when `dynamic_range`), `:221-227` (emits regs + `.{stem}{--fq-kind-idx:calc(var(--in-idx) / var(--range-kind));…}` once per matvec, asserts all inputs covered); `browser_gpt2_reused_core.py:82-85` (`specialize()` lifts + dedupes the rule) | `.shared-qkv/attn/fc{…"A000" var(--fq-qkv-000)…}`, `.shared-proj{…"X000" var(--fq-proj-0000)…}`; declarations `--fq-{qkv,attn,fc}-000..767`, `--fq-proj-0000..3071` on the same element |
| 12 query lists | `browser_gpt2_font_vector_cache.py:205-213` | `.fvs-query{--fq-q-H-i:calc(var(--qkv-…) / var(--fqs-H))}` × 768, `--fvs-query-H:"Q000" var(--fq-q-H-0),…` (F4's `--fvn` pattern) |
| embedding | `browser_gpt2_embedding.py:33-45, 62, 67` | `.embedding-source{--fq-token-group:round(down,calc(var(--token) / 256),1);--fq-token-local:mod(var(--token),256)}`, list `"GRUP" var(--fq-token-group),"LOCL" var(--fq-token-local)` |
| wall / manifest | `browser_gpt2_runtime.py:305-306` (`.head-isolation` wall exempts `--fq-*`), `browser_gpt2_reused_adapter.py:224-227` (`r2cHoistFvs/Stages/Query/Embedding`) | |

Design decisions (deviations from the brief, with reasons):
- The typed numbers live on the SAME element as the list (`inherits:false`), not on the parent publisher: same restyle set (§1.2), no growth of
  every descendant's inherited-variable map (round-2 target 5), no `:initial` wall / `.core-reset` entries needed, and same-element custom
  property dependencies are already used by F4's `--fvn-*`.
- Names `--fq-<kind>-<idx>` (`--fq-` prefix; distinct from the pre-existing `--fqs-H` query scales). proj uses 4-digit indices.
- Constants stay literal (`256`, `.000001`, `1.001`); `--range-*` and `--fqs-*` rules are untouched.
- Rounding point: the double operations and their order are unchanged (the declaration text IS the original entry text). The one new
  rounding is Blink's 6-significant-digit serialisation of the typed number when `var(--fq-…)` is substituted into the list
  (round6(round6(a)/round6(b)) instead of round6(a)/round6(b) evaluated in the list) — ≤5e-7 absolute on a [-1, 1] axis coordinate, below
  the 16.16 / F2Dot14 axis quantisation, the same 1e-6 class F4 §6 documents for the numeric K/V entries (exact integers, as in the head hoist,
  are not available here because the range is dynamic).

## 3. var()/calc counts before → after

| element | per restyle, combined | per restyle, R2C | Δ declarations |
|---|---|---|---|
| `.shared-qkv` / `-attn` / `-fc` (each) | list: 1,536 var + 768 calc | list: 768 var + 0 calc; + 768 typed decls (1,536 var + 768 calc) | +768 |
| `.shared-proj` | list: 6,144 var + 3,072 calc | list: 3,072 var + 0 calc; + 3,072 typed decls (6,144 var + 3,072 calc) | +3,072 |
| `.fvs-query` (12 lists) | 12 × (128 var, 64 calc tokens, unevaluated `*`) | 768 typed decls (1,536 var + 768 calc) + 12 × 64 var | +768 |
| each `.fvs-score-H-S` (×96) | 2 var → 768 numbers + **64 calc parsed** | 2 var → 832 numbers, **0 calc** | 0 |
| `.embedding-source` | 2 var + 1 calc + round + mod | 2 var; 2 typed decls | +2 |

Per token (16 restyles of each stage subtree, 16 of the attention branch): calc() evaluations 16 × (3×768 + 3,072 + 96×64) = 184k → 16 × (3×768 +
3,072 + 768) = 98k (−47 %); var() substitutions 16 × (3×1,536 + 6,144 + 96×2 + 12×128) = 197k → 16 × (3×(1,536+768) + (6,144+3,072) + 1,536 + 768 + 192) = 297k
(+51 %); declarations +5,376 per stage-restyle set. Estimated at MB5 rates: stage lists +78 ms/token, query hoist −26 ms/token → R2C ≈ +50 ms/token,
R2C-qonly ≈ −26 ms/token — both inside the ±20 % bench noise. The expected benchmark outcome is "no measurable change"; if B0 sees a
difference, it measures Blink's per-form costs, not a reduction in work. Sheet: 41,666,858 B → 40,927,799 B (−0.7 MB); 6,146 new registrations.

## 4. Verification

- Offline (`R2C/offline_check.py`, logs `offline_check-R2C.log`, `offline_check-R2C-qonly.log`, both `RESULT: ok`): (a) hoist identity — 61 lists, 65,282
  entries: every R2C entry is `"TAG" var(--fq-…)` with combined's tag, every `--fq-…` is declared exactly once on the list's element, and all
  65,282 declaration expressions are byte-identical to combined's entry arithmetic; no `calc(`/`round(`/`mod(` left in any hoisted list;
  (b) 6,146 `@property --fq-* <number> inherits:false`, no duplicates, registered set == declared set, no `--fq-*:initial` anywhere (wall clean),
  one top-level hoist rule per stage; (c) selector-level diff combined → R2C limited to the 4 stage list rules (12 → 13 each), `.fvs-query`
  (12 → 24), `.embedding-source` (1 → 2) and the `@property` additions; (d) 283 font witnesses identical (keys modulo the tools-copy dir),
  index.html byte-identical. `launch_browser_gpt2.py --check`: 285 static files / 286,719,849 B. NumPy reference (`R2C/reference_ids.py`,
  `reference_ids.log`): `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected.
- Chrome 153 correctness run (`R2C/run_correctness.sh R2C`, F4's passive harness with R2C paths; under `CHROME.lock` after a 675 s wait;
  02:53–02:58; NOT a timing run): **ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = required, 8/8 done markers**; `verify_browser_gpt2_runtime.py`
  rc=0: tokenAgreement 8/8, originalFloatAgreement 8/8, finalHeadMatchesActualInput (winner 1101), finalResidual rmse 0.0201 / max 0.187
  (combined: 0.0193 / 0.187), 96 packed KV slots complete, max cache rmse 0.00387 / max abs 0.0184 (combined: 0.00291 / 0.0181) — the
  expected 1e-6-class shift from the extra 6-digit serialisation (§2), same acceptance as F4. Head list read back as exact integers
  (`"X000" -12,…`). Capture deltas 28–37 s/token (5 s poll; correctness pacing only). **READY created 02:58** (`bundles/R2C/READY`), with
  the note that per R2A R7 / §1.4 the change cannot move the token; `bundles/R2C-qonly` has no READY (not Chrome-run).

## 6. Pivot (coordinator, 02:5x): R2E hop-gated view-timelines — design report only

Written to `work/2026-09-19/R2E-design.md` before building anything, as requested. Verdict: the hop-gating as specified is not
semantics-preserving (every hop's animated outputs are live `var()` dependencies of all downstream hops until the `--loop-phase` flip at
frame F latches `--saved`; a detached/`none` timeline makes the animation's current time unresolved → outputs revert to 0 → `--out` is
wrong before it is latched), and even with perfect semantics the per-cycle toggling cost (≈60–100 µs per timeline: ViewTimeline
re-creation + pending-animation updates + carrier restyle) exceeds the ≈11 µs × frames-off saving for every compute population (needed
6 of 7 frames per layer). Only pause-and-hold (paused animations keep a hold time across timeline removal, if Blink preserves it) could
work: best case ≈ −3 s/token (not −6 to −7), conditional on three Blink behaviours a 1k-carrier fixture must confirm first. No smoke
bundle built; go/no-go requested.

## 5. Residual risks / follow-ups

- Numerics: the extra 6-digit serialisation of every axis coordinate (§2) is the same class as F4's numeric lists; 8/8 ids in the Chrome run is
  the acceptance, not bit-identity with `combined`. `R2C_HOIST_FVS=0` reverts to `combined` exactly.
- Performance: per §1.2–1.4 the stage hoist is expected to be neutral or slightly negative and the query hoist slightly positive; both are
  ≈0.1–0.3 % of the token. If B0 has one slot, bench `R2C-qonly` (one Chrome run needed first) or treat `R2C` as a form-test. The real cost of the
  100–999-element passes (96 unique score-glyph font instances; 768 carriers with unique inline view-timelines at ≈0.17–0.7 ms each) is
  untouched and belongs to round-2 targets 2 and 4.
- 6,146 additional `@property` registrations (all `inherits:false`) — relevant to round-2 target 5 (registration tax) if that micro-benchmark
  finds a per-registration cost.
- The `lift_stage_rules()` regex assumes the exact declaration shape it generates; the emitter asserts coverage (`len(hoisted) == len(source)`)
  and the offline check asserts one top-level rule per stage, so a silent partial lift cannot pass.
