#!/usr/bin/env python3
"""Verify regenerated rowbase fonts in SRC_ROOT/layerNN against oracles.
Checks per layer 1..10: 36 files present; name set == layer11 set modulo prefix; sha256(woff2)[:12] == ?v= in layerNN/layer.css;
witness codepoint/advance/upem == every bundle's font-witnesses.json entry for that path.
Usage: python verify_layers.py SRC_ROOT   (SRC_ROOT = scratch out dir or experiments/gpt2-flat-12block-chain)
"""
import hashlib, json, re, sys
from pathlib import Path
from fontTools.ttLib import TTFont
ROOT = Path("/Users/shubhampatil/Documents/programming/gpt2-css")
CHAIN = ROOT / "experiments/gpt2-flat-12block-chain"
BUNDLES = ROOT / "work/2026-09-19/bundles"
src_root = Path(sys.argv[1]).resolve()
expected_names = sorted(p.name.replace("b11-", "bNN-", 1) for p in (CHAIN / "layer11").glob("b11-*rowbase*"))
assert len(expected_names) == 36, len(expected_names)
witness_sets = {b.name: json.loads((b / "font-witnesses.json").read_text()) for b in sorted(BUNDLES.iterdir()) if (b / "font-witnesses.json").exists()}
def witness(path):
    with TTFont(path, lazy=True) as font:
        cmap = font.getBestCmap()
        cp = next(c for c in sorted(cmap) if font["hmtx"][cmap[c]][0] > 1)
        return {"codepoint": cp, "advance": font["hmtx"][cmap[cp]][0], "upem": font["head"].unitsPerEm}
failures = 0
for layer in range(1, 11):
    d = src_root / f"layer{layer:02d}"
    names = sorted(p.name for p in d.glob(f"b{layer}-*rowbase*"))
    generic = sorted(n.replace(f"b{layer}-", "bNN-", 1) for n in names)
    name_ok = generic == expected_names
    css = (CHAIN / f"layer{layer:02d}" / "layer.css").read_text()
    oracle = dict(re.findall(rf'(b{layer}-[a-z-]+rowbase-s\d+\.woff2)\?v=([0-9a-f]+)', css))
    digest_ok = digest_bad = digest_mangled = 0
    for name, tag in sorted(oracle.items()):
        p = d / name
        real = hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else None
        if real == tag:
            digest_ok += 1
        elif real is not None and real.replace("b1", f"b{layer}") == tag:
            # layer.css was produced by rewrite_layer_assets: css.replace("b1", f"b{layer}") also mangles hex digests containing "b1"
            digest_ok += 1; digest_mangled += 1; print(f"  note layer{layer:02d} {name}: css ?v={tag} is the b1->b{layer}-mangled form of real digest {real}")
        else:
            digest_bad += 1; print(f"  DIGEST MISMATCH/MISSING layer{layer:02d} {name} want {tag}")
    w_ok = w_bad = 0
    for bname, ws in witness_sets.items():
        for key, info in ws.items():
            if f"/layer{layer:02d}/" not in key: continue
            p = d / Path(key).name
            if not p.exists(): w_bad += 1; print(f"  WITNESS file missing {bname} {key}"); continue
            got = witness(p)
            if all(got[k] == info[k] for k in ("codepoint", "advance", "upem")): w_ok += 1
            else: w_bad += 1; print(f"  WITNESS MISMATCH {bname} {key} got {got} want {info}")
    ref = json.loads((CHAIN / f"layer{layer:02d}" / "view-timeline-two-block-full-exact-reference.json").read_text())
    size_sum = sum(p.stat().st_size for p in d.glob(f"b{layer}-*rowbase*.woff2"))
    size_ok = size_sum == ref["font_bytes"]
    if not size_ok: print(f"  SIZE SUM MISMATCH layer{layer:02d} got {size_sum} want {ref['font_bytes']}")
    status = "OK" if (size_ok and name_ok and len(names) == 36 and digest_bad == 0 and w_bad == 0 and len(oracle) == 18) else "FAIL"
    if status == "FAIL": failures += 1
    print(f"layer{layer:02d}: files={len(names)} nameset_ok={name_ok} css_oracle={len(oracle)} digest_ok={digest_ok} (of which b1-mangled={digest_mangled}) digest_bad={digest_bad} witness_ok={w_ok} witness_bad={w_bad} woff2_size_sum_ok={size_ok} -> {status}")
print("RESULT:", "ALL OK" if failures == 0 else f"{failures} layer(s) FAILED")
sys.exit(1 if failures else 0)
