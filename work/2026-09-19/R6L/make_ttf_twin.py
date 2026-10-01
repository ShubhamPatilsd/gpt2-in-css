#!/usr/bin/env python3
"""R6L arm (a): serve the 283 faces uncompressed. Decompresses every woff2 referenced by <src>/runtime.css into
R6L/ttf/<same name>.ttf (fontTools; untouched tables are written back byte-for-byte) and writes <dst> whose url()s
point at them. TIMING ARM ONLY (≈914 MB on disk; delete R6L/ttf after the measurement). usage: make_ttf_twin.py <src> <dst>"""
import re, sys, shutil, json, time
from pathlib import Path
from fontTools.ttLib import TTFont
W = Path(__file__).resolve().parents[1]; src, dst = Path(sys.argv[1]), Path(sys.argv[2]); ttf_dir = W / "R6L" / "ttf"; ttf_dir.mkdir(parents=True, exist_ok=True)
css = (src / "runtime.css").read_text(); dst.mkdir(exist_ok=True); t0 = time.time(); done = {}
def repl(m):
    url = m.group(1); path = url.split("?")[0]
    absp = (src / path).resolve()
    if absp not in done:
        out = ttf_dir / (absp.stem + ".ttf")
        if not out.exists():
            f = TTFont(str(absp), lazy=True); f.flavor = None; f.save(str(out)); f.close()
        done[absp] = out
    rel = Path("../../R6L/ttf") / done[absp].name
    return 'url("' + rel.as_posix() + '")'
css2 = re.sub(r'url\("([^"]+\.woff2[^"]*)"\)', repl, css)
(dst / "runtime.css").write_text(css2); shutil.copy(src / "index.html", dst / "index.html")
m = json.loads((src / "manifest.json").read_text()); m["r6lTtfTwinOf"] = str(src); (dst / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
tot = sum(p.stat().st_size for p in done.values())
print(f"{len(done)} faces → ttf, {tot/1e6:.1f} MB on disk, {time.time()-t0:.0f} s; wrote {dst}")
