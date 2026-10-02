# bundles/combined8-c32-fast — `combined8-c32` + R6L load-time fix (in-body `<link>` + inline boot `<style>`), capacity 32, 12 blocks

Built by R6L on 2026-09-30 15:50 with `work/2026-09-19/R6L/compile.sh` (= `R5X/compile.sh` + `R6L_*` passthrough; tools copy `R6L/tools` = `R5X/tools`
+ `r6l_boot.py` + 3 hunks in `browser_gpt2_runtime.py`, diff below). Reference: `bundles/combined8-c32` (32/32 on prompt 40, 905.6 s). Same fonts (relative URLs
into `experiments/…`, `F2/…`, `F4/…`, `R5X/assets-r5h/…`; `launch_browser_gpt2.py --check`: 285 static files, 296,449,715 B, no JavaScript).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6L/compile.sh $PWD/bundles/combined8-c32-fast 32 12
# = combined8-c32's exports (bundles/combined8-c32/BUILD.md) plus R6L_BODY_LINK=1 R6L_BOOT=1 →
#   uv run --with numpy --with fonttools --with pillow --with brotli python tools/browser_gpt2_runtime.py \
#     --blocks 12 --capacity 32 --reuse-core --cache-codec font-vector --cache-layout flat --scoped-state --isolate-head \
#     --detached-output --value-layout widths --font-backend original --output .../bundles/combined8-c32-fast
```

## Why (R6L.md §1)

`R5X/run-combined8-c32/c32-p40.json` (the 32/32 run): HTML parsed by 0.17 s (domInteractive), then ONE 30.8 s main-thread task with LayoutCount 1 /
LayoutDuration 31.4 s and 169k layout objects already present, while `runtime.css` (50 MB) has responseEnd 31.8 s — its body stalls behind the blocked
main thread. Chrome laid out the UA-styled model markup (84,592 `<i>`, 780k characters in planes 2–7 → a system font-fallback lookup per character)
before the head stylesheet had arrived. CSS parse + first styled recalc (1.1 s) + 283 font fetches/decodes + first paint (33.1 s) + load (34.3 s) take 2.5 s.

## Flags (new; the rest as `bundles/combined8-c32/BUILD.md`)

| flag | default | effect |
|---|---|---|
| `R6L_BODY_LINK` | 1 | `<link rel="stylesheet" href="runtime.css">` is the first child of `<body>` instead of the last of `<head>`. Chromium treats a parser-inserted body stylesheet as parser-blocking: nothing after it is parsed until the sheet has loaded, so the model markup never exists in the UA-only state; content before it paints immediately. Cascade order unchanged (the link still follows the inline `<style>`). |
| `R6L_BOOT` | 1 | `<head>` gets `<style>html::before{content:"Loading the model stylesheet (50 MB)…";display:block;…}body{display:none}</style>`; `runtime.css` ends with `html::before{content:none}body{display:block}` (later author sheet, equal specificity → wins). The boot line is the only thing painted during the CSS phase; `body{display:none}` makes any UA-styled layout of already-parsed body content free. `R6L_BOOT_TEXT` overrides the message. |

Manifest adds `r6lBodyLink`, `r6lBoot`. **Merge note:** R6V's `R6V_EARLY_PAINT` is the same structural change (inline head style + body link, with the
controls and a loading panel before the link). A merged bundle must take one of the two (`R6L/split-point.md`: take R6V's, set `R6L_BODY_LINK=0 R6L_BOOT=0`).

## Offline verification (`R6L/check_identity.py bundles/combined8-c32-fast bundles/combined8-c32 --expect-r6l` → RESULT: PASS)

- `index.html` == `combined8-c32/index.html` with exactly `<link …></head><body>` → `<style>…</style></head><body><link …>` (6,221,370 B both after the transform; 280 B added).
- `runtime.css` == `combined8-c32/runtime.css` + `html::before{content:none}body{display:block}` (49,311,059 = 49,311,006 + 53 B; the prefix is byte-identical).
- `font-witnesses.json` identical (283/283, ignoring mtime/agent dir); manifest differs only by the two `r6l*` keys; 285 static files, no JS.
- Flag-off path: `head_html()` returns the original `<link>` string, `body_prefix()` and the css tail are empty → the emitter's page/CSS strings are the
  pre-R6L expressions verbatim (see the diff); the flag-on build equalling `transform(reference)` byte-for-byte shows nothing else in the emitter moved.
- **Flag-off twin** (`R6L_BODY_LINK=0 R6L_BOOT=0` → `R6L/scratch/c32-alloff`, deleted after the check): `index.html` byte-identical to `combined8-c32`
  (6,221,102 B); `runtime.css` identical after `../`-depth normalisation (`check_identity.py --normalize-urls`; the scratch dir is one level deeper,
  +849 B = 283 url() × 3); witnesses 283/283; manifest +`r6lBodyLink:false`,`r6lBoot:false` → PASS.
- Numerics: no rule, declaration, element or font of the model changed; `body`'s computed `display` is `block` before and after (UA default vs the tail).

## Chrome

Load timing (3 loads/arm, R6L/load_native.mjs) and the ONE prompt-40 32-token correctness run are armed behind the machine gate (`R6L/gate_wait.sh`);
results are appended to `R6L.md` §2/§4 when they land. Until then this bundle has **no READY**.

## `diff -ruN -x __pycache__ R5X/tools R6L/tools`

```diff
diff -ruN -x __pycache__ R5X/tools/browser_gpt2_runtime.py R6L/tools/browser_gpt2_runtime.py
--- R5X/tools/browser_gpt2_runtime.py	2026-09-24 16:21:15
+++ R6L/tools/browser_gpt2_runtime.py	2026-09-30 15:26:19
@@ -24,6 +24,7 @@
 import r2g_has_scope as r2g
 import r3h_blockflow_max as r3h
 import r5e_dead_weight as r5e
