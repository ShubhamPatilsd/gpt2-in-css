# bundles/combined8-c32-prompt — `combined8-c32` (R5X recipe, capacity 32, `--value-layout widths`) + R6P: (A) pre-Run prompt echo fix, (B) typed free-text prompt (OpenType BPE tokenizer fonts → ≤4 prompt ids → prefill through the feedback path)

Built by R6P on 2026-09-30 15:52 with `work/2026-09-19/R6P/compile.sh` (= `R5X/compile.sh` + the R6P flags; tools copy `work/2026-09-19/R6P/tools` =
`R5X/tools` + `r6p_prompt.py` + 7 conditional edits in `browser_gpt2_runtime.py`, diff embedded below and at `R6P/tools-vs-R5X.diff`). Symlinks as R5X
(`assets → F4/assets`, `data`, `experiments`, `global-projection-assets`, `assets-r5h → R5X/assets-r5h`) plus **`R6P/assets-r6p/gpt2-token-id-{0,1}-full.ttf`**
= byte-identical copies (md5 53bd2b59… / be15cafa…) of `tinystories/gpt2-token-id-{0,1}-full.ttf` (`make tinystories-tokenizer-font` =
`tools/build_metric_tokenizer_font.py --full --token-ids --positions 4`; GPT-2 vocabulary: `data/tiny-gpt2/vocab.json` == `data/gpt2/vocab.json` as dicts,
merges identical). The bundle depends on `work/2026-09-19/R6P/` (tokenizer fonts) and `R5X/` (dot fonts) staying in place.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6P
# combined8-c32's exports (bundles/combined8-c32/BUILD.md) plus:
export R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=1 R6P_PROMPT_SLOTS=4 R6P_DEFAULT_PROMPT=
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined8-c32-prompt 32 12
#  = uv run --with numpy --with fonttools --with pillow --with brotli python tools/browser_gpt2_runtime.py --blocks 12 --capacity 32 --reuse-core
#    --cache-codec font-vector --cache-layout flat --scoped-state --isolate-head --detached-output --value-layout widths --font-backend original --output …
```

## Flags (new; everything else as `bundles/combined8-c32/BUILD.md`)

| flag | default | effect |
|---|---|---|
| `R6P_ECHO_FIX` | 1 | (A) `.visible-output{--display-prompt:var(--frozen-prompt)}` and `::before{counter-reset:prompt var(--display-prompt)}` instead of `counter-reset:prompt var(--frozen-prompt)`. `--frozen-prompt` is registered `inherits:false` (F5), and a pseudo-element only inherits inherited properties from its originating element, so `::before` saw the initial value 0 → token 0 = "!" for every prompt. An unregistered copy on the element itself is inherited by the pseudo. |
| `R6P_TYPED_PROMPT` | 1 | (B) editable `<style id="tk-editor" contenteditable="plaintext-only">.tk-root { --draft-prompt: ""; }</style>`; tokenizer chain (4 slots × [metric, probe > bridge, metric, probe > bridge]) wrapping the model; `.feedback-select{--token}` becomes the prefill chain (`--pf-1..4`); `.visible-output` shows typed text pre-Run and the N decoded prompt tokens + generated tokens from Run; winners of epochs 1..N−1 hidden; EOS at a prefill epoch acked and `#eos-ready` suppressed; typed ids frozen (86400 s transition latch) once `#fonts-loaded.done` and `#run-latched.done`; editor read-only after run-latched; tokenizer fonts join the font barrier (witness glyph `~` / `!`). |
| `R6P_PROMPT_SLOTS` | 4 | N = max prompt tokens; must be ≤ the `--positions` built into the tokenizer fonts (checked at build) and < capacity. |
| `R6P_DEFAULT_PROMPT` | "" | initial text in the editor; empty = dropdown fallback path (so a Run without typing is exactly the old dropdown run). |

Both flags off (`R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0`) reproduces `bundles/combined8-c32` **byte-for-byte** (index.html identical; runtime.css identical after URL-depth normalisation; manifest +8 R6P keys; witnesses 283/283) — `R6P/logs/compare-c32-off-vs-combined8-c32.log`.

## Mechanism (see R6P.md §3 for the full design)

