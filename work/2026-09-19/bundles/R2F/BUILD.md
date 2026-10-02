# bundles/R2F — combined (F2 + F5 + F4) + R2F lean layer handshake

Built by R2F on 2026-09-19 06:11 (`work/2026-09-19/R2F/compile.sh R2F 12 8`, 21.4 s; flags as `bundles/combined/BUILD.md` plus
`R2F_LEAN_HANDSHAKE=1` (default ON; `=0` restores the SMIL relay and reproduces `bundles/combined` byte-for-byte apart from tools-copy paths).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2F
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1 R2F_LEAN_HANDSHAKE=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R2F
```

## What changed in the emitted bundle (vs `bundles/combined`)

| | combined | R2F |
|---|---|---|
| layer handshake | D pass 2: `--loop-ack:1` on `.loop-input` → `#loop-ready-P{animation:loop-pulse 1ms}` → E: pulse ends → SMIL `#loop-captured-P.done` → F: `:has()` → `--loop-captured-pass`/`--loop-held` + `#loop-ack-P` pulse → G: pulse ends → SMIL `#loop-advanced-P.done` → A: `:has()` → `--pass:P+1` → S1 | D pass 2: `.core-pass-reader` (new wrapper above `.core-controller`) reads the two bank pass markers through the existing `--loop-t-{0,1}-768` view-timelines; `.core-controller{--pass:min(calc(max(marker0,marker1) + 1),var(--pass-cap))}` → S1 of the next layer in the same pass |
| token boundary | `:where(body:has(#token-k-advanced.done)) .core-controller{--pass:12k+1}` | `…{--pass-cap:12(k+1)}` (`--pass-cap:12` initially; `<number>`, inherits:false) |
| removed | — | 96 ready-pulse rules, 96 captured rules, 95 ack-pulse rules, 95 advance rules, 2 `--loop-held` bank rules, 2 `--loop-ack` calcs; 384 `<g>` + 192 `<set>` SMIL elements (`svg.loop-signals` kept, empty) |
| elements / rules / registrations | 69,522 / 23,192 / — | 68,947 (−575) / 22,823 (+12 −381) / +1 (`--pass-cap`) |
| `@font-face`, font witnesses, all stage/bank/head rules | identical (`R2F/offline_check.py R2F combined`: PASS) | |

Invariant kept: the write bank's marker `--saved-b-768:var(--native-pass)` is declared in the same rule as the 768 output values and is
laid out / snapshotted / latched (base 86400 s transition list) together with them, so `max(markers)` reads P exactly when P's output is
readable — the same fact `--loop-ack` encoded. The pass advance closes every stage gate in that recalc (receipt `--epoch` ≠ stamp), so the
banks, which sit under the proj gate, are not restyled until the next proj readback (as before: the 769 latch transitions start/cancel in
frame D, R2A §5). Chrome correctness run (2026-09-19 10:07, battery, passive): ids 8/8 = reference, finalResidual rmse identical to `combined` — `work/2026-09-19/R2F.md` §5; READY created.

## Tools copy

`work/2026-09-19/R2F/tools` = `work/2026-09-19/F4/tools` + `r2f_lean_handshake.py` + 4 hunks in `browser_gpt2_reused_adapter.py`
(import; `apply_css`/`apply_body` after `compile_reused`, token loop skipped; `wrap_controller`; manifest flag). Symlinks beside the copy:
`data`, `experiments`, `global-projection-assets -> ../F2/global-projection-assets`, `assets -> ../F4/assets`.

## `diff -ruN -x __pycache__ work/2026-09-19/F4/tools work/2026-09-19/R2F/tools`

```diff
diff -ruN -x __pycache__ work/2026-09-19/F4/tools/browser_gpt2_reused_adapter.py work/2026-09-19/R2F/tools/browser_gpt2_reused_adapter.py
--- work/2026-09-19/F4/tools/browser_gpt2_reused_adapter.py	2026-09-18 19:38:03
+++ work/2026-09-19/R2F/tools/browser_gpt2_reused_adapter.py	2026-09-19 03:07:17
@@ -11,6 +11,7 @@
 import f4_packing as f4
 import f5_scoping as f5
 from browser_gpt2_reused_core import compile_reused
+import r2f_lean_handshake as r2f
 
 
 def compile_reused_runtime_core(
@@ -50,7 +51,14 @@
         "@container runtime style(--layer:0){.loop-input{--loop-ready:1;",
         "@container runtime style(--layer:0){.loop-input{--loop-ready:var(--embed-ready);",
     )
+    if r2f.LEAN_HANDSHAKE:
+        # R2F: the controller reads the bank pass markers itself; no SMIL relay,
+        # no pulse-end / pass-advance frames. Token boundaries raise --pass-cap.
+        css = r2f.apply_css(css, blocks, capacity)
+        body = r2f.apply_body(body)
     for token in range(1, capacity):
+        if r2f.LEAN_HANDSHAKE:
+            break
         step = token * blocks
         old = f"body:has(#loop-advanced-{step}.done){{--pass:{step + 1}}}"
         new = f"body:has(#token-{token}-advanced.done){{--pass:{step + 1}}}"
@@ -183,8 +191,10 @@
         '<div class="core-controller"><div class="core-block" id="block-0">'
         + body
         + "</div></div>"
-        + receiver
     )
+    if r2f.LEAN_HANDSHAKE:
+        body = r2f.wrap_controller(body)
+    body += receiver
     metadata = {
         "blocks": blocks,
         "capacity": capacity,
@@ -211,6 +221,7 @@
         "nativeLayerTokenHandshake": True,
         "privateLayerControl": True,
         "localLayerContainer": True,
+        "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
diff -ruN -x __pycache__ work/2026-09-19/F4/tools/r2f_lean_handshake.py work/2026-09-19/R2F/tools/r2f_lean_handshake.py
--- work/2026-09-19/F4/tools/r2f_lean_handshake.py	1969-12-31 16:00:00
+++ work/2026-09-19/R2F/tools/r2f_lean_handshake.py	2026-09-19 03:06:35
@@ -0,0 +1,131 @@
+"""R2F (2026-09-19): lean layer handshake — no pulse-end / pass-advance frames.
+
+Flag (default ON): R2F_LEAN_HANDSHAKE=0 restores the SMIL relay
+(ready pulse -> captured -> ack pulse -> advanced -> --pass).
+
+Mechanism (work/2026-09-19/R2A.md §5, §8): per layer the loop needed three
+protocol frames after the data frames A-D: E (ready pulse ends), F (`:has()`
+captured -> --loop-held, ack pulse starts), G (ack pulse ends) before the
+`:has()` advanced -> --pass+1 restyle in the next A. The relay exists only
+because the "write bank has the current pass" fact (`--loop-ack`) lives on a
+descendant of the pass controller and could reach it only through SMIL-driven
+DOM state.
+
+Here the controller reads the two bank pass markers directly: a wrapper above
+`.core-controller` carries two view-timeline animations on the existing
+`--loop-t-{0,1}-768` timelines (scoped on html), the controller inherits the
+two progress values explicitly (private properties, F5 pattern) and computes
+
+    --pass: min(calc(max(marker0, marker1) + 1), var(--pass-cap))
+
+The write bank's marker becomes P in the very style pass / layout that carries
+P's output (both are `--saved-b-*` declarations of the same bank, latched by
+the same 86400 s transition list when the bank turns into the read bank), so
+`--pass` advances in the same snapshot re-run pass that used to set
+`--loop-ack:1` (frame D, pass 2) and S1 of the next layer runs in that pass.
+Token boundaries hold `--pass` at k*blocks through `--pass-cap`, which the
+head's `#token-k-advanced.done` raises (same `:has()` rule as before, different
+declaration). The `--loop-held` arming step is not needed: transitions start
+from the after-change `transition-property`, and the base bank rule already
+lists every `--saved-*` name (the trace shows the 769 latch transitions start
+in frame D, when the proj gate opens, not at the pass advance).
+"""
+
+import os
+import re
+
+
+def flag(name):
+    return os.environ.get(name, "1") not in ("0", "false", "no", "off")
+
+
+LEAN_HANDSHAKE = flag("R2F_LEAN_HANDSHAKE")
+
+# centered carrier decode of loop_parts(..., centered=True): value = (1572864 / (p + 2) - 786432) / 128
+_DECODE = "round(nearest,(1572864 / (var({lp}) + 2) - 524288 - 262144) / 128,1)"
+
+
+def _remove_all(css, pattern, expected=None, what=""):
+    css, count = re.subn(pattern, "", css)
+    if expected is not None and count != expected:
+        raise ValueError(f"R2F: expected {expected} {what}, removed {count}")
+    return css
+
+
+def apply_css(css, blocks, capacity, width=768):
+    """Rewrite the loop_parts() control CSS (still in `body{}` / `var(--pass)` form)."""
+    steps = blocks * capacity
+    # 1. the SMIL relay: ready pulse, captured -> ack pulse, advanced -> pass
+    css = _remove_all(
+        css,
+        r"@container loopreceipt style\(--loop-ack:1\)\{@container loopcontrol style\(--pass:\d+\)\{#loop-ready-\d+\{animation:loop-pulse 1ms both\}\}\}",
+        steps,
+        "ready-pulse rules",
+    )
+    css = _remove_all(
+        css,
+        r"body:has\(#loop-captured-\d+\.done\)\{--loop-captured-pass:\d+\}",
+        steps,
+        "captured rules",
+    )
+    css = _remove_all(
+        css,
+        r"body:has\(#loop-captured-\d+\.done\) #loop-ack-\d+\{animation:loop-pulse 1ms both\}",
+        steps - 1,
+        "ack-pulse rules",
+    )
+    css = _remove_all(
+        css,
+        r"body:has\(#loop-advanced-\d+\.done\)\{--pass:\d+\}",
+        steps - 1,
+        "advance rules",
+    )
+    # 2. the redundant `--loop-held` arming of the write bank
+    css = _remove_all(
+        css,
+        r"@container loopcontrol style\(--loop-held:1\)\{\.loop-bank-[01]\{transition-property:[^{}]*\}\}",
+        2,
+        "held rules",
+    )
+    # 3. `--loop-ack` is no longer read by anything
+    css, count = re.subn(
+        r";--loop-ack:calc\(1 - min\(1,abs\(round\(nearest,\(1572864 / \(var\(--lp-[01]-\d+\) \+ 2\) - 524288 - 262144\) / 128,1\) - var\(--pass\)\)\)\)",
+        "",
+        css,
+    )
+    if count != 2:
+        raise ValueError(f"R2F: expected 2 --loop-ack declarations, removed {count}")
+    # 4. the controller: pass = min(max(markers) + 1, cap)
+    old = "body{--pass:1;container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2);--loop-held:calc(1 - min(1,abs(var(--pass) - var(--loop-captured-pass))))}"
+    if css.count(old) != 1:
+        raise ValueError("R2F: missing unique loop controller rule")
+    markers = ",".join(_DECODE.format(lp=f"--lp-{bank}-{width}") for bank in range(2))
+    new = (
+        f"body{{--pass:min(calc(max({markers}) + 1),var(--pass-cap));--pass-cap:{blocks};"
+        f"--lp-0-{width}:inherit;--lp-1-{width}:inherit;"
+        "container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2)}"
+        # the marker readers live on the wrapper, above the controller
+        f".core-pass-reader{{animation-name:loop-k-0-{width},loop-k-1-{width};"
+        "animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;"
+        f"animation-timeline:--loop-t-0-{width},--loop-t-1-{width}}}"
+        '@property --pass-cap{syntax:"<number>";inherits:false;initial-value:0}'
+    )
+    css = css.replace(old, new)
+    # 5. token boundaries raise the cap instead of writing the pass
+    for token in range(1, capacity):
+        css += f"body:has(#token-{token}-advanced.done){{--pass-cap:{(token + 1) * blocks}}}"
+    return css
+
+
+def apply_body(body):
+    """Drop the 4 <g> + 2 <set> SMIL signal elements per step."""
+    body, count = re.subn(
+        r'<svg class="loop-signals">.*?</svg>', '<svg class="loop-signals"></svg>', body
+    )
+    if count != 1:
+        raise ValueError("R2F: expected one svg.loop-signals")
+    return body
+
+
+def wrap_controller(body):
+    return '<div class="core-pass-reader">' + body + "</div>"
```