+import r6l_boot as r6l
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -571,7 +572,10 @@
         css += r2d.contain_paint_css()
     css = re.sub(r'url\("(file:[^\"]+)"\)', relative_asset, css)
     page = (
-        '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><title>Native GPT-2 • Chromium • no JavaScript</title><link rel="stylesheet" href="runtime.css"></head><body>'
+        '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><title>Native GPT-2 • Chromium • no JavaScript</title>'
+        + r6l.head_html()  # R6L: inline boot <style>; the <link> moves into <body> (parser-blocking, not render-blocking)
+        + '</head><body>'
+        + r6l.body_prefix()
         + controls
         + font_html
         + model
@@ -586,8 +590,10 @@
     if r5e.LEAN_WALLS:
         # R5E: shrink the two inheritance walls to the properties that can be non-initial there
         css, r5e_stats = r5e.lean_walls(css, page)
+    css = r6l.finish_css(css)  # R6L: `html::before{content:none}body{display:block}` at the very end of the sheet
     (directory / "runtime.css").write_text(css)
     (directory / "index.html").write_text(page)
+    metadata.update(r6l.manifest())
     metadata.update(
         r2gScopedHas=r2g_stats,
         fontFaces=font_count,
diff -ruN -x __pycache__ R5X/tools/r6l_boot.py R6L/tools/r6l_boot.py
--- R5X/tools/r6l_boot.py	1969-12-31 16:00:00
+++ R6L/tools/r6l_boot.py	2026-09-30 15:26:19
@@ -0,0 +1,62 @@
+"""R6L (2026-09-30): stop the 31 s unstyled layout at page load and paint a boot message first.
+
+R5X/run-combined8-c32/c32-p40.json: with `<link rel=stylesheet href=runtime.css>` in <head>, Chrome
+parses the 7 MB body in 0.17 s, then spends ONE 30.8 s main-thread task (LayoutCount 1,
+LayoutDuration 31.4 s, 169k layout objects) laying out the UA-styled model markup — 84,592 <i>
+elements whose 780k text characters live in unassigned/PUA planes, so every character runs a
+system font-fallback lookup — while the 50 MB stylesheet body stalls behind the blocked main
+thread (responseEnd 31.8 s). CSS parse + first styled recalc + fonts + first paint then take 2.5 s.
+
+  R6L_BODY_LINK=1  the <link> moves from <head> to the start of <body>. A parser-inserted body
+                   stylesheet is parser-blocking in Chromium: nothing after it is parsed until the
+                   sheet has loaded, so the model markup never exists in the UA-only state and the
+                   content before the link paints immediately. Cascade order is unchanged (the link
+                   still follows the inline boot <style>). Every other byte of the page is identical.
+  R6L_BOOT=1       an inline <style> in <head>: `html::before` shows a one-line boot message and
+                   `body{display:none}` guarantees a zero-cost layout should any Chrome version lay
+                   out UA-styled content before the sheet applies. runtime.css ends with
+                   `html::before{content:none}body{display:block}` (later author sheet, same
+                   specificity → wins), restoring the exact pre-R6L computed values.
+Both default ON. Flag-off build == bundles/combined8-c32 byte-for-byte (index.html and runtime.css).
+"""
+
+import os
+
+BODY_LINK = os.environ.get("R6L_BODY_LINK", "1") == "1"
+BOOT = os.environ.get("R6L_BOOT", "1") == "1"
+BOOT_TEXT = os.environ.get(
+    "R6L_BOOT_TEXT",
+    "Loading the model stylesheet (50 MB)… Chrome parses it, then loads the 283 weight fonts (239 MB). "
+    "Nothing else is shown until then.",
+)
+
+LINK_HTML = '<link rel="stylesheet" href="runtime.css">'
+
+
+def head_style():
+    """Inline shell sheet: applied before runtime.css exists; overridden by css_tail()."""
+    text = BOOT_TEXT.replace("\\", "\\\\").replace('"', '\\"')
+    return (
+        "<style>html::before{content:\"" + text + "\";display:block;margin:24px;"
+        "font:16px/1.5 system-ui;color:#222;background:#f7f5ef}body{display:none}</style>"
+    )
+
+
+def css_tail():
+    return "html::before{content:none}body{display:block}"
+
+
+def head_html():
+    return (head_style() if BOOT else "") + ("" if BODY_LINK else LINK_HTML)
+
+
+def body_prefix():
+    return LINK_HTML if BODY_LINK else ""
+
+
+def finish_css(css):
+    return css + css_tail() if BOOT else css
+
+
+def manifest():
+    return {"r6lBodyLink": BODY_LINK, "r6lBoot": BOOT}
```
