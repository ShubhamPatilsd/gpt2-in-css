# bundles/R2D — combined (F2 + F5 + F4) + head lock + `overflow:clip` + `contain:paint`

Built by R2D on 2026-09-19 (`work/2026-09-19/R2D/compile-R2D.sh R2D-cp`, then moved to `bundles/R2D`; 6.7 s). B0's recipe; F2/F5/F4 flags
as in `bundles/combined/BUILD.md` (all default ON). R2D flags (`work/2026-09-19/R2D/tools/r2d_knobs.py`; `=0` reverts each):

| flag | default | why (work/2026-09-19/R2D.md §3) |
|---|---|---|
| `R2D_HEAD_LOCK` | ON | harmless in 2 traced 2-token runs + the 8-token correctness run; the head's whole-DOM pass 470–583 ms vs 601–813 ms in `combined` (provisional) |
| `R2D_OVERFLOW_CLIP` | ON | layout −6 %/frame in both traced tokens, no other per-frame phase moved; no correctness effect |
| `R2D_POINTER_EVENTS` | **OFF** | hit-test 11.2 vs 10.7 ms/frame: no gain |
| `R2D_CONTAIN_PAINT` | ON | R2B MB9 (paint walk 12.6 → 0.02 ms/frame on a 50k-object static subtree); not A/B-measured here (B1 benches) |