body ▸ `.tk-root` (display:contents; the editable rule sets `--draft-prompt`, registered `<string>` inherits:false) ▸ per slot k: `<i class="tk-metric tk-pos-k tk-part-0">`
(1px, `font-feature-settings:"p00k" 1`, family GPT2TokenId0, `::before{content:var(--tk-text)}`), `<div class="tk-probe-k-0">` (position:absolute, `container:tk-k-0/inline-size`,
`width:anchor-size(--tk-a-k-0 width)`) ▸ `.tk-low-k` (`@container tk-k-0 (width>0px){--pt-low-k:round(100cqi/1px*64 − 1)}`) ▸ metric part 1 + `.tk-probe-k-1` ▸ `.tk-high-k`
(`--pt-high-k`, `--pt-present-k:1`; `--pt-id-k = low + 32767·high`; model-facing `--prompt-token-id-k = if(armed) --pt-id-k else −1`, `--prompt-has-k`) ▸ … ▸ `.tk-high-3`
(`container-name:tkprompt`, `--prompt-count = Σ --prompt-has-k`) ▸ `<i class="tk-tokens">` (live readout) + `.feedback-reader` (the model). `--prompt-armed` (private) is 1 while
`#run:checked`; all private values hop by explicit `inherit` so typing restyles ≈25 elements, never the model. `.feedback-select{--pf-e}` picks `--prompt-token-id-(e−1)` when
`--prompt-count ≥ e`, else `--feedback-(e−1)`; `--token = if(epoch e ≤ 4: --pf-e; e > 4: --feedback-(e−1))`. The embedding lookup (`--token` → GRUP/LOCL axes of the
full-vocabulary HVAR font) is unchanged and identical for prefilled and fed-back ids.

## Offline verification (R6P.md §4; logs `R6P/logs/`)

