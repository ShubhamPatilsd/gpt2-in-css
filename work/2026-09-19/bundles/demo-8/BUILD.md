# bundles/demo-8 — round 8 (R8U): production page layout on the round-7 bundle (model, controls and handshakes unchanged)

Built by R8U on 2026-10-02 with `work/2026-09-19/R8U/compile.sh` (= `R7X/compile.sh` + the `R8U_LAYOUT` passthrough, default 1; tools copy
`work/2026-09-19/R8U/tools` = `R7X/tools` + `r8u_layout.py` + module constants `PANEL_TOP`/`TOKENS_TOP` (r6p_prompt.py) and `WARN_TOP`
(r7h_id_guard.py) whose defaults are the old literals + the R8U block in `browser_gpt2_runtime.py`). `R8U_LAYOUT=0` rebuilds the round-7 bundle
byte for byte (index.html + runtime.css; R8U.md §2).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U
export R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32 R7H_ID_GUARD=1 R6X_SCROLLBAR_FIX=1 R8U_LAYOUT=1
./compile.sh <out> 8 12
```

Layout (R8U.md §1): title "GPT-2 in CSS" + one muted line (status small at the top right); one row "Prompt [dropdown] or type: [the
unchanged `.tk-root { --draft-prompt: "…"; }` editor] [Run / continue] [Reset]"; token chips under the editor; a quiet native
`<details>` "Options ▸" line with Seed / Sampling / readout; small progress line + 4 px bar; generated text 22 px; footer = practical notes.
DOM of .controls unchanged except one `<details class="r8u-opt">` after Reset; new body child `<header class="r8u-head">` (exempt from the
early-paint lock, styled inline). Offline: model core rules identical in multiset and order (R8U/check_layout_diff.py), witnesses identical,
static no-JS rc 0, pack dry-run resolves every url(). Previous BUILD.md (round 7) follows.

---

# bundles/demo-8 — the capacity-8 twin of demo-c32 (round 7): R7B features (stop rule → 8 steps in total incl. prompt tokens, prefill head skip, sampling controls) + R7H id guard, on demo-8 v6

Built by R7X on 2026-10-01 18:06 with `work/2026-09-19/R7X/compile.sh` (tools `R7X/tools` = `R7B/tools` + R7H guard hook; see `bundles/demo-c32/BUILD.md`). Sizes: index.html 6,668,962 B, runtime.css 39,512,652 B; 286 font faces.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7X
# demo-8 v6's exports (bundles/demo-8.prev/BUILD.md) plus:
export R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32
export R7H_ID_GUARD=1 R6X_SCROLLBAR_FIX=1
./compile.sh /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-8.next 8 12      # VALUE_LAYOUT=runs (default), R4S default
```

Stop rule at capacity 8 (manifest `r7bStops`): N = 0/1 → 8 new tokens, N = 2 → 7, N = 3 → 6, N = 4 → 5 (always stop at epoch 8). Guard: 8 agreement gates + calibration. Assets as demo-c32 (4 owners, 286 url()s, all resolve). Differences vs `bundles/demo-8.r7b` (R7B's cap-8 bundle, built 14:16): exactly the guard rules/elements plus R7B's own later `.pg{display:none!important}` stop-rule fix (R7X/logs/guard-diff-demo-8-next.log). R7B flags off reproduces `bundles/demo-8.r7h` byte for byte.

Verification: R7X.md (offline §2; Chrome §3: dropdown Hello 8/8 headless). READY only after the Chrome check passes. Previous live bundle history: `bundles/demo-8.prev/BUILD.md`.

## Verification status (R7X, 2026-10-01 21:17:34) — PASS, swapped in as bundles/demo-8
Dropdown Hello headless **8/8**, guard `--fb-ok` 1 / 8 agreement gates 1, "Complete • 8 new tokens" (R7X/run-demo-8.next/hello-headless; 194 s on battery — timing not comparable). Offline: R7X.md §2.