Sibling bundles (no READY): `bundles/R2D-lock` (lock only; A/B arm A), `bundles/R2D-allknobs` (lock + clip + pointer-events; A/B arm B),
`bundles/R2D-lockclip` (lock + clip, defaults before `contain:paint`; correctness run #1).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2D
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R2D
```

## What R2D changed in the emitted bundle (vs `bundles/combined`; selector-level diff — everything else byte-identical, index.html identical)

| flag | rule before | rule after |
|---|---|---|
| `R2D_HEAD_LOCK` | `@container headinput not style(--head-input-epoch:0){.full-head{content-visibility:visible}}` (permanent unlock after token 1: the latched epoch never returns to 0) | removed; the head is unlocked only by the existing `@container b11-bridge style(--bridge-ready:1){.full-head{content-visibility:visible}}` (now emitted twice — by the lock and by the detached-output block; harmless) |
| `R2D_OVERFLOW_CLIP` | `.head-row{…overflow:hidden…}` (50,257), `.head-fine-row{…overflow:hidden…}` (256), `.metric{…overflow:hidden…}` (8,551) | `overflow:clip;min-width:0` — same clipping, no scroll container; `min-width:0` pins the grid items' automatic minimum to what a scroll container had |
| `R2D_CONTAIN_PAINT` | — | `.head-group,.head-fine,.loop-scroll,.embedding-scroller{contain:paint}` (no descendant of these roots is read from outside by anchor-size()/container units; no position:fixed descendant) |
| `R2D_POINTER_EVENTS` (OFF) | — | (when ON: `.position-embedding,.detached-head-reader,.font-status,.font-witness,.font-proof,.feedback-scroller,.native-signals{pointer-events:none}`) |

Font witnesses: 283 entries equal to `combined`. `launch_browser_gpt2.py --check`: 285 static files, 287,459,001 B, no runtime JavaScript.
NumPy reference ids (`R2D/reference_ids.log`, verify's recipe): `[11,314,1101,7926,11,475,314,1101]`. Asset URLs are relative
(`../../F2/global-projection-assets/...`, `../../F4/assets/font-vector-operators-f4/...`, `../../../../experiments/...`), all under the repo root.

## Tools copy

`work/2026-09-19/R2D/tools` = `work/2026-09-19/F4/tools` + `r2d_knobs.py` + five hunks in `browser_gpt2_runtime.py`.
Symlinks beside the copy: `experiments`, `data`, `global-projection-assets -> ../F2/global-projection-assets`, `assets -> ../F4/assets`.

## `diff -ru -x __pycache__ work/2026-09-19/F4/tools work/2026-09-19/R2D/tools`

```diff
diff -ru -x __pycache__ work/2026-09-19/F4/tools/browser_gpt2_runtime.py work/2026-09-19/R2D/tools/browser_gpt2_runtime.py
--- work/2026-09-19/F4/tools/browser_gpt2_runtime.py	2026-09-18 19:38:03
+++ work/2026-09-19/R2D/tools/browser_gpt2_runtime.py	2026-09-19 09:45:08
@@ -18,6 +18,7 @@
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
+import r2d_knobs as r2d
 import f5_scoping as f5
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
@@ -361,7 +362,17 @@
     # scorer on fallback fonts or provisional zero inputs during cold load.
     # The retained epoch never returns to zero after the first complete core,
     # so feedback geometry stays alive throughout subsequent iterations.
-    css += ".head-input-bank{container-name:headinput}.full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container headinput not style(--head-input-epoch:0){.full-head{content-visibility:visible}}"
+    if r2d.HEAD_LOCK:
+        # R2D: the head is skipped (style, layout, paint, compositing inputs,
+        # hit test) except while --bridge-ready:1, i.e. from the end of layer
+        # 11 until the epoch advances. The token slots live outside the head
+        # (detached output) and retain the winner by transition, so nothing
+        # reads the head's geometry while it is locked.
+        if not detached_output:
+            raise ValueError("R2D_HEAD_LOCK requires --detached-output")
+        css += r2d.head_lock_css(blocks)
+    else:
+        css += ".head-input-bank{container-name:headinput}.full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container headinput not style(--head-input-epoch:0){.full-head{content-visibility:visible}}"
     core = core.replace(
         "{child}",
         '<div class="final-normalization"><div class="head-input-bank"><i id="head-input-observer" style="position:fixed;top:-30px;width:calc(var(--head-input-epoch)*1px);height:1px"></i>'
@@ -541,6 +552,12 @@
             + '")'
         )
 
+    if r2d.OVERFLOW_CLIP:
+        css = r2d.overflow_clip(css)
+    if r2d.POINTER_EVENTS:
+        css += r2d.pointer_events_css()
+    if r2d.CONTAIN_PAINT:
+        css += r2d.contain_paint_css()
     css = re.sub(r'url\("(file:[^\"]+)"\)', relative_asset, css)
     (directory / "runtime.css").write_text(css)
     (directory / "index.html").write_text(
@@ -565,6 +582,7 @@
         scheduler="CSS receipts and SVG SMIL events",
         isolateHead=isolate_head,
         detachedOutput=detached_output,
+        **r2d.manifest(),
         headEpochTransport="separate geometry" if capacity > 8 else "packed four bits",
         fontBackend=font_backend,
         teacherForcedInputs=teacher_forced_tokens[:capacity]
Only in work/2026-09-19/R2D/tools: r2d_knobs.py
```

### `r2d_knobs.py` (new file)

```python
"""R2D (2026-09-19, round 2): lock the output head outside its own pass, and
cheap per-frame knobs. Every change is behind an environment flag:

  R2D_HEAD_LOCK=0      keep the head unlocked forever after token 1 (the
                       `@container headinput not style(--head-input-epoch:0)`
                       unlock rule); default ON.
  R2D_OVERFLOW_CLIP=0  keep `overflow:hidden` on the 50,257 `.head-row`, the
                       256 `.head-fine-row` and the 8,551 `.metric` carriers
                       (each a scroll container = a PaintLayer +
                       PaintLayerScrollableArea walked on every frame).
  R2D_POINTER_EVENTS=0 keep the compute roots hit-testable (Blink re-hit-tests
                       the last mouse position after every layout). Default OFF
                       (A/B 06:14: no gain).
  R2D_CONTAIN_PAINT=0  no `contain:paint` on the head-row groups / loop and
                       embedding scrollers (R2B MB9: paint containment on a
                       50k-object static subtree cuts the per-frame Paint walk
                       12.6 -> 0.02 ms).

Mechanism (bench/combined.md + audit SYNTHESIS §8.2): the head's 51,247-row
style pass is exactly one per token (its own evaluation), but the head rows
stay laid out, painted, compositing-input-walked and hit-tested on every one
of the ~85 frames per token although they change only once. A
`content-visibility:hidden` lock skips the subtree in style, layout, paint,
compositing inputs and hit testing; it is opened by the existing
`@container b11-bridge style(--bridge-ready:1)` stamp (the head's own
evaluation window: end of layer 11 -> the epoch advance) and closed by the
same stamp, so no new frames or animations.
"""

import os
import re


def flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "false", "no", "off")


HEAD_LOCK = flag("R2D_HEAD_LOCK")
OVERFLOW_CLIP = flag("R2D_OVERFLOW_CLIP")
POINTER_EVENTS = flag("R2D_POINTER_EVENTS", "0")
CONTAIN_PAINT = flag("R2D_CONTAIN_PAINT")

# Subtree roots whose geometry is never painted for the user and none of whose
# descendants is read from outside through anchor-size()/container units:
#   .head-group (197 x 256 head rows; the group itself is the anchor read by
#   .head-score-N, paint containment on the anchor does not affect that),
#   .head-fine (256 fine rows; anchor --head-local on itself), .loop-scroll
#   (1,538 loop carriers, read by view-timelines inside), .embedding-scroller
#   (769 carriers). NOT .position-embedding / .head-isolation / .full-head /
#   .head-coarse-reader: they contain .detached-head-source whose anchor is read
#   by .detached-head-reader outside, and `contain:paint` would also become the
#   containing block of every position:fixed probe/scroller inside. .scroller and
#   .readback already carry contain:strict. The roots contain no position:fixed
#   descendants; the absolutely positioned carriers keep their relative track as
#   containing block, so no geometry changes.
CONTAIN_PAINT_ROOTS = [".head-group", ".head-fine", ".loop-scroll", ".embedding-scroller"]  # A/B 06:14: hit-test 11.2 vs 10.7 ms/frame, no gain -> default OFF

# Compute subtrees no user interaction ever reaches. `.position-embedding`
# holds the core and the head; `.detached-head-reader` the token state
# (its `.token-display` is empty in the production build); the rest are
# off-screen probes.
POINTER_EVENTS_ROOTS = [
    ".position-embedding",
    ".detached-head-reader",
    ".font-status",
    ".font-witness",
    ".font-proof",
    ".feedback-scroller",
    ".native-signals",
]


def head_lock_css(blocks):
    """Replacement for the permanent head unlock: hidden unless the bridge
    stamp says the head input for the CURRENT epoch is ready."""
    return (
        ".head-input-bank{container-name:headinput}"
        ".full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
        f"@container b{blocks - 1}-bridge style(--bridge-ready:1){{.full-head{{content-visibility:visible}}}}"
    )


def _swap(css, old, new, expected):
    count = css.count(old)
    if count != expected:
        raise ValueError(f"R2D: expected {expected} x {old!r}, found {count}")
    return css.replace(old, new)


def overflow_clip(css):
    """`overflow:hidden` -> `overflow:clip` on the dense leaf populations.

    `clip` clips identically but does not make the box a scroll container, so
    Blink creates no PaintLayer / PaintLayerScrollableArea for it. The only
    sizing difference between the two values is the automatic minimum size of
    grid/flex items (`min-width:auto` is 0 for scroll containers, content-based
    otherwise); the head rows are grid items, so pin `min-width:0` explicitly.
    `.metric` is absolutely positioned (auto minimum already 0) but gets the
    same pin for clarity.
    """
    css = _swap(
        css,
        ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:hidden;",
        ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0;",
        1,
    )
    css = _swap(
        css,
        ".head-fine-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:hidden;",
        ".head-fine-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;min-width:0;",
        1,
    )
    css = _swap(
        css,
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:hidden;white-space:pre}",
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:clip;min-width:0;white-space:pre}",
        1,
    )
    return css


def pointer_events_css():
    return ",".join(POINTER_EVENTS_ROOTS) + "{pointer-events:none}"


def contain_paint_css():
    return ",".join(CONTAIN_PAINT_ROOTS) + "{contain:paint}"


def manifest():
    return {
        "r2dHeadLock": HEAD_LOCK,
        "r2dOverflowClip": OVERFLOW_CLIP,
        "r2dPointerEvents": POINTER_EVENTS,
        "r2dContainPaint": CONTAIN_PAINT,
    }
```
