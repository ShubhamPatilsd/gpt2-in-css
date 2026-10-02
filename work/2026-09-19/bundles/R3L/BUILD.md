# bundles/R3L — combined3 recipe + ONE font-axis latch per loop bank (R3L_FONT_LOOP, default ON) — READY (8/8; bench data point only, superseded by R3R in the combined4 line)

Built by R3L on 2026-09-20 21:54 (rebuilt twice: HarfBuzz caps one glyph advance at 32768 px → 32 hi copies; Chrome's WOFF2 decoder rejects the 256-axis carrier fonts → TrueType assets) (`work/2026-09-19/R3L/compile.sh R3L 12 8`; tools copy `work/2026-09-19/R3L/tools` = `R2H/tools` +
`r3l_packed_loop.py` + 3 hooked files; fonts / F2 shards / F4 assets via the `experiments -> ../../../experiments`, `data -> ../../../data`,
`assets -> ../F4/assets`, `global-projection-assets -> ../F2/global-projection-assets` symlinks beside the tools copy). **New assets**: the 6
loop-carrier fonts `work/2026-09-19/R3L/loop-carrier-assets/loop-carrier-{0..5}.ttf` (built deterministically by `r3l_packed_loop.ensure_fonts()`;
TrueType because Chrome's WOFF2 decoder rejects every WOFF2 encoding of these fonts — `OTS parsing error: Failed to convert WOFF 2.0 font to SFNT`, even the builder's own; 545 KB each, 526 KB of it the 256-region HVAR: 257 glyphs = 256 value glyphs with zero base advance + 1 static witness glyph U+E100 for the font barrier, 256 axes with fvar max 16384), referenced as `../../R3L/loop-carrier-assets/…ttf?v=<sha256[:12]>` (`launch_browser_gpt2.py --check`: 291 static files / 290,700,324 B).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3L
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R3L_FONT_LOOP=1 R3L_PACKED_LOOP=0
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R3L
```

## Flags

| flag | default | effect |
|---|---|---|
| `R3L_FONT_LOOP` | **1** | each loop bank latches ONE `*` `font-variation-settings` list `--lst-b` (1,536 entries: `"Hiii" k_hi_i, "Liii" k_lo_i`, exact integers) + the epoch `--saved-b-768` with a 2-name `transition-property` list (`transition-behavior:allow-discrete`, F4's `--head-fvs` idiom) instead of 769 `<number>` latches. Carriers become glyph elements `<i class="loop-metric lf-k" style="width:max-content"><b class="lh">hi×32</b><b class="ll">lo</b></i>`: the hi glyph (2 px/unit at font-size 512 px, zero base advance, HVAR delta 16384 on axis `Hiii`) repeated 32× because HarfBuzz caps ONE glyph advance at 32768 px (16.16 positions), plus the lo glyph (1/64 px/unit at 4 px, axis `Liii`); max-content = 32·2·k_hi + k_lo/64 = 64·k_hi + k_lo/64 px = today's `262144px + v·128px` on the same 1/64-px LayoutUnit grid (equal or 1 LayoutUnit apart: pure truncation vs float32-then-truncation). 3,072 private `<number>` helpers `--lh/--ll-b-i` are computed on the write bank: `k_hi = clamp(0,round(down,(v+2048)*2,1),16383)`, `k_lo = clamp(0,round(down,((v+2048)*2 − k_hi)*4096,1),4095)`. Read side unchanged. Manifest `r3lFontLoop`. |
| `R3L_PACKED_LOOP` | **0** | 384 packed 2×26-bit `<number>` pairs — **numerically wrong in Blink** (`var()` substitutes a registered `<number>` as 6-significant-digit text; R3L.md §2); kept for the record. Manifest `r3lPackedLoop`. |

Both off reproduces combined3's recipe output byte-for-byte (verified on the 2-layer build vs `bundles/smoke-R3F-2L-ref`).

Sizes: runtime.css 41,277,244 B (combined3 40,872,840: +2 × 190 KB write rules, +3,076 registrations), index.html 7,045,186 B (6,658,236: 1,536 carriers × 33 glyph references),
289 font faces (283 + 6 loop carriers).

## Offline verification

- `PYTHONPATH=tools python R3L/offline_check.py bundles/R3L bundles/combined3` → `RESULT: ok`: runtime.css byte-identical outside the 2 base
  latch rules, 2 write rules (= `r3l_packed_loop.write_declarations` spec, 190,502 B each), the `.loop-scroll,.loop-track` forwards, the latch
  `@property` registrations (3,076 vs 1,538) and their `initial` entries in the reset lists, the 6 `@font-face` + 11 glyph/track rules, and the
  font-barrier bookkeeping (6 more faces → different reduction tree); index.html identical outside the 1,538 carriers (= `carrier_markup` spec) and
  the 6 extra font-witness probes; loop-carrier URLs inside R3L; all helper registrations `inherits:false`.
- `R3L/loop_range.py` (NumPy forward, transport modelled at every layer boundary incl. the 6-digit `var()` step): font transport = today's
  carrier on 50 % of values and exactly 1 LayoutUnit (1.22e-4) off on the rest; accumulated divergence vs exact at layer 12: today 6.4e-3, font
  3.9e-3; q9/q16 ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]` for exact / today / font.