- flags-off twin == `bundles/combined8-c32` byte-identical (above); echo-only twin (`R6P_TYPED_PROMPT=0`) differs from combined8-c32 by exactly the two `.visible-output` rules (index.html identical) — `R6P/logs/compare-c32-echo-vs-combined8-c32.log`.
- vs `combined8-c32`: elements 86,438 → 86,471 (+33: 32 chain elements + `.tk-tokens`; the panel's 3 elements are in the controls), max depth 165 → 182, runtime.css 49,311,014 → 50,311,897 B (+1.0 MB: 3 R2G `:has()` chains gain 17 levels each in 3,437 `tk-` rule occurrences), index.html 7,125,736 → 7,127,853 B; witnesses 283/285 identical + the 2 tokenizer faces; `launch_browser_gpt2.py --check`: 287 static files, 299,822,634 B, `runtimeJavaScript:false`; 0 `<script>`, 0 `on*=` attributes.
- Tokenizer fonts vs the Python GPT-2 tokenizer (`R6P/hb_check.py`, hb-shape 14.2.1, positions 0..3, both digit fonts): 22/26 prompts identical incl. "Once upon a time" → [7454, 2402, 257, 640], "I" → [40], contractions, digits, punctuation; the 4 mismatches are the known limits: newline, runs of ≥2 spaces, non-ASCII (café, naïve) — `R6P/logs/hb_check.log`.
- NumPy references (`R6P/reference_prompt.py`, same q9/q16 path as R4C/R4P; memoised like R4P): typed "I" → `R6P/reference_ids_I.json` **== R4P/reference_ids_32_40.json** (free-running == teacher-forced); "Once upon a time" → `R6P/reference_ids_once_upon_a_time.json` (32 winners; winners 1..3 = [262, 257, 640] are the discarded prefill predictions, generated 29 = `, the world was a place of great beauty and great danger. The world was a place of great danger, and the world was a place of`; teacher-forced check == winners; quantized == float at all 32 steps); 2-layer twins for the smoke.

## Chrome (gated; `R6P/run_chain.sh`, armed 15:53 — gate closed at the time: disk 2 GB, swap used 7.7 GB)

Planned under CHROME.lock, one run each: (1) 2-layer smoke `R6P/scratch/smoke2-on` typed "Once upon a time" vs `reference_ids_once_upon_a_time_2layers.json`;
(2) `bundles/combined8-prompt` (cap 8) dropdown Hello 8/8 + verify rc 0 → READY; (3) this bundle typed "I" → 32/32 vs `R4P/reference_ids_32_40.json`;
(4) this bundle typed "Once upon a time" → 32/32 vs `R6P/reference_ids_once_upon_a_time.json` → READY. Results land in `R6P/run-*/` and `R6P.log.md`; READY is created only on 32/32 for both (3) and (4). Harness: `R6P/bench_native.mjs` (= R4M's + `B0_TYPED_PROMPT`: Playwright `locator.fill` on `#tk-editor` before `DOM.focus(#run)` + Space; live `--pt-id-k` asserted against `B0_TYPED_IDS`, model-facing values asserted unarmed pre-Run).


## `diff -ruN -x __pycache__ work/2026-09-19/R5X/tools work/2026-09-19/R6P/tools` (431 lines; also `R6P/tools-vs-R5X.diff`; R5X/tools vs R4M/tools7 is embedded in `bundles/combined8-c32/BUILD.md`)

```diff
diff -ruN -x __pycache__ ../R5X/tools/browser_gpt2_runtime.py tools/browser_gpt2_runtime.py
--- ../R5X/tools/browser_gpt2_runtime.py	2026-09-24 16:21:15
+++ tools/browser_gpt2_runtime.py	2026-09-30 15:45:19
@@ -24,6 +24,7 @@
 import r2g_has_scope as r2g
 import r3h_blockflow_max as r3h
 import r5e_dead_weight as r5e
+import r6p_prompt as r6p  # R6P: pre-Run prompt echo fix + typed free-text prompt (prefill)
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -94,14 +95,18 @@
         + ",".join(timelines)
         + "}"
     )
-    css += (
-        ".feedback-select{--token:if(style(--epoch:1):var(--frozen-prompt);"
-        + ";".join(
-            f"style(--epoch:{i}):var(--feedback-{i - 1})"
-            for i in range(2, capacity + 1)
+    if r6p.TYPED:
+        # R6P: registrations live here so the head-isolation wall resets them; --token becomes the prefill chain
+        css += r6p.regs(capacity) + r6p.token_select_css(capacity)
+    else:
+        css += (
+            ".feedback-select{--token:if(style(--epoch:1):var(--frozen-prompt);"
+            + ";".join(
+                f"style(--epoch:{i}):var(--feedback-{i - 1})"
+                for i in range(2, capacity + 1)
+            )
+            + ";else:var(--frozen-prompt))}"
         )
-        + ";else:var(--frozen-prompt))}"
-    )
     signals, metrics = (
         [
             '<g id="eos-ready"></g><g id="eos-done"><set attributeName="class" to="done" begin="eos-ready.animationend+0.001s" fill="freeze"/></g>'
@@ -159,7 +164,10 @@
         else:
             with TTFont(path, lazy=True) as font:
                 cmap = font.getBestCmap()
-                cp = next(c for c in sorted(cmap) if font["hmtx"][cmap[c]][0] > 1)
+                if r6p.TYPED and r6p.is_tokenizer_font(path):
+                    cp = r6p.barrier_codepoint(font, cmap)  # R6P: printable witness glyph (TAB expands to tab stops)
+                else:
+                    cp = next(c for c in sorted(cmap) if font["hmtx"][cmap[c]][0] > 1)
                 info = {
                     "codepoint": cp,
                     "advance": font["hmtx"][cmap[cp]][0],
@@ -463,6 +471,12 @@
         )
         if tagged != (3 if r5e.KEEP_DIAG else 2):  # R5E: #core-probe's epoch twin
             raise ValueError(f"Unexpected inline epoch readers in model: {tagged}")
+    r6p_font_info = None
+    if r6p.TYPED:
+        # R6P: the tokenizer fonts join the font barrier; the model nests under the tokenizer chain
+        r6p_font_info = r6p.check_fonts()
+        css += r6p.font_faces_css()
+        model = r6p.wrap_model(model)
     font_html, font_css, font_count = font_barrier(css, directory)
     css += font_css
     scopes = re.findall(r"html\{timeline-scope:([^}]+)\}", css)
@@ -490,10 +504,18 @@
         + ";".join(f"--display-token-{i}:-1" for i in range(1, capacity + 1))
         + "}"
     )
-    css += ".visible-output::before{counter-reset:prompt var(--frozen-prompt);content:counter(prompt,gpt2-vocabulary)}"
+    if r6p.TYPED:
+        css += r6p.display_css()  # R6P: typed text / decoded prompt tokens + echo fix
+    elif r6p.ECHO_FIX:
+        css += r6p.echo_fix_css()  # R6P (A): the pseudo-element does not inherit the private --frozen-prompt
+    else:
+        css += ".visible-output::before{counter-reset:prompt var(--frozen-prompt);content:counter(prompt,gpt2-vocabulary)}"
     css += 'body:has(#eos-done.done) .status::after{content:"Complete • end of text"}'
     for i in range(1, capacity + 1):
-        css += f"body:has(#token-{i}-captured.done) .visible-output{{--display-token-{i}:var(--feedback-{i})}}"
+        if r6p.TYPED:
+            css += r6p.display_token_rule(i)  # R6P: prefill winners hidden
+        else:
+            css += f"body:has(#token-{i}-captured.done) .visible-output{{--display-token-{i}:var(--feedback-{i})}}"
     css += f'body{{margin:24px;font:16px/1.5 system-ui;background:#f7f5ef;color:#222}}.controls{{position:fixed;left:24px;top:16px;z-index:100}}body:has(#run-latched.done) select{{pointer-events:none;opacity:.6}}.status::after{{content:"Loading model fonts…"}}body:has(#fonts-loaded.done) .status::after{{content:"Ready • {blocks}-block native compute"}}'
     css += f'body:has(#token-{capacity}-captured.done) .status::after{{content:"Complete • {capacity} tokens"}}'
     options = [15496, 464, 40, 32, 1212, 2061]
@@ -529,6 +551,14 @@
         else "Speed depends on the block/context configuration."
     )
     controls += f'<aside style="position:fixed;left:24px;right:24px;top:176px;font:13px/1.5 system-ui;color:#666">Experimental q9/q16 GPT-2 • one prompt token • at most {capacity} generated tokens.<br>HTML/CSS/OpenType + native SVG control. No JavaScript. {speed}</aside>'
+    if r6p.TYPED:
+        # R6P: editable prompt panel, tokenizer chain, prefill handshakes, display layout
+        controls = controls.replace(
+            "one prompt token",
+            f"typed prompt (first {r6p.SLOTS} BPE tokens; each prefilled token costs one full step) or one dropdown token",
+        ).replace('<aside style="', '<aside class="tk-aside" style="')
+        controls += r6p.panel_html()
+        css += r6p.chain_css() + r6p.prefill_handshake_css() + r6p.panel_css(capacity)
     if teacher_forced_tokens is not None:
         # Known evaluation INPUT IDs, not generated answers or activations.
         # The native embedding, 12-layer loop, KV retention and full head still
@@ -593,7 +623,8 @@
         fontFaces=font_count,
         autostart=autostart,
         head="full-vocabulary-q16-two-pass",
-        promptTokens=1,
+        promptTokens=r6p.SLOTS if r6p.TYPED else 1,
+        **r6p.manifest(r6p_font_info),
         generatedTokenLimit=capacity,
         kvStorage="native remembered layout"
         if cache_codec == "geometry"
diff -ruN -x __pycache__ ../R5X/tools/r6p_prompt.py tools/r6p_prompt.py
--- ../R5X/tools/r6p_prompt.py	1969-12-31 16:00:00
+++ tools/r6p_prompt.py	2026-09-30 15:49:44
@@ -0,0 +1,319 @@
+"""R6P (2026-09-30): (A) pre-Run prompt echo fix and (B) typed free-text prompt for the GPT-2 runtime.
+
+(A) `R6P_ECHO_FIX` (default 1). `.visible-output::before` renders `counter(prompt, gpt2-vocabulary)` from
+    `counter-reset: prompt var(--frozen-prompt)`. Since F5 `--frozen-prompt` is registered `inherits:false`; a
+    pseudo-element only inherits *inherited* properties from its originating element, so inside `::before`
+    `--frozen-prompt` is the registration's initial value 0 -> token 0 = "!" for every prompt, before and after
+    Run. Fix: copy the value into an UNREGISTERED property on `.visible-output` itself (`--display-prompt`),
+    which the pseudo-element does inherit. `.visible-output` is a leaf that is already restyled once per token
+    (it forwards the 32 `--feedback-i` by explicit `inherit`); one more var() on it is not measurable.
+
+(B) `R6P_TYPED_PROMPT` (default 1), `R6P_PROMPT_SLOTS` (default 4 = the positions built into the tokenizer
+    fonts). The TinyStories mechanism (tools/build_tinystories_dynamic.py, tools/build_metric_tokenizer_font.py)
+    ported to this runtime:
+      * an editable `<style contenteditable>` holds `.tk-root{--draft-prompt:"..."}` (registered <string>,
+        inherits:false -> typing restyles only the elements that hop it with `inherit`);
+      * per prompt slot k two hidden 1px metric elements render the whole draft text with the two OpenType
+        BPE tokenizer fonts (rlig = GPT-2's ranked merges; feature p00k keeps only token k, every other glyph
+        becomes the zero-advance `zero` glyph; glyph advance = digit+1 of the token id in base 32767, part 0 =
+        low digit, part 1 = high digit; upem 64 at font-size 1px -> the advance is an exact LayoutUnit);
+      * `anchor-size()` copies each metric's width onto an absolutely positioned inline-size query container
+        whose child reads `round(100cqi/1px*64 - 1)` = the digit (registered <integer>, inherits:false);
+      * the slot element combines low + 32767*high into `--pt-id-k` (private); the values that the MODEL
+        inherits (`--prompt-token-id-k`, `--prompt-has-k`, `--prompt-count`, inherits:true) are gated by
+        `--prompt-armed` (private, hopped from body, 1 once #run is checked) so typing never restyles the
+        model's 86k descendants, and are frozen by the runtime's 86400 s transition latch once fonts-loaded
+        and run-latched are both done (same latch as `--frozen-prompt`);
+      * `.feedback-select{--token}` becomes the prefill chain: epoch e <= N reads `--prompt-token-id-(e-1)`
+        when the prompt has >= e tokens, else the fed-back `--feedback-(e-1)`; epoch 1 falls back to the
+        dropdown's `--frozen-prompt` when nothing is typed. The embedding lookup is the SAME full-vocabulary
+        HVAR font lookup (`--token` -> GRUP/LOCL axes) for prefilled and fed-back ids -> exact-class numerics
+        identical to generation (the TinyStories approximation came from its 8-bit feedback table, which this
+        runtime does not have);
+      * the winners of epochs 1..N-1 (predictions made while prefilling) are captured like any winner but
+        hidden from the display and never fed back; an EOS winner at a prefill epoch neither stops the run
+        nor fires #eos-ready.
+"""
+
+from __future__ import annotations
+
+import html as html_lib
+import os
+from pathlib import Path
+
+from fontTools.ttLib import TTFont
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+ECHO_FIX = flag("R6P_ECHO_FIX")
+TYPED = flag("R6P_TYPED_PROMPT")
+SLOTS = int(os.environ.get("R6P_PROMPT_SLOTS", "4"))
+DEFAULT_TEXT = os.environ.get("R6P_DEFAULT_PROMPT", "")
+BASE = 32_767  # tools/build_metric_tokenizer_font.py TOKEN_ID_BASE (HarfBuzz exposes advances > 32767 as signed)
+UPEM = 64
+EOS = 50_256
+ASSETS = Path(__file__).resolve().parents[1] / "assets-r6p"
+FONTS = [ASSETS / f"gpt2-token-id-{part}-full.ttf" for part in range(2)]
+FAMILIES = ["GPT2TokenId0", "GPT2TokenId1"]
+LATCH = "transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)"
+
+
+def check_fonts():
+    """The fonts must carry position features p000..p(SLOTS-1), upem 64, and the +1 digit encoding."""
+    info = {}
+    for part, path in enumerate(FONTS):
+        if not path.exists():
+            raise FileNotFoundError(f"R6P: tokenizer font missing: {path}")
+        with TTFont(path, lazy=True) as font:
+            tags = {fr.FeatureTag for fr in font["GSUB"].table.FeatureList.FeatureRecord}
+            missing = [f"p{k:03d}" for k in range(SLOTS) if f"p{k:03d}" not in tags]
+            if missing:
+                raise ValueError(f"R6P: {path.name} lacks position features {missing}; rebuild with --positions {SLOTS}")
+            if font["head"].unitsPerEm != UPEM:
+                raise ValueError(f"R6P: {path.name} unitsPerEm {font['head'].unitsPerEm} != {UPEM}")
+            cmap = font.getBestCmap()
+            # 'I' (U+0049) is token 40: part 0 advance 41, part 1 advance 1
+            adv = font["hmtx"][cmap[0x49]][0]
+            expected = (40 // BASE**part) % BASE + 1
+            if adv != expected:
+                raise ValueError(f"R6P: {path.name}: advance of 'I' is {adv}, expected {expected}")
+            positions = sorted(int(t[1:]) for t in tags if t.startswith("p") and t[1:].isdigit())
+            info[path.name] = {"positions": len(positions), "glyphs": len(font.getGlyphOrder()), "bytes": path.stat().st_size}
+    return info
+
+
+def font_faces_css():
+    return "".join(
+        f'@font-face{{font-family:{family};src:url("{path.resolve().as_uri()}") format("truetype")}}'
+        for family, path in zip(FAMILIES, FONTS)
+    )
+
+
+def is_tokenizer_font(path):
+    return Path(path).resolve().parent == ASSETS.resolve()
+
+
+def barrier_codepoint(font, cmap):
+    """font_barrier() picks the first cmap codepoint whose advance > 1. For the tokenizer fonts that is U+0009
+    (TAB, byte token 197, advance 198 in the low-digit font): a tab in `white-space:pre` is laid out at tab stops,
+    not at its glyph advance, so the witness would never match and fonts-loaded would never fire. The high-digit
+    font has no advance > 1 at all (every ASCII byte token is < 32767 -> digit 0 -> advance 1). Choose the
+    PRINTABLE ASCII codepoint with the largest non-zero advance instead ('~' = token 93 -> 94 units in the low font;
+    '!' = token 0 -> 1 unit in the high font); a fallback-font glyph at 4px is ~1-2.5px, never within 0.125px."""
+    best = max((c for c in sorted(cmap) if 32 < c < 127 and font["hmtx"][cmap[c]][0] > 0),
+               key=lambda c: (font["hmtx"][cmap[c]][0], -c))
+    return best
+
+
+# ---------------------------------------------------------------- registrations (emitted inside feedback())
+
+
+def regs(capacity):
+    """@property registrations. Emitted with the feedback CSS so the head-isolation wall sees them."""
+    if SLOTS < 1 or SLOTS >= capacity:
+        raise ValueError(f"R6P: prompt slots {SLOTS} must be in 1..capacity-1 ({capacity - 1})")
+    css = '@property --draft-prompt{syntax:"<string>";inherits:false;initial-value:""}'
+    css += '@property --prompt-armed{syntax:"<integer>";inherits:false;initial-value:0}'
+    css += '@property --tk-count{syntax:"<integer>";inherits:false;initial-value:0}'
+    css += '@property --prompt-count{syntax:"<integer>";inherits:true;initial-value:0}'
+    for k in range(SLOTS):
+        css += f'@property --pt-low-{k}{{syntax:"<integer>";inherits:false;initial-value:0}}'
+        css += f'@property --pt-high-{k}{{syntax:"<integer>";inherits:false;initial-value:0}}'
+        css += f'@property --pt-present-{k}{{syntax:"<integer>";inherits:false;initial-value:0}}'
+        css += f'@property --pt-id-{k}{{syntax:"<integer>";inherits:false;initial-value:-1}}'
+        css += f'@property --prompt-token-id-{k}{{syntax:"<integer>";inherits:true;initial-value:-1}}'
+        css += f'@property --prompt-has-{k}{{syntax:"<integer>";inherits:true;initial-value:0}}'
+    for e in range(1, SLOTS + 1):
+        css += f'@property --pf-{e}{{syntax:"<number>";inherits:false;initial-value:0}}'
+    return css
+
+
+# ---------------------------------------------------------------- the model input (replaces .feedback-select{--token})
+
+
+def token_select_css(capacity):
+    """Prefill chain on .feedback-select (F5: --token / --feedback-* / --frozen-prompt are private and forwarded
+    there by `inherit`; --prompt-token-id-* / --prompt-count are inherited from the tokenizer chain above)."""
+    pf = ".feedback-select{--pf-1:if(style(--prompt-count:0):var(--frozen-prompt);else:var(--prompt-token-id-0))"
+    for e in range(2, SLOTS + 1):
+        fed = f"var(--feedback-{e - 1})"
+        cases = ";".join(f"style(--prompt-count:{c}):{fed}" for c in range(0, e))
+        pf += f";--pf-{e}:if({cases};else:var(--prompt-token-id-{e - 1}))"
+    pf += "}"
+    token = ".feedback-select{--token:if(" + ";".join(
+        [f"style(--epoch:{e}):var(--pf-{e})" for e in range(1, SLOTS + 1)]
+        + [f"style(--epoch:{e}):var(--feedback-{e - 1})" for e in range(SLOTS + 1, capacity + 1)]
+    ) + ";else:var(--frozen-prompt))}"
+    return pf + token
+
+
+# ---------------------------------------------------------------- tokenizer chain (HTML + CSS)
+
+
+def wrap_model(model_html):
+    """Nest the model (and the live token readout) under SLOTS tokenizer stages, TinyStories' structure:
+    metric_k0, probe_k0 > lowbridge_k > [metric_k1, probe_k1 > highbridge_k > child]. Each probe is an
+    absolutely positioned inline-size container whose width is anchor-size() of the preceding metric, so the
+    anchor is always a descendant of the positioned element's containing block (acceptable anchor element)."""
+    child = '<i class="tk-tokens"></i>' + model_html
+    for k in reversed(range(SLOTS)):
+        child = (
+            f'<i class="tk-metric tk-pos-{k} tk-part-0 tk tk-{k}" aria-hidden="true"></i>'
+            f'<div class="tk-probe-{k}-0 tk-probe tk tk-{k}"><div class="tk-low-{k} tk-bridge tk tk-{k}">'
+            f'<i class="tk-metric tk-pos-{k} tk-part-1 tk tk-{k}" aria-hidden="true"></i>'
+            f'<div class="tk-probe-{k}-1 tk-probe tk tk-{k}"><div class="tk-high-{k} tk-bridge tk tk-{k}">'
+            + child
+            + "</div></div></div></div>"
+        )
+    return '<div class="tk-root">' + child + "</div>"
+
+
+def chain_css():
+    last = SLOTS - 1
+    digit = f"round(nearest,calc(100cqi/1px*{UPEM} - 1),1)"
+    css = (
+        ".tk-root{display:contents;--prompt-armed:inherit}"  # body sets --prompt-armed; .tk-root sets --draft-prompt itself
+        # every chain element hops the two private inputs (typing / arming restyle only these elements)
+        ".tk{--draft-prompt:inherit;--prompt-armed:inherit}"
+        "body:has(#run:checked){--prompt-armed:1}"
+        ".tk-metric{position:absolute;left:0;top:0;opacity:0;display:inline-block;width:max-content;height:1px;"
+        "overflow:hidden;font-size:1px;line-height:1;white-space:pre;pointer-events:none;font-kerning:none;"
+        "font-variation-settings:normal;--tk-text:var(--draft-prompt)}"
+        ".tk-metric::before{content:var(--tk-text)}"
+        f".tk-part-0{{font-family:{FAMILIES[0]}}}.tk-part-1{{font-family:{FAMILIES[1]}}}"
+        ".tk-probe{position:absolute;inset:0 auto auto 0;height:1px}"
+        # the model's in-flow containing block keeps body's content width (viewport - 2*24px margin)
+        ".tk-bridge{width:calc(100vw - 48px)}"
+    )
+    for k in range(SLOTS):
+        css += (
+            f'.tk-pos-{k}{{font-feature-settings:"p{k:03d}" 1}}'
+            f".tk-pos-{k}.tk-part-0{{anchor-name:--tk-a-{k}-0}}.tk-pos-{k}.tk-part-1{{anchor-name:--tk-a-{k}-1}}"
+            f".tk-probe-{k}-0{{container:tk-{k}-0/inline-size;width:anchor-size(--tk-a-{k}-0 width,0px)}}"
+            f".tk-probe-{k}-1{{container:tk-{k}-1/inline-size;width:anchor-size(--tk-a-{k}-1 width,0px)}}"
+            f"@container tk-{k}-0 (width > 0px){{.tk-low-{k}{{--pt-low-{k}:{digit}}}}}"
+            f"@container tk-{k}-1 (width > 0px){{.tk-high-{k}{{--pt-high-{k}:{digit};--pt-present-{k}:1}}}}"
+            f".tk-probe-{k}-1,.tk-high-{k}{{--pt-low-{k}:inherit}}"
+            f".tk-high-{k}{{--pt-id-{k}:if(style(--pt-present-{k}:1):calc(var(--pt-low-{k}) + {BASE}*var(--pt-high-{k}));else:-1);"
+            f"--prompt-token-id-{k}:if(style(--prompt-armed:1):var(--pt-id-{k});else:-1);"
+            f"--prompt-has-{k}:if(style(--prompt-armed:1):var(--pt-present-{k});else:0)}}"
+        )
+        if k:
+            hops = ";".join(f"--pt-id-{j}:inherit;--pt-present-{j}:inherit" for j in range(k))
+            css += f".tk-{k}{{{hops}}}"
+        # freeze the model-facing values once the model may start (fonts loaded AND run latched), as --frozen-prompt
+        props = f"--prompt-token-id-{k},--prompt-has-{k}" + (",--prompt-count" if k == last else "")
+        css += f"body:has(#fonts-loaded.done):has(#run-latched.done) .tk-high-{k}{{transition-property:{props};{LATCH}}}"
+    count = " + ".join(f"var(--prompt-has-{j})" for j in range(SLOTS))
+    css += f".tk-high-{last}{{container-name:tkprompt;--prompt-count:calc({count})}}"
+    # live readout of the tokenizer (leaf sibling of the model root; private hops, never restyled per token)
+    hops = ";".join(f"--pt-id-{j}:inherit;--pt-present-{j}:inherit" for j in range(SLOTS))
+    tk_count = " + ".join(f"var(--pt-present-{j})" for j in range(SLOTS))
+    parts = ";".join(
+        f'--tkd-{j}:var(--pt-id-{j});--tko-{j}:if(style(--pt-present-{j}:1):"[";else:"");--tkc-{j}:if(style(--pt-present-{j}:1):"]";else:"")'
+        for j in range(SLOTS)
+    )
+    css += (
+        f".tk-tokens{{position:fixed;left:24px;right:24px;top:118px;font:13px/1.4 system-ui;color:#666;white-space:pre-wrap;"
+        f"{hops};--tk-count:calc({tk_count});{parts};"
+        f'--tk-label:if(style(--tk-count:0):"Typed prompt: none — the dropdown prompt is used. ";else:"Typed prompt → GPT-2 tokens (first {SLOTS} used, each costs one full step): ")}}'
+        ".tk-tokens::after{counter-reset:"
+        + " ".join(f"tkt{j} var(--tkd-{j})" for j in range(SLOTS))
+        + ";content:var(--tk-label) "
+        + " ".join(f"var(--tko-{j}) counter(tkt{j},gpt2-vocabulary) var(--tkc-{j})" for j in range(SLOTS))
+        + "}"
+    )
+    return css
+
+
+# ---------------------------------------------------------------- display (.visible-output) and prefill handshakes
+
+
+def echo_fix_css():
+    return (
+        ".visible-output{--display-prompt:var(--frozen-prompt)}"
+        ".visible-output::before{counter-reset:prompt var(--display-prompt);content:counter(prompt,gpt2-vocabulary)}"
+    )
+
+
+def display_css():
+    """Pre-Run: the typed text (or the dropdown token when nothing is typed). From Run: the N decoded prompt
+    tokens (what the model actually consumed) followed by the generated tokens; winners 1..N-1 are hidden."""
+    css = (
+        ".feedback-reader,.visible-output{--draft-prompt:inherit;--pt-present-0:inherit}"
+        ".visible-output{--display-prompt:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));"
+        '--draft-echo:if(style(--prompt-count:0):var(--draft-prompt);else:"")}'
+        ".visible-output::before{counter-reset:prompt var(--display-prompt) "
+        + " ".join(f"tkp{k} var(--prompt-token-id-{k})" for k in range(SLOTS))
+        + ";content:counter(prompt,gpt2-vocabulary) var(--draft-echo) "
+        + " ".join(f"counter(tkp{k},gpt2-vocabulary)" for k in range(SLOTS))
+        + "}"
+    )
+    return css
+
+
+def display_token_rule(i):
+    """`body:has(#token-i-captured.done) .visible-output{--display-token-i:...}` for i < SLOTS: hidden when the
+    prompt has more than i tokens (the winner at epoch i was a prefill prediction, not a generated token)."""
+    if i >= SLOTS:
+        return f"body:has(#token-{i}-captured.done) .visible-output{{--display-token-{i}:var(--feedback-{i})}}"
+    cases = ";".join(f"style(--prompt-count:{c}):-1" for c in range(i + 1, SLOTS + 1))
+    return f"body:has(#token-{i}-captured.done) .visible-output{{--display-token-{i}:if({cases};else:var(--feedback-{i}))}}"
+
+
+def prefill_handshake_css():
+    """While epoch e is a prefill position (prompt has > e tokens) an EOS winner must neither stop the run
+    (ack it like any other winner) nor fire #eos-ready."""
+    css = ""
+    for e in range(1, SLOTS):
+        for c in range(e + 1, SLOTS + 1):
+            css += (
+                f"@container tkprompt style(--prompt-count:{c}){{"
+                f"@container headstate style(--winner:{EOS}){{body:has(#run:checked):has(#token-{e}-captured.done) #token-{e}-ack{{animation:native-handshake 1ms both}}}}"
+                f"@container runtime style(--epoch:{e}){{body:has(#run:checked) #eos-ready{{animation:none!important}}}}"
+                "}"
+            )
+    return css
+
+
+# ---------------------------------------------------------------- controls
+
+
+def panel_html():
+    text = html_lib.escape(DEFAULT_TEXT.replace("\\", "\\\\").replace('"', '\\"'))
+    return (
+        '<div class="tk-panel"><label for="tk-editor">Or type a prompt between the quotes (ASCII, single spaces; the first '
+        f"{SLOTS} GPT-2 tokens are used):</label>"
+        f'<style id="tk-editor" class="tk-editor" contenteditable="plaintext-only" spellcheck="false" role="textbox" aria-label="Editable prompt">.tk-root {{ --draft-prompt: "{text}"; }}</style></div>'
+    )
+
+
+def panel_css(capacity):
+    return (
+        ".tk-panel{position:fixed;left:24px;right:24px;top:52px;z-index:100;font:13px/1.4 system-ui;color:#444}"
+        ".tk-panel label{display:block;margin-bottom:2px}"
+        ".tk-editor{display:block;box-sizing:border-box;width:100%;max-width:800px;padding:4px 8px;border:1px solid #aaa;border-radius:4px;"
+        "background:#fff;color:#111;font:13px/1.4 ui-monospace,Menlo,monospace;white-space:pre;overflow:hidden;caret-color:#111}"
+        ".tk-editor:focus{outline:2px solid Highlight}"
+        "body:has(#run-latched.done) .tk-editor{-webkit-user-modify:read-only;pointer-events:none;opacity:.6}"
+        ".visible-output{top:146px}"
+        ".tk-aside{top:auto!important;bottom:16px}"
+    )
+
+
+def manifest(font_info):
+    return dict(
+        r6pEchoFix=ECHO_FIX,
+        r6pTypedPrompt=dict(
+            enabled=TYPED,
+            slots=SLOTS if TYPED else 0,
+            fonts=[str(p) for p in FONTS] if TYPED else [],
+            fontInfo=font_info,
+            defaultText=DEFAULT_TEXT if TYPED else None,
+            base=BASE,
+            prefill="epochs 1..N read --prompt-token-id-(e-1) through the same --token embedding lookup as fed-back ids; winners 1..N-1 hidden and never fed back",
+        ),
+    )
```
