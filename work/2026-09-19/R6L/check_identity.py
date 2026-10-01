#!/usr/bin/env python3
"""R6L identity oracle. usage: check_identity.py <built-bundle> <reference-bundle> [--expect-r6l]
Without --expect-r6l: index.html and runtime.css must be byte-identical (flag-off build vs combined8-c32).
With --expect-r6l: built == postprocess.py(reference) byte-for-byte (the emitter's R6L output equals the mechanical
transformation of the reference: only the head/link bytes of index.html and the 2-rule css tail differ from the reference)."""
import sys, json, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
built, ref = Path(sys.argv[1]), Path(sys.argv[2]); expect = "--expect-r6l" in sys.argv
import r6l_boot as r6l
ok = True
bh, rh = (built / "index.html").read_text(), (ref / "index.html").read_text()
bc, rc = (built / "runtime.css").read_text(), (ref / "runtime.css").read_text()
if "--normalize-urls" in sys.argv:  # a twin one directory deeper has one more ../ per url() (R5X BUILD.md artefact)
    import re as _re
    bc, rc = (_re.sub(r'url\("(\.\./)+', 'url("', x) for x in (bc, rc))
if expect:
    old = r6l.LINK_HTML + "</head><body>"
    th = rh.replace(old, r6l.head_html() + "</head><body>" + r6l.body_prefix(), 1)
    tc = r6l.finish_css(rc)
    print("index.html == transform(ref):", bh == th, len(bh), len(th)); ok &= bh == th
    print("runtime.css == transform(ref):", bc == tc, len(bc), len(tc)); ok &= bc == tc
    print("css minus tail == ref css:", bc[: len(rc)] == rc and bc[len(rc):] == r6l.css_tail())
else:
    print("index.html identical:", bh == rh, len(bh), len(rh)); ok &= bh == rh
    print("runtime.css identical:", bc == rc, len(bc), len(rc)); ok &= bc == rc
bm, rm = json.loads((built / "manifest.json").read_text()), json.loads((ref / "manifest.json").read_text())
diff = {k: (rm.get(k), bm.get(k)) for k in set(bm) | set(rm) if bm.get(k) != rm.get(k)}
print("manifest diffs:", diff)
bw, rw = json.loads((built / "font-witnesses.json").read_text()), json.loads((ref / "font-witnesses.json").read_text())
import re
def norm(k): return re.sub(r"work/2026-09-19/R\w+/", "work/2026-09-19/AGENT/", k) if isinstance(k, str) else k
def strip(w):
    if isinstance(w, list): return [strip(x) for x in w]
    if isinstance(w, dict): return {norm(k): strip(v) for k, v in w.items() if k not in ("mtime", "modified", "path")}
    return norm(w)
print("witnesses identical (ignoring mtime/path):", strip(bw) == strip(rw)); ok &= strip(bw) == strip(rw)
print("RESULT:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
