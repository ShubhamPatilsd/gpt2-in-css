"""R4W: var() references and substituted bytes per V leaf per restyle, before (combined4-c32c) and after (combined4-c32d),
from the emitted CSS + the prompt-40 trajectory's actual V lists (browser_gpt2_core.reference_sequence, R4W tools; the
emitter's list format: '"Vxxx" <number>' with Blink's 6-significant-digit serialisation of the substituted --fvn numbers).
Restyles of the V-leaf subtree per token: 12 (R4V trace, R4W/trace-parse: the 25,351-element style passes = 24,576 leaves
+ 768 rows + wrappers, 12 per token = one per layer)."""
import json, re, sys, time
import numpy as np
W = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19"
sys.path.insert(0, f"{W}/R4W/tools")
from browser_gpt2_core import reference_sequence
t0 = time.time()
ref = json.load(open(f"{W}/R4P/reference_ids_32_40.json"))
tokens = [ref["promptToken"]] + ref["freeRunningReference"][:31]
r = reference_sequence(tokens, 12, kv_window=None, kv_sinks=0)
print("keys", list(r.keys()), f"{time.time()-t0:.0f}s")
# V lists exactly as the emitter forms them: per layer, position, head: v[h*64:(h+1)*64] / max(1e-6, max|v_h|), 6 sig digits
def fmt(x): return f"{x:.6g}"
sizes = []
qkv_key = "layers"
for layer in range(12):
    qkv = np.asarray(r["layers"][layer]["qkv"])   # (positions, 2304)
    v = qkv[:, 1536:]
    for pos in range(v.shape[0]):
        for h in range(12):
            vh = v[pos, h*64:(h+1)*64]; vn = vh / max(1e-6, np.abs(vh).max())
            sizes.append(sum(len('"V000" ') + len(fmt(x)) + 1 for x in vn) - 1)
sizes = np.array(sizes)
print(f"V list (64 axes) substituted text: mean {sizes.mean():.1f} B, min {sizes.min()}, max {sizes.max()} over {len(sizes)} lists")
def leaf_rule(css, h, s):
    m = re.search(r'\.fvs-v-%d-%d\{([^}]*)\}' % (h, s), css); return m.group(1)
out = []
for name in ("combined4-c32c", "combined4-c32d"):
    css = open(f"{W}/bundles/{name}/runtime.css").read()
    rule = leaf_rule(css, 3, 17)
    nvar = rule.count("var("); fvs = "font-variation-settings" in rule
    lit = len(rule)
    # substituted bytes per filled leaf per restyle: list (if the leaf references it) + the --fw number (~8 B, e.g. 0.123456)
    sub = (sizes.mean() if fvs else 0) + 8
    wrap = re.search(r'\.fvs-value-head-3\{([^}]*)\}', css)
    wrap_var = wrap.group(1).count("var(") if wrap else 0
    out.append((name, rule, nvar, lit, sub, wrap_var))
    print(f"\n[{name}] .fvs-v-3-17{{{rule}}}\n  var() refs per leaf: {nvar}; literal declaration bytes: {lit}; substituted bytes per FILLED leaf per restyle: ~{sub:.0f} B"
          f" (list {sizes.mean():.0f} B x {int(fvs)} + --fw ~8 B); head wrapper var() refs: {wrap_var}")
# per position per token totals (12 leaf-subtree restyles per token, 768 leaves per position)
before = out[0][4]; after = out[1][4]
print(f"\nper filled position per token (768 leaves x 12 restyles): before {before*768*12/1e6:.2f} MB substituted text, after {after*768*12/1e6:.2f} MB;"
      f" wrapper (after): 12 heads x 12 restyles x ({sizes.mean():.0f} B per filled slot) = {12*12*sizes.mean()/1e3:.0f} KB per filled position per token")
print(f"parsed axes per restyle at p filled: before 65*768*p + 1*768*(32-p); after 65*12*p + 1*12*(32-p)  (p=32: {65*768*32:,} vs {65*12*32:,})")
print(f"{time.time()-t0:.0f}s")