- Fonts: `R3L/fixture/build_loop_font.py` uharfbuzz check — 6 fonts × 64 random axis vectors × 16 glyphs, all advances exact (= k units, zero base).

## Chrome runs

- 2-layer smoke (`bundles/smoke-R3L-2L-font` vs `-ref`, `R3L/runs/smoke-2L-*`): ids [11, 3387] both; same pass/layout counts; latch frame 673 → 494 ms
  (pass 252 → 60 ms, layout +33 ms, transition starts 769 → 2). See `R3L.md` §4.1.
- 12-layer correctness (`R3L/run_correctness.sh R3L`, 21:59–22:02, AC, passive, `R3L/run-R3L/`): ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** 8/8,
  `verify_browser_gpt2_runtime.py` rc=0, finalResidualError rmse 0.0155 / max 0.120 (combined3: 0.0201 / 0.187), text "Hello, I'm sorry, but I'm".
  Per-token capture times (5 s poll, indicative only): 28.2 17.4 26.5 17.4 23.0 23.1 23.7 23.5 s.
- **READY** created 2026-09-20 22:03 (coordinator: one bench data point for B4; the combined4 line (R3R) has no loop-bank hop, so this latch has no target there).

## `diff -ruN-x __pycache__ work/2026-09-19/R2H/tools work/2026-09-19/R3L/tools`

