# bundles/R5M — combined7 + R5M memory cut `R5M_HEAD_LITERAL` (capacity 8, `runs` layout)

Built by R5M on 2026-09-24 12:5x from `work/2026-09-19/R5M/tools` = `R4M/tools7` (combined7's tools) + `r5m_flags.py` + a 3-line hook in
`browser_gpt2_runtime.py`. Same symlinks/fonts as combined7 (283 faces, all under `F4/assets`, `F2/global-projection-assets`, `experiments/`).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
R5M_HEAD_LITERAL=1 R5M/compile.sh tools bundles/R5M 8
# = combined7's exports (bundles/combined7/BUILD.md: F4_*, R2C_*, R2F_*, R2D_*, R2G_*, R3R_*, R3H_*, R4S_*, R4D_*, R4T_CONSUMER_CHUNK=64) plus R5M_HEAD_LITERAL, then
uv run --with numpy --with fonttools --with pillow --with brotli python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R5M
```

## Flags

| flag | default | effect |
|---|---|---|
| `R5M_HEAD_LITERAL` | 1 (`0` = combined7) | the 50,257 coarse head rows carry `style="width:calc-size(max-content,round(nearest,(size - <base>px)*120.777609693 + 211968px,4px))"` instead of `style="--base:<base>;--tie:<tie>"`. Applied as a string transform of the prebuilt `experiments/browser-gpt2/head-two-pass/head-body.html` in `browser_gpt2_runtime.py` (after R3H), FACTOR/OFFSET read from the two-pass `.head-row` width rule (asserted unique and later in the cascade than the tie-bearing base rule). Exact: `var(--base)*1px` with `--base:<n>` is the length `<n>px`; `--tie` is dead in the winning rule. Rows declare no custom properties, so a head restyle allocates no per-row StyleInheritedVariables delta / var() substitution / calc parse. Manifest key `r5mHeadLiteral`. Cost: index.html 6.52 → 9.91 MB (longer inline declarations, parsed once). |

## Offline verification (`R5M/offline-checks.txt`, `R5M/offline_check_r5m.py`)

- `R5M_HEAD_LITERAL=0` twin reproduces `bundles/combined7` byte-for-byte (index.html identical; runtime.css identical after url-depth normalisation; manifest +`r5mHeadLiteral:false`; witnesses 283/283).
- `bundles/R5M` vs combined7: runtime.css IDENTICAL; font-witnesses 283/283 identical (no font touched — protected tables trivially byte-identical); manifest differs only in `r5mHeadLiteral`;
  index.html identical once the head-row `style` attributes are removed; all 50,257 row literals equal the reference row's `--base` with the rule's factor/offset; no `--base`/`--tie` left on rows; cascade order verified.
- `tools/launch_browser_gpt2.py --check --directory bundles/R5M`: 285 static files, `runtimeJavaScript: false`.
- NumPy reference ids with `R5M/tools` (`R5M/reference_ids.log`, model path untouched by construction — `diff -rq R4M/tools7 R5M/tools` = runtime.py + r5m_flags.py): `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected, 8/8.

## Chrome correctness run

See `R5M.md` §5 / `R5M/run-R5M-run1/` (ONE passive 8-token run with `R5M/correctness_run.mjs` = R4M's harness + renderer RSS at 1 Hz; gated on AC, disk ≥ 3 GB, swap < 3 GB per the coordinator's 12:5x rule). READY is created only on 8/8 ids + verify rc 0.

## `diff -ruN -x __pycache__ R4M/tools7 R5M/tools`

```diff
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_runtime.py R5M/tools/browser_gpt2_runtime.py
--- R4M/tools7/browser_gpt2_runtime.py	2026-09-21 01:39:46
+++ R5M/tools/browser_gpt2_runtime.py	2026-09-24 12:57:26
@@ -23,6 +23,7 @@
 import r2c_hoist as r2c
 import r2g_has_scope as r2g
 import r3h_blockflow_max as r3h
+import r5m_flags as r5m
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -271,6 +272,9 @@
         # zero-height rows; a block's max-content width is the max child width,
         # i.e. the same quantity the single max-content grid track computed.
         head_css = r3h.blockflow_max(head_css)
+    if r5m.HEAD_LITERAL:
+        # R5M: coarse rows carry the two-pass width as an inline literal (no --base/--tie custom properties per row).
+        head = r5m.head_literal(head, head_css)
     front, output, control_css, timeline_names = feedback(capacity)
     output_receiver = ""
     if detached_output:
@@ -600,6 +604,7 @@
         detachedOutput=detached_output,
         **r2d.manifest(),
         r3hBlockflowMax=r3h.BLOCKFLOW_MAX,
+        r5mHeadLiteral=r5m.HEAD_LITERAL,
         headEpochTransport="separate geometry" if capacity > 8 else "packed four bits",
         fontBackend=font_backend,
         teacherForcedInputs=teacher_forced_tokens[:capacity]
diff -ruN -x __pycache__ R4M/tools7/r5m_flags.py R5M/tools/r5m_flags.py
--- R4M/tools7/r5m_flags.py	1969-12-31 16:00:00
+++ R5M/tools/r5m_flags.py	2026-09-24 12:57:26
@@ -0,0 +1,51 @@
+"""R5M memory cuts (round 5). Flags default ON; `0` reproduces combined7 byte-for-byte (R4M/tools7 recipe).
+
+R5M_HEAD_LITERAL: each of the 50,257 coarse head rows (prebuilt `experiments/browser-gpt2/head-two-pass/head-body.html`, read by
+  browser_gpt2_runtime.py) carries its width as an inline literal expression
+      width:calc-size(max-content,round(nearest,(size - <base>px)*FACTOR + OFFSET,4px))
+  instead of the two inline custom properties `--base`/`--tie` that the `.head-row` rules substitute. Exactness: the cascade winner
+  for `.head-row{width}` in combined7 is the two-pass rule `(size - var(--base)*1px)*FACTOR + OFFSET` (later than the tie-bearing base
+  rule, same specificity); `var(--base)*1px` with `--base:<n>` is the length `<n>px` bit-for-bit, and `--tie` is dead in that rule.
+  FACTOR/OFFSET are read from the two-pass rule itself (assert exactly one). Rows declare no custom properties afterwards, so a head
+  restyle no longer allocates a StyleInheritedVariables delta, a var() substitution and a calc parse per row (R5M/fx head50k-* fixtures).
+"""
+import os
+import re
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+HEAD_LITERAL = flag("R5M_HEAD_LITERAL")
+
+TWO_PASS_RULE = re.compile(
+    r"\.head-row\{width:calc-size\(max-content,round\(nearest,\(size - var\(--base\)\*1px\)\*([\d.]+) \+ ([-\d.]+px),4px\)\)\}"
+)
+ROW_STYLE = re.compile(r'(<i class="head-row" data-token="\d+" style=")--base:([-\d.]+);--tie:\d+(")')
+TIE_RULE_PREFIX = ".head-row{grid-area:1/1"
+
+
+def head_literal(head_html, head_css):
+    """Rewrite the coarse rows' inline styles to the literal two-pass width (verified shape)."""
+    rules = TWO_PASS_RULE.findall(head_css)
+    if len(rules) != 1:
+        raise ValueError(f"R5M: expected 1 two-pass .head-row width rule, found {len(rules)}")
+    factor, offset = rules[0]
+    two_pass_at = TWO_PASS_RULE.search(head_css).start()
+    tie_at = head_css.find(TIE_RULE_PREFIX)
+    if not (0 <= tie_at < two_pass_at):
+        raise ValueError("R5M: the two-pass rule must follow the tie-bearing base rule (cascade order)")
+    n = 0
+
+    def rep(m):
+        nonlocal n
+        n += 1
+        return f"{m.group(1)}width:calc-size(max-content,round(nearest,(size - {m.group(2)}px)*{factor} + {offset},4px)){m.group(3)}"
+
+    out = ROW_STYLE.sub(rep, head_html)
+    if n != head_html.count('class="head-row"'):
+        raise ValueError(f"R5M: rewrote {n} rows of {head_html.count('class=\"head-row\"')}")
+    if "--base" in out or "--tie" in out:
+        raise ValueError("R5M: a head row still declares --base/--tie")
+    return out
```

### 5.1 Results (appended by `R5M/finish_after_run.sh`)

fx3 fixtures (`R5M/fx-results/*.json`; RSS MB vs blank tab; gens = successive `--head-fvs` changes on the real 50 k-row head):

| fixture | load ms | Δ loaded | Δ per gen | after GC | after pressure | layoutObjects |
|---|---:|---:|---|---:|---:|---:|
| dom-50k-inline | 1396 | +320 |  | 242 | 242 | 100004 |
| dom-50k-inline-props | 1592 | +372 |  | 524 | 524 | 100004 |
| head50k-vars-gen | not run |
| head50k-literal-gen | not run |
| head50k-nowall-gen | not run |

Correctness run `R5M/run_correctness.sh R5M run1` (- 2026-09-24 14:31:31 [R5M correctness/R5M/run1] START correctness run url=http://127.0.0.1:46450/work/2026-09-19/bundles/R5M/index.html waited=546s power=Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 37%; charging; 5:11 remaining present: true load={ 4.42 4.38 4.33 }):
- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.01605519804514142, 'maximum': 0.11651862085027176}, 'text': "Hello, I'm sorry, but I'm".
- Per-token capture times (5 s poll, indicative): 21.8, 34.6, 46.0, 57.5, 74.7, 92.0, 108.9, 127.7 s → per token 21.8, 12.9, 11.4, 11.5, 17.1, 17.3, 16.9, 18.8 s (combined7's R4M correctness run: 22.6, 11.0, 18.2, 16.9, 19.3, 20.4, 20.3, 18.1 = 146.8 s).
- Renderer RSS (MB): pre-run idle 1735, at token captures 1:3399, 2:4356, 3:4237, 4:4129, 5:3684, 6:4318, 7:3683, 8:3903, **peak 4414** (combined7 before: idle 1,846–2,033, token 1 3.5–3.9 GB, peak 5.7–6.0 GB in B5's clean-state runs; 4.3 GB in R5A's swap-pressured run — compare within one memory state only, B6 pairs).
- READY: created.
