#!/usr/bin/env python3
"""R6L: make a self-contained, shareable copy of a bundle.
  <out>/tools/launch_browser_gpt2.py   (verbatim copy of the repo's strict server + launcher; ROOT = <out>)
  <out>/model/index.html, runtime.css  (url()s rewritten to fonts/<basename>?v=…), model/fonts/*.woff2 (283 files)
  <out>/README.txt                     (run recipe, Chrome ≥ 139, memory warning)
  --br    also writes index.html.br / runtime.css.br (+ .gz) next to the originals for hosts that serve precompressed files
  --dry-run  print the size table only (nothing written).      usage: pack_bundle.py <bundle-dir> <out-dir> [--br] [--dry-run]
Then: `cd <out> && python3 tools/launch_browser_gpt2.py --directory model` (or zip <out> and send it)."""
import re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]  # REPO_ROOT
src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(); dry = "--dry-run" in sys.argv; br = "--br" in sys.argv
css = (src / "runtime.css").read_text(); html = (src / "index.html").read_text()
fonts = {}
def repl(m):
    url = m.group(1); path, _, q = url.partition("?"); p = (src / path).resolve(); assert p.is_file(), p
    name = p.name; assert fonts.get(name, p) == p, f"basename collision {name}"; fonts[name] = p
    return 'url("fonts/' + name + ("?" + q if q else "") + '")'
css2 = re.sub(r'url\("([^"]+)"\)', repl, css)
assert not re.search(r'url\(', html)
font_bytes = sum(p.stat().st_size for p in fonts.values()); big = max(fonts.values(), key=lambda p: p.stat().st_size)
print(f"index.html {len(html.encode()):>12,} B\nruntime.css {len(css2.encode()):>11,} B\nfonts ({len(fonts)}) {font_bytes:>12,} B  (largest {big.name} {big.stat().st_size:,} B)")
print(f"total {len(html.encode()) + len(css2.encode()) + font_bytes:>19,} B uncompressed")
if dry: sys.exit(0)
(out / "tools").mkdir(parents=True, exist_ok=True); (out / "model" / "fonts").mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT / "tools" / "launch_browser_gpt2.py", out / "tools" / "launch_browser_gpt2.py")
(out / "model" / "index.html").write_text(html); (out / "model" / "runtime.css").write_text(css2)
for name, p in fonts.items(): shutil.copy(p, out / "model" / "fonts" / name)
for extra in ("manifest.json", "BUILD.md"):
    if (src / extra).exists(): shutil.copy(src / extra, out / "model" / extra)
(out / "README.txt").write_text("""GPT-2 in pure HTML + CSS (no JavaScript). Requirements: Google Chrome / Chromium 139 or newer (uses CSS @function, if(),
calc-size(), anchor positioning, view timelines, @container style() queries), a machine with 16 GB RAM or more (the tab uses ≈2 GB after
load and up to ≈6 GB while generating 32 tokens; close other big apps), ≈300 MB of disk for this folder.
Run:   python3 tools/launch_browser_gpt2.py --directory model          (Python 3.9+; opens a separate Chrome profile with JavaScript disabled)
       python3 tools/launch_browser_gpt2.py --directory model --no-open   then open the printed URL in Chrome yourself.
Loading: the page shows one line while the 50 MB stylesheet is parsed (a few seconds), then "Loading model fonts…" while the 283 weight
fonts (239 MB) load, then "Ready". Choose a prompt, tick Run. Each token takes ≈15–45 s; 32 tokens ≈ 15 min.
""")
if br:
    for f in ("index.html", "runtime.css"):
        subprocess.run(["brotli", "-q", "11", "-f", "-k", str(out / "model" / f)], check=True)
        subprocess.run(["gzip", "-9", "-f", "-k", str(out / "model" / f)], check=True)
print("wrote", out)
