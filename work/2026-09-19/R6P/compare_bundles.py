"""R6P: compare two bundle dirs (= R4M/compare_bundles.py + agent-dir normalisation): index.html bytes, runtime.css after normalising the
relative url("../…") depth AND the agent dir of the R5H dot fonts (R5H/assets-r5h == R6P/assets-r5h), manifest key diff, font-witnesses
(keys modulo tools/agent dir). usage: compare_bundles.py <dirA> <dirB>"""
import json, re, sys, pathlib
A, B = map(pathlib.Path, sys.argv[1:3])
def norm_css(p):
    s = (p / "runtime.css").read_text()
    s2 = re.sub(r'url\("(?:\.\./)+', 'url("../', s)
    s2 = re.sub(r'url\("\.\./(?:(?:R5[HX]|R6P)/)?assets-r5h/', 'url("../AGENT/assets-r5h/', s2)  # scratch twins sit inside R6P: no agent dir in the relative URL
    return s2, len(s)
def norm_wit(p):
    w = json.loads((p / "font-witnesses.json").read_text())
    if isinstance(w, dict):
        return {re.sub(r"^.*?/2026-09-19/(?:R5[HX]|R6P)/assets-r5h/", "AGENT/assets-r5h/", re.sub(r"^.*?/(experiments|assets|global-projection-assets|data)/", r"\1/", k)): v for k, v in w.items()}
    return w
ha, hb = (A / "index.html").read_bytes(), (B / "index.html").read_bytes()
print(f"index.html: {'IDENTICAL' if ha == hb else 'DIFFER'} ({len(ha)} vs {len(hb)} B)")
if ha != hb:
    i = next((i for i, (x, y) in enumerate(zip(ha, hb)) if x != y), min(len(ha), len(hb)))
    print(f"  first difference at {i}: A[...]={ha[max(0,i-80):i+120]!r}\n                        B[...]={hb[max(0,i-80):i+120]!r}")
ca, la = norm_css(A); cb, lb = norm_css(B)
print(f"runtime.css (url-normalised): {'IDENTICAL' if ca == cb else 'DIFFER'} (raw {la} vs {lb} chars)")
if ca != cb:
    i = next((i for i, (x, y) in enumerate(zip(ca, cb)) if x != y), min(len(ca), len(cb)))
    print(f"  first difference at {i}: A[...]={ca[max(0,i-80):i+120]!r}\n                        B[...]={cb[max(0,i-80):i+120]!r}")
ma, mb = json.loads((A / "manifest.json").read_text()), json.loads((B / "manifest.json").read_text())
def flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict): out.update(flat(v, pre + k + "."))
        else: out[pre + k] = json.dumps(v, sort_keys=True)
    return out
fa, fb = flat(ma), flat(mb)
diff = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
print(f"manifest: {len(diff)} differing keys: " + "; ".join(f"{k}: {fa.get(k)} -> {fb.get(k)}" for k in diff)[:3000])
wa, wb = norm_wit(A), norm_wit(B)
if isinstance(wa, dict):
    same = sum(1 for k in wa if k in wb and wa[k] == wb[k])
    nomt = lambda v: {kk: vv for kk, vv in v.items() if kk != "mtime"} if isinstance(v, dict) else v
    same_nomt = sum(1 for k in wa if k in wb and nomt(wa[k]) == nomt(wb[k]))
    print(f"font-witnesses: {same}/{len(wa)} identical (keys modulo tools/agent dir; {same_nomt}/{len(wa)} ignoring the file mtime field); only in A {len(set(wa)-set(wb))}, only in B {len(set(wb)-set(wa))}")
    for k in sorted(set(wa) - set(wb))[:3]: print("   only in A:", k)
    for k in sorted(set(wb) - set(wa))[:3]: print("   only in B:", k)
else:
    print(f"font-witnesses: {'IDENTICAL' if wa == wb else 'DIFFER'} (list form, {len(wa)} vs {len(wb)})")
