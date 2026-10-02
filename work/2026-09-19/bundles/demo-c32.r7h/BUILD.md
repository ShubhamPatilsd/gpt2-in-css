# bundles/demo-c32 — the shareable demo: `combined8-c32` (R5X recipe, capacity 32, `--value-layout widths`, R4D flags, R4T chunk 64, R5E, R5H) + R6P (prompt echo fix + typed prompt, N = 4) + R6V (progress UI, smooth fill, font-count loader, early paint); R6L flags off

Built by R6X on 2026-09-30 16:08 with `work/2026-09-19/R6X/compile.sh` (= `R5X/compile.sh` + the R6P and R6V flag passthroughs; tools copy `work/2026-09-19/R6X/tools` =
`R5X/tools` + `R6P/tools-vs-R5X.diff` + `R6V/tools-vs-R5X.diff` (`r6v_progress_ui.py` taken verbatim from `R6V/tools`, R6V's diff predates their `·` fix) + `R6X/apply_conflicts.py`;
full diff vs R5X/tools: `R6X/tools-vs-R5X.diff`, 712 lines; merge log `R6X/merge.log`, report `R6X.md`). Sizes: index.html 7,130,218 B, runtime.css 50,366,464 B; 285 font faces (271 F4 + 12 R5H dot + 2 GPT-2 tokenizer).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X
# combined8-c32's exports (bundles/combined8-c32/BUILD.md) plus:
export R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=1 R6P_PROMPT_SLOTS=4 R6P_DEFAULT_PROMPT=
export R6V_PROGRESS_UI=1 R6V_SMOOTH=1 R6V_EARLY_PAINT=1 R6V_FONT_COUNT=1
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-c32 32 12
```

## Asset dependencies (relative url() in runtime.css; `R6L/pack_bundle.py bundles/demo-c32 <out> --br` copies them into <out>/model/fonts/ — dry run: every file resolves)

| faces | path | owner |
|---|---|---|
| 271 | `../../F4/assets/…` (weights, embedding lookup 56.9 MB, head faces) | F4 (via R6X/assets → ../F4/assets) |
| 12 | `../../R5X/assets-r5h/font-vector-operators-r5h/dot-h*-…-f4-r5h.woff2` | R5H's dot fonts, R5X's copies (via R6X/assets-r5h symlink) |
| 2 | `../../R6P/assets-r6p/gpt2-token-id-{0,1}-full.ttf` (1.66 + 1.62 MB) | R6P (via R6X/assets-r6p symlink) |

## Merge-specific behaviour (R6X/apply_conflicts.py; see R6X.md §1)

- Layout: R6P's prompt panel (top 52 px) + token readout (118) keep their places; R6V's loading/progress row moves from 52 to 146 px and the output text from 146 to 184 px (`r6v.TOP_PX = 146`, `r6p.OUTPUT_TOP = 184`, set at import when both flags are on).
- Early paint: R6V's inline <head> style also carries the 4 visual rules of the prompt panel (`.tk-panel`, `.tk-panel label`, `.tk-editor`, `.tk-editor:focus`) and its lock selector is `body>:not(.controls):not(.ld):not(.tk-panel){content-visibility:hidden}` (lifted by the last rule of runtime.css), so controls, editor and loading panel are all visible before the stylesheet arrives.
- Everything else is the owners' code unchanged; all-new-flags-off (`R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0 R6V_PROGRESS_UI=0`) reproduces `bundles/combined8-c32` byte for byte; `R6V_PROGRESS_UI=0` reproduces `bundles/combined8-c32-prompt`; `R6P_*=0` reproduces `bundles/combined8-c32-ui` (R6X.md §2).

## Flags: see `bundles/combined8-c32-prompt/BUILD.md` (R6P_*) and `bundles/combined8-c32-ui/BUILD.md` (R6V_*); base flags as `bundles/combined8-c32/BUILD.md`.

## Verification: R6X.md §2 (offline) and §6 (Chrome, gated); READY is created by `R6X/run_chain.sh` only on the ids checks passing.

## v2 (2026-09-30 19:23:54, R6X) — layout-only rebuild
Rebuilt with the same recipe after `R6X/apply_conflicts.py` edit 4: ONE extra rule at the end of runtime.css, `html .visible-output{bottom:96px;overflow:auto}` (the output text is bounded above the fixed footer `.tk-aside` and scrolls when longer; before, 2+ output lines overlapped the footer in short windows). `R6X/compare_rules.py` vs the v1 build: index.html byte-identical, rule multiset + order identical except that one rule (`R6X/logs/compare_rules-demo-c32-v2.log`). The v1 ids results (READY) therefore transfer; v2 re-verification: R6X.md §7.

## v3 (2026-09-30 20:06:35, R6X) — display-only rebuild (layout fix + head-phase segment)
Rebuilt with the same recipe after `R6X/apply_conflicts.py` edit 4: ONE extra rule at the end of runtime.css, `html .visible-output{bottom:96px;overflow:auto}` (the output text is bounded above the fixed footer `.tk-aside` and scrolls when longer; before, 2+ output lines overlapped the footer in short windows). `R6X/compare_rules.py` vs the v1 build: index.html byte-identical, rule multiset + order identical except that one rule (`R6X/logs/compare_rules-demo-c32-v2.log`). Plus the 13th bar segment for the vocabulary-head phase (,  fill over an estimated 2.8 s + opacity pulse, label "vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"; transform/opacity only). The v1 ids results (READY) therefore transfer; re-verification: R6X.md §7.

## v4 (2026-09-30 21:15:58, R6X) — display-only rebuild (robust output sizing + footer placement; head-phase segment)
Rebuilt with the same recipe after `R6X/apply_conflicts.py` edit 4: two sizing rules at the end of runtime.css, `html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto}` (the output box is its content, never shorter than 4 lines, never taller than the window allows above the footer; scrolls when longer) and `html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto}` (the footer sits right below the output's maximum extent — off-screen in windows shorter than ≈320 px, never overlapping; v2/v3's `bottom:96px` clipped the box to ≤ 20 px in such windows). `R6X/compare_rules.py` vs the v1 build: index.html byte-identical, rule multiset + order identical except that one rule (`R6X/logs/compare_rules-demo-c32-v2.log`). Plus the 13th bar segment for the vocabulary-head phase (,  fill over an estimated 2.8 s + opacity pulse, label "vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"; transform/opacity only). The v1 ids results (READY) therefore transfer; re-verification: R6X.md §7.

## v5 (2026-10-01 11:03:00, R6X) — typed-prompt arming fix (token-fresh embedding receipt, sticky arming, no latch, editor locked from the click, Run after Ready, echo from the model-facing values)
Rebuilt with the same recipe after `R6X/apply_conflicts.py` edit 6 (R6X.md §10: the typed prompt could be shown while the model ran the dropdown prompt — the embedding receipt stamped only the epoch, so layer 0 could consume the idle dropdown embedding; plus the 86,400 s latch could freeze pre-armed values). Model core rules identical (`R6X/check_v5_identity.py`). Also v4's two sizing rules at the end of runtime.css, `html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto}` (the output box is its content, never shorter than 4 lines, never taller than the window allows above the footer; scrolls when longer) and `html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto}` (the footer sits right below the output's maximum extent — off-screen in windows shorter than ≈320 px, never overlapping; v2/v3's `bottom:96px` clipped the box to ≤ 20 px in such windows). `R6X/compare_rules.py` vs the v1 build: index.html byte-identical, rule multiset + order identical except that one rule (`R6X/logs/compare_rules-demo-c32-v2.log`). Plus the 13th bar segment for the vocabulary-head phase (,  fill over an estimated 2.8 s + opacity pulse, label "vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"; transform/opacity only). The v1 ids results (READY) therefore transfer; re-verification: R6X.md §7.

## v6 (2026-10-01 13:21:18, R6X) — headed-Chrome id-readback fix (R7H): `.feedback-scroller{scrollbar-width:none}`; plus v5's typed-prompt arming fix
Rebuilt with the same recipe after `R6X/apply_conflicts.py` edit 7 (R6X.md §11: in headed Chrome with macOS "Show scroll bars: Always" the classic 15 px scrollbar inside `.feedback-scroller` (524288 px scrollport hardcoded in the id decode, 8 px per id) biased every read-back id ≥ 9283 by +1 — found by R7H; headless harness runs cannot see it) and edit 6 (R6X.md §10: the typed prompt could be shown while the model ran the dropdown prompt — the embedding receipt stamped only the epoch, so layer 0 could consume the idle dropdown embedding; plus the 86,400 s latch could freeze pre-armed values). Model core rules identical (`R6X/check_v5_identity.py`). Also v4's two sizing rules at the end of runtime.css, `html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto}` (the output box is its content, never shorter than 4 lines, never taller than the window allows above the footer; scrolls when longer) and `html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto}` (the footer sits right below the output's maximum extent — off-screen in windows shorter than ≈320 px, never overlapping; v2/v3's `bottom:96px` clipped the box to ≤ 20 px in such windows). `R6X/compare_rules.py` vs the v1 build: index.html byte-identical, rule multiset + order identical except that one rule (`R6X/logs/compare_rules-demo-c32-v2.log`). Plus the 13th bar segment for the vocabulary-head phase (,  fill over an estimated 2.8 s + opacity pulse, label "vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"; transform/opacity only). The v1 ids results (READY) therefore transfer; re-verification: R6X.md §7.
