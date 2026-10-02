# bundles/R5E — combined7 + R5E dead-weight removal (capacity 8, 12 layers, `runs` layout)

Built by R5E on 2026-09-24 12:45 with `work/2026-09-19/R5E/compile.sh` (= R4M/compile.sh's combined7 recipe: every round-2..4 flag ON,
`R4T_CONSUMER_CHUNK=64`) on the tools copy `work/2026-09-19/R5E/tools` (= `R4M/tools7` + `r5e_dead_weight.py` + 5 edited files; diff below).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
./R5E/compile.sh /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R5E 12 8
# expands to (all combined7 flags exported, plus the R5E defaults below):
uv run --with numpy --with fonttools --with pillow --with brotli \
  python R5E/tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R5E
```

## Flags (all in `R5E/tools/r5e_dead_weight.py`; combined7's flags unchanged)

| flag | default | effect | exactness |
|---|---|---|---|
| `R5E_LEAN_WALLS` | 1 | `.core-reset` 16,156 `--p:initial` → 0; `.head-isolation` 24,105 → 3,865 (kept = registered properties declared/animated/inline on an ancestor-or-self of the wall element, derived mechanically from the assembled page + sheet at build time) | a property no ancestor declares or animates is at its initial value on the wall's parent, so `initial` there is a no-op; every property that can change above the wall is still pinned → same computed values, same dirtying |
| `R5E_LP_INHERIT` | 1 | `--lp-*` (proj readback numbers) stay `inherits:true`; the 768 `--lp-i:inherit` forwards on `.loop-input` and R4T's 4,224 forwards on `.loop-reader-cK` are not emitted | same values at `.loop-input`; the subtree they now inherit into is the one `--loop-in-*` (inherits:true) already dirty in the same pass |
| `R5E_DROP_DEAD_LISTS` | 1 | `.fvs-query{--fvs-all-fields}` and 8 `--fvs-retained-S` lists not emitted (F5_BANK_LITERAL_LISTS inlines the literals; 0 `var()` readers in the sheet) | unread, unregistered declarations |
| `R5E_KEEP_DIAG` | 0 | removes the 3 readback probe pairs (`#core-probe`, `#block-11-probe`, `#reused-probe` + `*-epoch` twins; 15–19 KB inline width calcs over 768 `var()`, position:fixed) and `#core-epoch-observer`; `=1` keeps them for geometry-readback diagnostics | the verifier reads computed styles of `#core-result`, `.head-input-bank`, `.fvs-bank-L`, `.token-slot-N` — all kept |

Manifest keys: `r5eLeanWalls`, `r5eLpInherit`, `r5eDropDeadLists`, `r5eKeepDiag`, `r5eLeanWallStats`.

## Offline verification (`R5E/offline_check.py bundles/R5E bundles/combined7` → `R5E/offline_check-R5E.log`, RESULT: PASS)

- **All four flags off** (`R5E/scratch/off-8`, same recipe): `index.html` byte-identical to `bundles/combined7`; `runtime.css` identical after relative-URL normalisation; manifest +5 keys.
- CSS rule-level diff vs combined7 confined to: `.head-isolation` (462,918 → 78,925 B), `.core-reset` (309,076 → 50 B), 11 `.loop-reader-cN` (90,351 → 19,717 B), `.loop-input` forward rule (12,945 → 0 B), 768 `@property --lp-N` (`inherits:false` → `true`), 9 `.fvs-query` list rules removed (15,809 B). Nothing else differs.
- HTML: removing the 6 readback probes + `#core-epoch-observer` from combined7's index.html gives bundles/R5E's byte-for-byte. Elements 67,569 → 67,562; inline style bytes 1,854,714 → 1,803,867.
- Sizes: runtime.css 39,073,102 → 38,279,819 B (−793 KB); index.html 5,612,552 → 5,561,375.
- `font-witnesses.json` 283/283 identical; `launch_browser_gpt2.py --check`: 285 static files, `runtimeJavaScript: false`; NumPy reference ids (`R5E/reference_ids.py` on this tools copy) = 11,314,1101,7926,11,475,314,1101.
- `lean_walls` re-derived independently on combined7's own page + sheet gives the same kept/dropped counts (core-reset 0/16,156; head-isolation 3,865/20,240; kept families: `--bridge-p-N`, `--embed-N`, `--embedp-N`, `--x-N`, `--final-h-N` ×768, `--feedback-N`, `--feedback-p-N` ×8, plus `--bridge-ready --bridge-stamp --embed-ready --embed-stamp --epoch --final-mean --final-var --frozen-prompt --token`).

