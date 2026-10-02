"""R8U: flag-off twin vs live bundle: index.html + runtime.css byte-identical; font-witnesses.json / manifest.json identical after
normalising the agent dir (R7X/... -> R8U/... through identical symlinks). usage: check_flagoff.py <twin> <live>"""
import sys, pathlib, re, json
A, B = map(pathlib.Path, sys.argv[1:3]); ok = True
for f in ("index.html", "runtime.css"):
    same = (A / f).read_bytes() == (B / f).read_bytes(); print(f, "BYTE-IDENTICAL" if same else "DIFFERS", (A / f).stat().st_size, (B / f).stat().st_size); ok &= same
norm = lambda t: re.sub(r"/work/2026-09-19/R[0-9A-Z]+/", "/work/2026-09-19/AGENT/", t)
for f in ("font-witnesses.json", "manifest.json"):
    a, b = norm((A / f).read_text()), norm((B / f).read_text())
    if a == b: print(f, "identical (agent dir normalised)")
    else:
        ja, jb = json.loads(a), json.loads(b)
        keys = [k for k in set(ja) | set(jb) if ja.get(k) != jb.get(k)] if isinstance(ja, dict) else "list"
        print(f, "DIFFERS; keys:", keys); ok = False
print("RESULT:", "PASS" if ok else "FAIL")
