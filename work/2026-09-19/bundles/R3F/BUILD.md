# bundles/R3F — combined3 (F2+F5+F4+R2C+R2F+R2D) + R2G `:has()` argument scoping, generalised (flag `R2G_SCOPED_HAS`, default ON)

Built by R3F on 2026-09-20 19:14 (`work/2026-09-19/R3F/compile.sh R3F 12 8`, log `R3F/compile-R3F.log`). Tools copy
`work/2026-09-19/R3F/tools` = `cp -R R2H/tools` + `r2g_has_scope.py` (new) + a 3-line hook in `browser_gpt2_runtime.py`
(the only two files that differ, see the diff below). Fonts / F2 projection shards / F4 assets are reused through the
`experiments -> ../../../experiments`, `data`, `global-projection-assets -> ../F2/global-projection-assets`, `assets -> ../F4/assets`
symlinks beside the tools copy (no new font files; `launch_browser_gpt2.py --check`: 285 static files, 286,652,618 B, no JavaScript).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3F
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R3F
```

## What R2G_SCOPED_HAS does here (R2G.md §4, generalised by R3F)

Every body-anchored `:has(#id.done)` / `:has(#id:checked)` argument in the sheet is rewritten to the exact direct-child chain of the id,
read from the emitted HTML and verified against it (`> :where(.detached-head-reader) > … > :where(.native-signals) > #token-3-captured.done`);
`:where()` steps keep the rule's specificity and cascade order identical. Blink then bounds the `:has()` traversal to the chain's depth
instead of walking body's whole 69k-element subtree once per distinct argument per restyle of a subject. 79 arguments in 69 rules:
`#run:checked` 26, `#token-N-captured.done` 33, `#token-N-advanced.done` 14 (7 `--epoch`, 7 `--pass-cap`), `#run-latched.done` 3,
`#fonts-loaded.done` 2, `#eos-done.done` 1. R2G's original 272 `.core-controller:where(:has(#loop-…))` rules no longer exist (R2F's lean
handshake removed them), so the expected gain is small (≈ −0.05 s/token, see `R3F.md` §3), not R2G's pre-R2F −0.35 s. Manifest key
`r2gScopedHas` (rewritten counts + chains); `R2G_SCOPED_HAS=0` reproduces `bundles/combined3`'s runtime.css exactly (offline check below).

## Offline verification (`R3F/offline_check.py R3F combined3`: PASS)

- rule-level diff vs `bundles/combined3`: 22,841 rules both; 69 added / 69 removed, every added rule is the scoped copy of a removed one
  (same declarations), no unscoped `:has(#id…)` left; `@property` and `@font-face` lists identical; `index.html` byte-identical to combined3;
  `font-witnesses.json` identical (modulo tools-copy path / mtime). runtime.css 39,981,992 B (combined3 39,966,130).
- NumPy reference (`R3F/reference_ids.py`, R3F tools): `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected.
- 2-layer smoke (`bundles/smoke-R3F-2L`, 2 blocks / 2 positions, vs `smoke-R3F-2L-ref` = flag off): offline PASS (21 rules / 25 arguments); Chrome
  run: see `R3F.md` §4.

## `diff -ruN -x __pycache__ work/2026-09-19/R2H/tools work/2026-09-19/R3F/tools`

```diff
diff -ruN -x __pycache__ R2H/tools/browser_gpt2_runtime.py R3F/tools/browser_gpt2_runtime.py
--- R2H/tools/browser_gpt2_runtime.py	2026-09-19 10:10:29
+++ R3F/tools/browser_gpt2_runtime.py	2026-09-20 19:07:21
@@ -21,6 +21,7 @@
 import r2d_knobs as r2d
 import f5_scoping as f5
 import r2c_hoist as r2c
+import r2g_has_scope as r2g
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -562,8 +563,7 @@
     if r2d.CONTAIN_PAINT:
         css += r2d.contain_paint_css()
     css = re.sub(r'url\("(file:[^\"]+)"\)', relative_asset, css)