## Chrome

See `R5E.md` §4: smoke pair identical tokens + identical pass counts (−26 elements = the probes); ONE 8-token correctness run 16:00: 8/8 ids, verify rc 0, residual rmse 0.016055 → READY 16:00:59.

## `diff -ruN -x __pycache__ work/2026-09-19/R4M/tools7 work/2026-09-19/R5E/tools`

```diff
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_font_vector_cache.py R5E/tools/browser_gpt2_font_vector_cache.py
--- R4M/tools7/browser_gpt2_font_vector_cache.py	2026-09-21 01:39:46
+++ R5E/tools/browser_gpt2_font_vector_cache.py	2026-09-24 12:42:11
@@ -14,6 +14,7 @@
 import f4_packing as f4
 import f5_scoping as f5
 import r4d_flags as r4d
+import r5e_dead_weight as r5e
 import r2c_hoist as r2c
 import r4s_small_hops as r4s
 import numpy as np
@@ -210,9 +211,8 @@
     )
     literal = f5.BANK_LITERAL_LISTS
     css += (
-        ".fvs-query{--fvs-all-fields:"
-        + ",".join(all_fields)
-        + "}.fvs-bank{transition-property:"
+        ("" if (literal and r5e.DROP_DEAD_LISTS) else ".fvs-query{--fvs-all-fields:" + ",".join(all_fields) + "}")  # R5E: unread when literal
+        + ".fvs-bank{transition-property:"
         + (",".join(all_fields) if literal else "var(--fvs-all-fields)")
         + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
     )
@@ -303,7 +303,8 @@
             name for name in all_fields
             if name not in fields and (not lean or f4.slot_of(name) < slot)
         ) or "none"
-        css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
+        if not (literal and r5e.DROP_DEAD_LISTS):  # R5E: unread when literal
+            css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
         writes = []
         if packed:
             # F4: the 12 live head lists concatenate into one latched list per kind.
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_reused_adapter.py R5E/tools/browser_gpt2_reused_adapter.py
--- R4M/tools7/browser_gpt2_reused_adapter.py	2026-09-21 01:39:46
+++ R5E/tools/browser_gpt2_reused_adapter.py	2026-09-24 12:42:11
@@ -17,6 +17,7 @@
 import r4s_small_hops as r4s
 import r4d_flags as r4d
 import r4t_consumer_chunk as r4t
+import r5e_dead_weight as r5e
 
 
 def compile_reused_runtime_core(
@@ -84,9 +85,9 @@
     source = source.replace("var(--epoch)", "var(--position)")
     export = (
         '<div class="reused-final-export">'
-        + hybrid.probe(f"block-{last}-probe", "out", 768).replace(
+        + (hybrid.probe(f"block-{last}-probe", "out", 768).replace(
             "var(--epoch)", "var(--position)"
-        )
+        ) if r5e.KEEP_DIAG else "")  # R5E: diagnostic readback only
         + source
         + "</div>"
     )
@@ -171,7 +172,8 @@
             body, "var(--position)", "pass-reader"
         )
         # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists
-        if tagged != (6 if r4s.SMALL_HOPS else 7) or tagged_position != 2:
+        diag = 1 if r5e.KEEP_DIAG else 0  # R5E: the reused-probe / block-11-probe epoch twins
+        if tagged != (6 if r4s.SMALL_HOPS else 7) - 1 + diag or tagged_position != 1 + diag:
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -199,7 +201,7 @@
     receiver = receiver.replace(
         "{child}",
         '<div id="core-result">'
-        + hybrid.probe("core-probe", "x", 768)
+        + (hybrid.probe("core-probe", "x", 768) if r5e.KEEP_DIAG else "")  # R5E
         + "{child}</div>",
     )
     body = (
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_reused_core.py R5E/tools/browser_gpt2_reused_core.py
--- R4M/tools7/browser_gpt2_reused_core.py	2026-09-21 01:39:46
+++ R5E/tools/browser_gpt2_reused_core.py	2026-09-24 12:42:11
@@ -16,6 +16,7 @@
 import f5_scoping as f5
 import r2c_hoist as r2c
 import r3r_fold_hop as r3r
+import r5e_dead_weight as r5e
 import r4t_consumer_chunk as r4t
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
@@ -303,7 +304,7 @@
         )
     inner = (
         '<div class="reused-output" id="reused-result">'
-        + h.probe("reused-probe", "out", W)
+        + (h.probe("reused-probe", "out", W) if r5e.KEEP_DIAG else "")  # R5E
         + output.replace("{child}", '<i id="loop-result"></i>')
         + "</div>"
     )
@@ -345,7 +346,8 @@
                 f"--gate-{kind}",
             ]
         if r3r.FOLD_HOP:
-            lp, saved, outputs = r3r.reader_names(W), [], []
+            # R5E: --lp-* stay inherits:true (no forwards) under R5E_LP_INHERIT
+            lp, saved, outputs = ([] if r5e.LP_INHERIT else r3r.reader_names(W)), [], []
         else:
             lp = [f"--lp-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
             saved = [f"--saved-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_runtime.py R5E/tools/browser_gpt2_runtime.py
--- R4M/tools7/browser_gpt2_runtime.py	2026-09-21 01:39:46
+++ R5E/tools/browser_gpt2_runtime.py	2026-09-24 12:42:11
@@ -23,6 +23,7 @@
 import r2c_hoist as r2c
 import r2g_has_scope as r2g
 import r3h_blockflow_max as r3h
+import r5e_dead_weight as r5e
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -460,7 +461,7 @@
         model, tagged = f5.tag_inline_readers(
             model, "var(--epoch)", "epoch-reader", skip_class="pass-reader"
         )
-        if tagged != 3:
+        if tagged != (3 if r5e.KEEP_DIAG else 2):  # R5E: #core-probe's epoch twin
             raise ValueError(f"Unexpected inline epoch readers in model: {tagged}")
     font_html, font_css, font_count = font_barrier(css, directory)
     css += font_css
@@ -574,13 +575,17 @@
         + controls
         + font_html
         + model
-        + f'<i id="core-epoch-observer" style="position:fixed;top:-30px;width:anchor-size(--block-{blocks - 1}-probe-epoch width,0px);height:1px"></i>'
+        + (f'<i id="core-epoch-observer" style="position:fixed;top:-30px;width:anchor-size(--block-{blocks - 1}-probe-epoch width,0px);height:1px"></i>' if r5e.KEEP_DIAG else '')  # R5E
         + "</body></html>"
     )
     r2g_stats = None
     if r2g.SCOPED_HAS:
         # R2G/R3F: fixed-depth `:has()` arguments for every handshake rule (chains verified against the page).
         css, r2g_stats = r2g.scope_has_arguments(css, page, capacity)
+    r5e_stats = None
+    if r5e.LEAN_WALLS:
+        # R5E: shrink the two inheritance walls to the properties that can be non-initial there
+        css, r5e_stats = r5e.lean_walls(css, page)
     (directory / "runtime.css").write_text(css)
     (directory / "index.html").write_text(page)
     metadata.update(
@@ -600,6 +605,8 @@
         detachedOutput=detached_output,
         **r2d.manifest(),
         r3hBlockflowMax=r3h.BLOCKFLOW_MAX,
+        **r5e.manifest(),
+        r5eLeanWallStats=r5e_stats,
         headEpochTransport="separate geometry" if capacity > 8 else "packed four bits",
         fontBackend=font_backend,
         teacherForcedInputs=teacher_forced_tokens[:capacity]
diff -ruN -x __pycache__ R4M/tools7/r3r_fold_hop.py R5E/tools/r3r_fold_hop.py
--- R4M/tools7/r3r_fold_hop.py	2026-09-21 01:39:46
+++ R5E/tools/r3r_fold_hop.py	2026-09-24 12:42:11
@@ -47,6 +47,7 @@
 import os
 
 import r4t_consumer_chunk as r4t
+import r5e_dead_weight as r5e
 from build_pretrained_gpt2 import css_number as num
 
 
@@ -133,7 +134,7 @@
             ids = range(k * r4t.CHUNK, min(width, (k + 1) * r4t.CHUNK))
             # --lp-* are registered inherits:false by the core's scoped_state and forwarded with `inherit` at .loop-input
             # (one level): every chunk element must forward the earlier chunks' values so the innermost one holds all of them.
-            forward = "".join(f";--lp-{i}:inherit" for i in range(0, k * r4t.CHUNK))
+            forward = "" if r5e.LP_INHERIT else "".join(f";--lp-{i}:inherit" for i in range(0, k * r4t.CHUNK))  # R5E
             css += (
                 f".{cls}{{animation-name:"
                 + ",".join(f"lpk{i}" for i in ids)
diff -ruN -x __pycache__ R4M/tools7/r5e_dead_weight.py R5E/tools/r5e_dead_weight.py
--- R4M/tools7/r5e_dead_weight.py	1969-12-31 16:00:00
+++ R5E/tools/r5e_dead_weight.py	2026-09-24 12:43:53
@@ -0,0 +1,278 @@
+"""R5E (2026-09-24): remove the declarations and elements that every style pass
+re-applies without carrying a live value (work/2026-09-19/R5E.md).
+
+Blink re-applies EVERY declaration of a dirtied element (audit SYNTHESIS §8.1:
+4.45 us/element + 36.5 ns/byte for var() declarations, 0.72 us per short literal
+declaration). The combined7 census (R5A/census.md, R5E.md §1) found four
+populations that are restyled per layer pass or per token but carry no value:
+
+  R5E_LEAN_WALLS=0       keep the two inheritance walls as emitted: `.core-reset`
+                         (16,156 `--p:initial`, 309 KB, restyled every layer pass)
+                         and `.head-isolation` (24,105 `--p:initial`, 463 KB, ~5
+                         restyles per token). ON: each wall keeps only the
+                         registered properties that some ancestor-or-self of the
+                         wall element declares (CSS rule whose rightmost compound
+                         can match it, inline style, or keyframes it animates);
+                         every other property is provably at its initial value on
+                         the wall's parent, so `initial` there is a no-op. Derived
+                         mechanically from the assembled page + sheet at build
+                         time (lean_walls()); identical computed values and
+                         identical dirtying (the wall still pins every property
+                         that can change above it).
+  R5E_LP_INHERIT=0       keep R3R/F5's private `--lp-*` (proj readback numbers,
+                         inherits:false) with 768 `--lp-i:inherit` forwards on
+                         `.loop-input` plus R4T's 4,224 forwards on the nested
+                         `.loop-reader-cK` chunks. ON: `--lp-*` stay registered
+                         inherits:true (as r3r_fold_hop registers them) and the
+                         forwards disappear. Same values at `.loop-input`; the
+                         subtree they now inherit into is exactly the subtree the
+                         decoded `--loop-in-*` (inherits:true) already dirty in the
+                         same pass.
+  R5E_DROP_DEAD_LISTS=0  keep `.fvs-query{--fvs-all-fields:…}` and the 8
+                         `--fvs-retained-S` lists. ON (F5_BANK_LITERAL_LISTS only):
+                         not emitted — the bank rules inline the literal lists and
+                         nothing references these unregistered properties.
+  R5E_KEEP_DIAG=1        keep the three geometry readback probe pairs
+                         (`#core-probe`, `#block-11-probe`, `#reused-probe`: 15–19 KB
+                         inline width calcs over 768 var() each, position:fixed,
+                         plus their `*-epoch` twins) and `#core-epoch-observer`.
+                         Default OFF: removed. `#reused-probe` sits in the proj
+                         stage and is restyled + laid out every layer; the others
+                         per token. The verifier reads computed styles of
+                         `#core-result`, `.head-input-bank`, `.fvs-bank-L` and
+                         `.token-slot-N`, none of which change.
+"""
+
+import os
+import re
+from html.parser import HTMLParser
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+LEAN_WALLS = flag("R5E_LEAN_WALLS")
+LP_INHERIT = flag("R5E_LP_INHERIT")
+DROP_DEAD_LISTS = flag("R5E_DROP_DEAD_LISTS")
+KEEP_DIAG = flag("R5E_KEEP_DIAG", "0")
+
+WALLS = (".core-reset", ".head-isolation")
+
+
+def manifest():
+    return {
+        "r5eLeanWalls": LEAN_WALLS,
+        "r5eLpInherit": LP_INHERIT,
+        "r5eDropDeadLists": DROP_DEAD_LISTS,
+        "r5eKeepDiag": KEEP_DIAG,
+    }
+
+
+# ---------------------------------------------------------------- DOM ancestry
+_VOID = {"meta", "link", "input", "br", "img", "hr", "set", "animate"}
+
+
+class _Dom(HTMLParser):
+    def __init__(self):
+        super().__init__(convert_charrefs=False)
+        self.stack, self.nodes = [], []  # node = (tag, classes, id, style, parent)
+
+    def handle_starttag(self, tag, attrs):
+        a = dict(attrs)
+        node = (tag, frozenset((a.get("class") or "").split()), a.get("id"), a.get("style") or "",
+                self.stack[-1] if self.stack else -1)
+        self.nodes.append(node)
+        if tag not in _VOID:
+            self.stack.append(len(self.nodes) - 1)
+
+    def handle_startendtag(self, tag, attrs):
+        self.handle_starttag(tag, attrs)
+        if tag not in _VOID:
+            self.stack.pop()
+
+    def handle_endtag(self, tag):
+        for i in range(len(self.stack) - 1, -1, -1):
+            if self.nodes[self.stack[i]][0] == tag:
+                del self.stack[i:]
+                break
+
+
+def _ancestors_or_self(nodes, index):
+    out = []
+    while index >= 0:
+        out.append(nodes[index])
+        index = nodes[index][4]
+    return out
+
+
+# ---------------------------------------------------------------- CSS scanning
+def _rules(css):
+    """Yield (prelude, body, parents) for every block, nested blocks included; body = the
+    declarations before any nested '{'; parents = tuple of enclosing preludes (outermost first)."""
+    i, n, start = 0, len(css), 0
+    stack = []
+    while i < n:
+        c = css[i]
+        if c == '"':
+            j = css.find('"', i + 1)
+            while j > 0 and css[j - 1] == "\\":
+                j = css.find('"', j + 1)
+            i = j + 1
+            continue
+        if c == "{":
+            stack.append((css[start:i].strip(), i + 1))
+            i += 1
+            start = i
+            continue
+        if c == "}":
+            pre, bstart = stack.pop()
+            body = css[bstart:i]
+            k = body.find("{")
+            yield pre, (body if k < 0 else body[:k]), tuple(p for p, _ in stack)
+            i += 1
+            start = i
+            continue
+        if c == ";" and not stack:
+            i += 1
+            start = i
+            continue
+        i += 1
+
+
+def _split_top(text, sep):
+    parts, depth, cur = [], 0, []
+    for ch in text:
+        if ch in "([":
+            depth += 1
+        elif ch in ")]":
+            depth -= 1
+        if ch == sep and depth == 0:
+            parts.append("".join(cur))
+            cur = []
+        else:
+            cur.append(ch)
+    parts.append("".join(cur))
+    return parts
+
+
+def _rightmost_compound(selector):
+    depth = 0
+    for k in range(len(selector) - 1, -1, -1):
+        ch = selector[k]
+        if ch in ")]":
+            depth += 1
+        elif ch in "([":
+            depth -= 1
+        elif depth == 0 and ch in " >+~":
+            return selector[k + 1:]
+    return selector
+
+
+_CLASS = re.compile(r"\.([\w-]+)")
+_ID = re.compile(r"#([\w-]+)")
+_TYPE = re.compile(r"^([a-zA-Z][\w-]*|\*)")
+
+
+def _compound_matches(compound, node):
+    """Could `compound` match `node`? Pseudo-classes are ignored (superset = safe)."""
+    # strip functional pseudo-class arguments so their inner selectors do not count as constraints
+    flat, depth, out = compound, 0, []
+    for ch in flat:
+        if ch == "(":
+            depth += 1
+            continue
+        if ch == ")":
+            depth -= 1
+            continue
+        if depth == 0:
+            out.append(ch)
+    flat = "".join(out)
+    tag, classes, ident = node[0], node[1], node[2]
+    m = _TYPE.match(flat)
+    if m and m.group(1) != "*" and m.group(1).lower() != tag:
+        return False
+    for c in _CLASS.findall(flat):
+        if c not in classes:
+            return False
+    for i in _ID.findall(flat):
+        if i != ident:
+            return False
+    return True
+
+
+_DECL_PROP = re.compile(r"(?:^|;)\s*(--[\w-]+)\s*:")
+_ANIM_NAMES = re.compile(r"(?:^|;)\s*animation(?:-name)?\s*:([^;]*)")
+_IDENT = re.compile(r"[A-Za-z_-][\w-]*")
+
+
+def _declared_props(body):
+    return set(_DECL_PROP.findall(body))
+
+
+def _animation_names(body):
+    names = set()
+    for value in _ANIM_NAMES.findall(body):
+        for part in value.split(","):
+            for tok in _IDENT.findall(part):
+                names.add(tok)
+    return names
+
+
+def lean_walls(css, page, walls=WALLS):
+    """Shrink each wall rule to the properties that can be non-initial on the wall element.
+
+    Returns (css, stats). A property is kept when an ancestor-or-self of the wall element
+    (a) declares it in a rule whose rightmost compound can match that element,
+    (b) declares it in its inline style, or
+    (c) animates it (keyframes referenced by an animation on such a rule).
+    """
+    dom = _Dom()
+    dom.feed(page)
+    nodes = dom.nodes
+    keyframes = {}
+    matched_rules = []
+    for pre, body, parents in _rules(css):
+        if parents and parents[-1].startswith("@keyframes"):
+            keyframes.setdefault(parents[-1].split()[1], set()).update(_declared_props(body))
+            continue
+        if pre.startswith("@"):
+            continue
+        matched_rules.append((pre, body))
+    stats = {}
+    for wall in walls:
+        cls = wall.lstrip(".")
+        targets = [i for i, n in enumerate(nodes) if cls in n[1]]
+        if len(targets) != 1:
+            raise ValueError(f"R5E: expected one {wall} element, found {len(targets)}")
+        chain = _ancestors_or_self(nodes, targets[0])
+        live, anims = set(), set()
+        for node in chain:
+            live |= _declared_props(node[3])
+        for pre, body in matched_rules:
+            if pre == wall:
+                continue  # the wall rule itself
+            for selector in _split_top(pre, ","):
+                comp = _rightmost_compound(selector.strip())
+                if any(_compound_matches(comp, node) for node in chain):
+                    live |= _declared_props(body)
+                    anims |= _animation_names(body)
+                    break
+        for name in anims:
+            live |= keyframes.get(name, set())
+        start = css.find(wall + "{")
+        if start < 0 or css.find(wall + "{", start + 1) >= 0:
+            raise ValueError(f"R5E: expected exactly one {wall} rule")
+        end = css.index("}", start)
+        decls = css[start + len(wall) + 1:end].split(";")
+        kept, dropped = [], 0
+        for d in decls:
+            name = d.split(":", 1)[0].strip()
+            if d.strip().endswith(":initial") and name.startswith("--") and name not in live:
+                dropped += 1
+                continue
+            kept.append(d)
+        css = css[:start] + wall + "{" + ";".join(kept) + "}" + css[end + 1:]
+        stats[wall] = {"kept": len([d for d in kept if d.strip().endswith(":initial")]),
+                       "dropped": dropped, "liveOnAncestors": len(live), "ancestors": len(chain) - 1}
+    return css, stats
```