```diff
diff -ruN -x __pycache__ ../R2H/tools/browser_gpt2_reused_adapter.py tools/browser_gpt2_reused_adapter.py
--- ../R2H/tools/browser_gpt2_reused_adapter.py	2026-09-19 10:10:29
+++ tools/browser_gpt2_reused_adapter.py	2026-09-20 20:54:05
@@ -13,6 +13,7 @@
 import r2c_hoist as r2c
 from browser_gpt2_reused_core import compile_reused
 import r2f_lean_handshake as r2f
+import r3l_packed_loop as r3l
 
 
 def compile_reused_runtime_core(
@@ -223,6 +224,8 @@
         "privateLayerControl": True,
         "localLayerContainer": True,
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
+        "r3lPackedLoop": r3l.PACKED_LOOP,
+        "r3lFontLoop": r3l.FONT_LOOP,
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
diff -ruN -x __pycache__ ../R2H/tools/browser_gpt2_reused_core.py tools/browser_gpt2_reused_core.py
--- ../R2H/tools/browser_gpt2_reused_core.py	2026-09-19 10:10:29
+++ tools/browser_gpt2_reused_core.py	2026-09-20 20:54:05
@@ -15,6 +15,7 @@
 import build_hybrid_twelve_block as h
 import f5_scoping as f5
 import r2c_hoist as r2c
+import r3l_packed_loop as r3l
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -333,9 +334,13 @@
                 f"--gate-{kind}",
             ]
         lp = [f"--lp-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
-        saved = [f"--saved-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
+        saved = (
+            [n for bank in range(2) for n in r3l.latched_names(bank, W)]
+            if r3l.active(W)
+            else [f"--saved-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
+        )
         outputs = [f"--loop-out-{i}" for i in range(W)]
-        private = set(progress + lp + saved + outputs + bank_props)
+        private = set(progress + lp + saved + outputs + bank_props + (r3l.private_names(W) if r3l.active(W) else []))
         css = re.sub(
             r"@property (--[\w-]+)\{[^{}]+\}",
             lambda m: (
@@ -352,7 +357,13 @@
         css += forward(".loop-input", lp)
         css += forward(".loop-bank-0,.loop-bank-1", outputs)
         css += forward(".loop-scroll,.loop-track", saved)
-        if f5.INLINE_FORWARD:
+        if r3l.active(W):
+            # R3L: the carriers already carry their inline forward where they
+            # read a latched number (r3l.carrier_markup); glyph carriers read none.
+            count = body.count('<i class="loop-metric')
+            if count != 2 * (W + 1):
+                raise ValueError(f"Expected {2 * (W + 1)} R3L loop carriers, found {count}")
+        elif f5.INLINE_FORWARD:
             # F5: 1,538 `.loop-metric:nth-child(N)` rules share one class
             # bucket, so every loop-metric tested all 1,538 selectors on each
             # restyle (P2: 153 us/element on the 1,553-element pass). The
diff -ruN -x __pycache__ ../R2H/tools/probe_native_reused_loop.py tools/probe_native_reused_loop.py
--- ../R2H/tools/probe_native_reused_loop.py	2026-09-19 10:10:29
+++ tools/probe_native_reused_loop.py	2026-09-20 20:54:05
@@ -6,6 +6,7 @@
 from pathlib import Path
 
 from build_hybrid_twelve_block import regs
+import r3l_packed_loop as r3l
 from probe_native_value_latch import navigate, props
 from profile_hybrid_twelve_block import browser, query
 
@@ -26,17 +27,24 @@
         + [f"--loop-in-{i}" for i in range(width)]
         + [f"--loop-out-{i}" for i in range(width)]
         + [f"--lp-{b}-{i}" for b in range(2) for i in range(width + 1)]
-        + [f"--saved-{b}-{i}" for b in range(2) for i in range(width + 1)]
+        + ([] if r3l.active(width) else [f"--saved-{b}-{i}" for b in range(2) for i in range(width + 1)])
     )
+    if r3l.active(width):
+        # R3L: latched values registered by the packing module (font list / packed pairs + epoch)
+        css += r3l.registrations(width) + r3l.style_css()
     css += "body{--pass:1;container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2);--loop-held:calc(1 - min(1,abs(var(--pass) - var(--loop-captured-pass))))}@keyframes loop-pulse{from{opacity:.99}to{opacity:1}}.loop-signals{position:fixed;width:1px;height:1px;top:0;left:0}"
     css += ".loop-scroll{position:fixed;top:-100000px;left:0;width:524288px;height:1px;overflow:scroll;visibility:hidden}.loop-track{width:1572864px;height:1px;position:relative}.loop-metric{position:absolute;top:0;left:0;height:1px}"
     timelines, anims = [], []
     output = "{child}"
     bank_css = []
     for bank in range(2):
-        names = [f"--saved-{bank}-{i}" for i in range(width + 1)]
+        names = (
+            r3l.latched_names(bank, width)
+            if r3l.active(width)
+            else [f"--saved-{bank}-{i}" for i in range(width + 1)]
+        )
         bank_css.append(
-            f".loop-bank-{bank}{{transition-property:{','.join(names)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}"
+            f".loop-bank-{bank}{{transition-property:{','.join(names)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end){r3l.transition_extra() if r3l.active(width) else ''}}}"
         )
         metrics = []
         for i in range(width + 1):
@@ -45,7 +53,9 @@
             anims.append(key)
             css += f"@keyframes {key}{{from{{--lp-{bank}-{i}:{-2 if centered else 0}}}to{{--lp-{bank}-{i}:1}}}}"
             metrics.append(
-                f'<i class="loop-metric" style="width:calc(262144px + var(--saved-{bank}-{i}) * 128px);view-timeline:{tl} inline"></i>'
+                r3l.carrier_markup(bank, i, width, tl)
+                if r3l.active(width)
+                else f'<i class="loop-metric" style="width:calc(262144px + var(--saved-{bank}-{i}) * 128px);view-timeline:{tl} inline"></i>'
             )
         output = (
             f'<div class="loop-bank-{bank}"><div class="loop-scroll"><div class="loop-track">'
@@ -55,8 +65,13 @@
             + "</div>"
         )
         css += f"@container loopcontrol style(--loop-phase:{bank}){{.loop-bank-{bank}{{transition-property:none;"
-        css += ";".join(f"--saved-{bank}-{i}:var(--loop-out-{i})" for i in range(width))
-        css += f";--saved-{bank}-{width}:var(--pass)}}}}"
+        if r3l.active(width):
+            # R3L: one `*` glyph-axis list (or 384 packed pairs) + the epoch instead of 769 separate latches
+            css += ";".join(r3l.write_declarations(bank, width, "var(--pass)"))
+            css += "}}"
+        else:
+            css += ";".join(f"--saved-{bank}-{i}:var(--loop-out-{i})" for i in range(width))
+            css += f";--saved-{bank}-{width}:var(--pass)}}}}"
         css += f"@container loopcontrol style(--loop-held:1){{.loop-bank-{bank}{{transition-property:{','.join(names)}}}}}"
         read_bank = 1 - bank
         css += f"@container loopcontrol style(--loop-phase:{bank}){{.loop-input{{"
diff -ruN -x __pycache__ ../R2H/tools/r3l_packed_loop.py tools/r3l_packed_loop.py
--- ../R2H/tools/r3l_packed_loop.py	1969-12-31 16:00:00
+++ tools/r3l_packed_loop.py	2026-09-20 21:53:29
@@ -0,0 +1,210 @@
+"""R3L (2026-09-20): fewer loop-bank latch transitions — 2 per bank instead of 769.
+
+Flags:
+  R3L_FONT_LOOP   (default ON)  ONE `*` font-variation-settings list per bank (+ the epoch) latched by a single
+                                `transition-behavior:allow-discrete` transition (F4's `--head-fvs` idiom); the 768
+                                values leave the bank as glyph advances of the loop-carrier fonts (var()-free).
+  R3L_PACKED_LOOP (default OFF) 384 packed 2 x 26-bit `<number>` pairs — NUMERICALLY WRONG in Blink: `var()`
+                                substitutes a registered <number> as text with 6 significant digits (R3L fixture,
+                                R3L.md §2), so a 52-bit packed integer decodes to garbage. Kept for the record.
+
+Why (work/2026-09-19/R2A.md §3, R3L.md): the loop banks hold the residual vector between layers as 769 registered
+`<number>`s per bank; at every phase flip 769 delayed transitions START on the new read bank and 769 are cancelled
+on the new write bank (≈218 µs style + ≈107 µs paint lifecycle per start in the demo ≈ 0.25 s/layer ≈ 3 s/token).
+The fixture confirmed the cost is per started transition (385 starts: −11 ms style, −7.5 ms paint, −22 ms busy per
+flip; list length is not the cost — 8 shorter lists on 8 elements were slower).
+
+Font-axis carrier: HarfBuzz rounds HVAR-varied advances to integer font units and deltas are int16, so one glyph
+carries ≤ 16 bits; each carrier <i> therefore holds two glyphs whose advances add: hi (k_hi units at font-size
+512 px, UPM 256 → 2 px/unit, repeated 32× — HarfBuzz caps one advance at 32768 px) and lo (k_lo units at 4 px → 1/64 px/unit). Each glyph responds to its own axis
+("H%03X"/"L%03X", global value index) with delta 16384 over the normalised range, with a ZERO base advance, i.e. advance = k units for
+an integer axis value k ∈ [0, 16384] (fvar maxValue patched to 16384 so the list carries exact integers — integers
+survive the 6-digit var() serialisation). ≤ 256 axes per font (the tested browser path) → 6 fonts × 128 values.
+Write side (typed numbers on the bank; s = (v + 2048)·2 = today's width / 64 px):
+  k_hi = clamp(0, round(down, s, 1), 16383);  k_lo = clamp(0, round(down, (s − k_hi) · 4096, 1), 4095)
+Carrier width = max-content = 32·2·k_hi + k_lo/64 = 64·k_hi + k_lo/64 px = today's `262144px + v·128px`
+truncated to the 1/64-px LayoutUnit grid (today: float32 then truncation — equal or ±1 LayoutUnit). Read side
+(timelines, `--lp-*`, `.loop-input` decodes, R2F pass markers) unchanged.
+"""
+
+import hashlib
+import os
+from pathlib import Path
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+FONT_LOOP = flag("R3L_FONT_LOOP")
+PACKED_LOOP = flag("R3L_PACKED_LOOP", "0")
+if FONT_LOOP and PACKED_LOOP:
+    raise ValueError("R3L: set at most one of R3L_FONT_LOOP / R3L_PACKED_LOOP")
+
+WIDTH = 768
+PER_FONT = 128
+FONTS = WIDTH // PER_FONT
+DELTA = BASE_UNITS = 16384
+UPM = 256
+HI_PX, LO_PX = 512, 4                        # font sizes: 2 px/unit (x32 copies -> 64 px per k_hi) and 1/64 px/unit
+HI_COPIES = 32                               # HarfBuzz caps ONE glyph advance at 32768 px (16.16 positions); 32 x 32766 covers 2^20 px
+ASSETS = Path(__file__).resolve().parents[1] / "loop-carrier-assets"   # not under the `assets` symlink (-> F4)
+
+# ---- numeric packing (R3L_PACKED_LOOP; wrong in Blink, see module docstring)
+M26, MAXQ, SCALE, OFFSET = 67108864, 67108863, 8192, 2048
+
+
+def pairs(width):
+    if width % 2:
+        raise ValueError("R3L packing needs an even vector width")
+    return width // 2
+
+
+def quantize(src):
+    return f"clamp(0,round(nearest,({src} + {OFFSET}) * {SCALE},1),{MAXQ})"
+
+
+def pack(src_hi, src_lo):
+    return f"calc({quantize(src_hi)} * {M26} + {quantize(src_lo)})"
+
+
+def _packed_carrier_style(bank, i, width):
+    if i == width:
+        return f"--saved-{bank}-{width}:inherit;width:calc(262144px + var(--saved-{bank}-{width}) * 128px)"
+    p = f"var(--sv-{bank}-{i // 2})"
+    hi = f"round(down,{p} / {M26},1)"
+    body = f"calc({hi} * 0.015625px)" if i % 2 == 0 else f"calc(({p} - {hi} * {M26}) * 0.015625px)"
+    return f"--sv-{bank}-{i // 2}:inherit;width:{body}"
+
+
+# ---- shared API used by probe_native_reused_loop / browser_gpt2_reused_core
+def active(width):
+    return (FONT_LOOP or PACKED_LOOP) and width == WIDTH
+
+
+def latched_names(bank, width):
+    """The bank's transition-property list."""
+    if FONT_LOOP:
+        return [f"--lst-{bank}", f"--saved-{bank}-{width}"]
+    return [f"--sv-{bank}-{j}" for j in range(pairs(width))] + [f"--saved-{bank}-{width}"]
+
+
+def private_names(width):
+    """Registered helper properties that must stay non-inherited."""
+    if FONT_LOOP:
+        return [f"--l{h}-{b}-{i}" for b in range(2) for i in range(width) for h in "hl"] + [f"--lst-{b}" for b in range(2)]
+    return []
+
+
+def registrations(width):
+    """@property rules for the latched values (replaces the 2 x 769 `--saved-b-i` <number> registrations)."""
+    if FONT_LOOP:
+        css = "".join(f'@property --saved-{b}-{width}{{syntax:"<number>";inherits:false;initial-value:0}}' for b in range(2))
+        css += "".join(f'@property --lst-{b}{{syntax:"*";inherits:false;initial-value:"H000" 0}}' for b in range(2))
+        css += "".join(f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}' for p in private_names(width) if p.startswith("--l") and not p.startswith("--lst"))
+        return css
+    return "".join(f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}' for b in range(2) for p in latched_names(b, width))
+
+
+def transition_extra():
+    return ";transition-behavior:allow-discrete" if FONT_LOOP else ""
+
+
+def write_declarations(bank, width, epoch_source):
+    """Write-bank declarations (inside `@container loopcontrol style(--loop-phase:b)`)."""
+    if FONT_LOOP:
+        decls = []
+        for i in range(width):
+            s = f"(var(--loop-out-{i}) + 2048) * 2"
+            decls.append(f"--lh-{bank}-{i}:clamp(0,round(down,{s},1),16383)")
+            decls.append(f"--ll-{bank}-{i}:clamp(0,round(down,({s} - round(down,{s},1)) * 4096,1),4095)")
+        decls.append(f"--lst-{bank}:" + ",".join(f'"H{i:03X}" var(--lh-{bank}-{i}),"L{i:03X}" var(--ll-{bank}-{i})' for i in range(width)))
+        decls.append(f"--saved-{bank}-{width}:{epoch_source}")
+        return decls
+    decls = [f"--sv-{bank}-{j}:{pack(f'var(--loop-out-{2 * j})', f'var(--loop-out-{2 * j + 1})')}" for j in range(pairs(width))]
+    decls.append(f"--saved-{bank}-{width}:{epoch_source}")
+    return decls
+
+
+def carrier_markup(bank, i, width, timeline):
+    """The whole carrier element (incl. the F5 explicit forward of its non-inherited latched property)."""
+    if FONT_LOOP and i < width:
+        local = i % PER_FONT
+        return (f'<i class="loop-metric lf-{i // PER_FONT}" style="width:max-content;view-timeline:{timeline} inline">'
+                f'<b class="lh">{f"&#x{0xE000 + 2 * local:X};" * HI_COPIES}</b><b class="ll">&#x{0xE001 + 2 * local:X};</b></i>')
+    if FONT_LOOP:
+        style = f"--saved-{bank}-{width}:inherit;width:calc(262144px + var(--saved-{bank}-{width}) * 128px)"
+    else:
+        style = _packed_carrier_style(bank, i, width)
+    return f'<i class="loop-metric" style="{style};view-timeline:{timeline} inline"></i>'
+
+
+def style_css():
+    if not FONT_LOOP:
+        return ""
+    css = font_faces_css()
+    css += "".join(f".lf-{k}{{font-family:LoopCarrier{k}}}" for k in range(FONTS))
+    css += (".loop-metric{white-space:pre;line-height:1;font-kerning:none;letter-spacing:0;word-spacing:0}"
+            f".lh{{font-size:{HI_PX}px}}.ll{{font-size:{LO_PX}px}}")
+    css += "".join(f".loop-bank-{b}>.loop-scroll>.loop-track{{font-variation-settings:var(--lst-{b})}}" for b in range(2))
+    return css
+
+
+# ---- fonts
+def _tags(font_index):
+    out = []
+    for local in range(PER_FONT):
+        i = font_index * PER_FONT + local
+        out += [f"H{i:03X}", f"L{i:03X}"]
+    return out
+
+
+def ensure_fonts():
+    """Build the 6 loop-carrier woff2 files once (deterministic; fontTools HVAR via build_matrix_backend_prototypes)."""
+    # TrueType, not WOFF2: Chrome's WOFF2 decoder rejects these 256-axis fonts ("Failed to convert WOFF 2.0 font to
+    # SFNT", even the builder's own untouched woff2 — R3L fontprobe bisect); the TTF loads and varies correctly.
+    paths = [ASSETS / f"loop-carrier-{k}.ttf" for k in range(FONTS)]
+    if all(p.exists() for p in paths):
+        return paths
+    import numpy as np
+    from fontTools.ttLib import TTFont
+    import build_matrix_backend_prototypes as bm
+
+    ASSETS.mkdir(parents=True, exist_ok=True)
+    for k, path in enumerate(paths):
+        # 256 value glyphs (hi_i <- H_i, lo_i <- L_i, delta 16384, ZERO base advance) + 1 static witness glyph (U+E100) for font_barrier
+        weights = np.zeros((2 * PER_FONT + 1, 2 * PER_FONT), dtype=np.int16)
+        for g in range(2 * PER_FONT):
+            weights[g, g] = DELTA
+        ttf = path.with_name(f"build-{k}.ttf")
+        bm.build_direct_font_backend(weights, ttf, base_advance=BASE_UNITS, axis_tags=_tags(k))
+        font = TTFont(ttf, recalcTimestamp=False)
+        font["head"].unitsPerEm = UPM
+        for axis in font["fvar"].axes:
+            axis.maxValue = 16384
+        # advance-only glyphs: empty outlines (Chrome's WOFF2 decoder rejected the transformed glyf/hmtx of the
+        # post-edited outlines: "Failed to convert WOFF 2.0 font to SFNT"); no WOFF2 table transforms either
+        from fontTools.ttLib.tables._g_l_y_f import Glyph
+        glyf = font["glyf"]
+        for name in font.getGlyphOrder():
+            glyf[name] = Glyph()
+        font["head"].xMin = font["head"].yMin = font["head"].xMax = font["head"].yMax = 0
+        for name in font.getGlyphOrder():
+            font["hmtx"][name] = (font["hmtx"][name][0], 0)
+        for name in font.getGlyphOrder()[1:1 + 2 * PER_FONT]:
+            font["hmtx"][name] = (0, font["hmtx"][name][1])
+        font["post"].formatType = 3.0  # no glyph names
+        font.save(path)
+        ttf.unlink()
+        for stray in (ttf.with_suffix(".woff2"),):
+            if stray.exists():
+                stray.unlink()
+    return paths
+
+
+def font_faces_css():
+    css = ""
+    for k, path in enumerate(ensure_fonts()):
+        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
+        css += f'@font-face{{font-family:LoopCarrier{k};src:url("file://{path}?v={digest}") format("truetype")}}'
+    return css
```