-    (directory / "runtime.css").write_text(css)
-    (directory / "index.html").write_text(
+    page = (
         '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><title>Native GPT-2 • Chromium • no JavaScript</title><link rel="stylesheet" href="runtime.css"></head><body>'
         + controls
         + font_html
@@ -571,7 +571,14 @@
         + f'<i id="core-epoch-observer" style="position:fixed;top:-30px;width:anchor-size(--block-{blocks - 1}-probe-epoch width,0px);height:1px"></i>'
         + "</body></html>"
     )
+    r2g_stats = None
+    if r2g.SCOPED_HAS:
+        # R2G/R3F: fixed-depth `:has()` arguments for every handshake rule (chains verified against the page).
+        css, r2g_stats = r2g.scope_has_arguments(css, page, capacity)
+    (directory / "runtime.css").write_text(css)
+    (directory / "index.html").write_text(page)
     metadata.update(
+        r2gScopedHas=r2g_stats,
         fontFaces=font_count,
         autostart=autostart,
         head="full-vocabulary-q16-two-pass",
diff -ruN -x __pycache__ R2H/tools/r2g_has_scope.py R3F/tools/r2g_has_scope.py
--- R2H/tools/r2g_has_scope.py	1969-12-31 16:00:00
+++ R3F/tools/r2g_has_scope.py	2026-09-20 19:11:14
@@ -0,0 +1,155 @@
+"""R2G (as applied by R3F): bound the traversal of every handshake `:has()` argument.
+
+Why (R2G.md §3b/§4): Blink's `:has()` matcher walks the anchor's WHOLE subtree once per distinct argument
+(the fast-reject filter cannot reject `#id.done` once any `.done` exists), in reverse DOM order. With only
+child combinators in the argument Blink limits the traversal to a fixed depth
+(check_pseudo_has_argument_context.cc). R2G rewrote the 272 `.core-controller:where(:has(#loop-…))` rules
+(gone since R2F's lean handshake), the 7 `:where(body:has(#token-N-advanced.done)) .core-controller` rules
+and the `.core-block` visibility rule. R3F generalises the rewrite to EVERY body-anchored `:has(#id…)`
+argument in the sheet (token captured/advanced, run/run-latched/fonts-loaded/eos-done, N-ready/ack
+subjects): each `:has(#id.done)` / `:has(#id:checked)` becomes `:has(> .a > .b > … > #id.done)` with the
+exact ancestor chain read from the emitted HTML, and the chain is VERIFIED (the id's ancestor path must
+start at the anchor and equal the chain), so a DOM change fails the build instead of emitting a handshake
+that never fires. `:has()` takes the specificity of its most specific argument, so every chain step is
+written as `> :where(.a)` (zero specificity): the rewritten rules keep exactly their original specificity and
+cascade order (the token-slot / epoch / handshake rules compete with @container rules on the same properties).
+Flag: R2G_SCOPED_HAS (default on).
+"""
+from __future__ import annotations
+
+import html.parser
+import os
+import re
+
+SCOPED_HAS = os.environ.get("R2G_SCOPED_HAS", "1") not in ("0", "false", "no", "off")
+
+LOOP_CHAIN = [".core-block", ".loop-reader", ".loop-input", ".loop-signals"]
+
+
+class _Paths(html.parser.HTMLParser):
+    """Ancestor path (tag, classes) of every element with an id we care about."""
+
+    def __init__(self, wanted):
+        super().__init__()
+        self.wanted = wanted
+        self.stack = []
+        self.paths = {}
+
+    def handle_starttag(self, tag, attrs):
+        d = dict(attrs)
+        if d.get("id") in self.wanted:
+            self.paths[d["id"]] = list(self.stack)
+        if tag not in {"br", "meta", "link", "input", "img", "hr", "set", "option"}:
+            self.stack.append((tag, d.get("class", "").split()))
+
+    def handle_startendtag(self, tag, attrs):
+        d = dict(attrs)
+        if d.get("id") in self.wanted:
+            self.paths[d["id"]] = list(self.stack)
+
+    def handle_endtag(self, tag):
+        if self.stack and self.stack[-1][0] == tag:
+            self.stack.pop()
+
+
+def _step(tag, classes):
+    return f".{classes[0]}" if classes else tag
+
+
+def _chain_from(path, anchor_index):
+    steps = [_step(t, c) for t, c in path[anchor_index + 1 :]]
+    return " ".join(f"> :where({s})" for s in steps)
+
+
+def scope_has_arguments(css: str, page_html: str, capacity: int) -> tuple[str, dict]:
+    """Rewrite every handshake `:has()` argument to a fixed-depth child chain; verify against page_html."""
+    id_args = sorted(set(re.findall(r":has\((#[\w-]+)(?:\.done|:checked)\)", css)))
+    ids = set(a.lstrip("#") for a in id_args)
+    parser = _Paths(ids)
+    parser.feed(page_html)
+    paths = parser.paths
+    missing = ids - set(paths)
+    if missing:
+        raise ValueError(f"R2G: :has() ids not found in the page: {sorted(missing)[:8]}")
+
+    def anchor(path, klass):
+        for i, (tag, classes) in enumerate(path):
+            if klass in classes or tag == klass:
+                return i
+        raise ValueError(f"anchor {klass} not found in path {path}")
+
+    stats = {"rewritten": {}, "chains": {}}
+    total = 0
+
+    # 1. R2G's original loop rules (absent when R2F's lean handshake is on): anchor .core-controller.
+    n_loop = 0
+    if re.search(r"\.core-controller:where\(:has\(#loop-", css):
+        for key in ("loop-captured-1", "loop-advanced-1"):
+            p = paths[key]
+            below = p[anchor(p, "core-controller") + 1 :]
+            if [c[0] for t, c in below] != [s.lstrip(".") for s in LOOP_CHAIN]:
+                raise ValueError(f"loop signal chain mismatch for {key}: {below}")
+        loop_chain = " ".join(f"> :where({s})" for s in LOOP_CHAIN)
+        css, n_loop = re.subn(
+            r"\.core-controller:where\(:has\((#loop-(?:captured|advanced)-\d+\.done)\)\)",
+            lambda m: f".core-controller:where(:has({loop_chain} > {m[1]}))",
+            css,
+        )
+        stats["chains"]["loop"] = loop_chain
+    stats["rewritten"]["loop"] = n_loop
+    total += n_loop
+
+    # 2. every body-anchored `:has(#id.done)` / `:has(#id:checked)`: chain = ancestors strictly below body.
+    #    A compound may carry several :has() (`body:has(#run:checked):has(#token-N-captured.done)`); each
+    #    occurrence is rewritten in place after verifying that, skipping earlier balanced `:has(...)` groups,
+    #    the compound is anchored on `body`.
+    chains = {}
+    for arg in id_args:
+        key = arg.lstrip("#")
+        if key.startswith("loop-"):
+            continue
+        p = paths[key]
+        chain = _chain_from(p, anchor(p, "body"))
+        if not chain:
+            raise ValueError(f"{key} is a direct child of body (nothing to scope)")
+        chains[key] = chain
+        stats["rewritten"][key] = 0
+        stats["chains"][key] = chain
+
+    def anchored_on_body(text, pos):
+        """text[:pos] ends with the compound preceding `:has(`: skip balanced `:has(...)` groups, expect `body`."""
+        i = pos
+        while text.endswith(")", 0, i):
+            depth, j = 0, i - 1
+            while j >= 0:
+                if text[j] == ")":
+                    depth += 1
+                elif text[j] == "(":
+                    depth -= 1
+                    if depth == 0:
+                        break
+                j -= 1
+            if j < 4 or text[j - 4 : j + 1] != ":has(":
+                return False
+            i = j - 4
+        return text.endswith("body", 0, i)
+
+    def rewrite(m):
+        key = m[1].lstrip("#")
+        if key.startswith("loop-") or key not in chains:
+            return m[0]
+        if not anchored_on_body(css, m.start()):
+            raise ValueError(f"R2G: :has({m[1]}) not anchored on body at {css[max(0, m.start() - 80):m.start()]!r}")
+        stats["rewritten"][key] += 1
+        return f":has({chains[key]} > {m[1]}{m[2]})"
+
+    css = re.sub(r":has\((#[\w-]+)(\.done|:checked)\)", rewrite, css)
+    total += sum(v for k, v in stats["rewritten"].items() if k != "loop")
+
+    left = re.findall(r":has\(#[\w-]+(?:\.done|:checked)\)", css)
+    if left:
+        raise ValueError(f"R2G: unscoped :has() arguments left: {sorted(set(left))[:8]}")
+    if stats["rewritten"].get("token-1-advanced", 0) != 2 or total == 0:
+        raise ValueError(f"R2G: unexpected :has() rule counts {stats['rewritten']}")
+    stats["total"] = total
+    return css, stats
```

## Chrome correctness run (R3F.md §5)

ONE passive run, `R3F/run_chrome.sh correctness-12L 900 correctness_inner.sh R3F` (F4's correctness_run.mjs, heap flag, 5 s poll), 21:11:45–21:15:47 AC:
ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]**, done markers 8/8, verify rc=0 (tokenAgreement 8×True, rmse 0.02005934198718561 = combined3), RecalcStyleCount 1116 /
LayoutCount 720 (Performance.getMetrics at the end; combined3 1107/710). READY created 2026-09-20 21:16:44.
