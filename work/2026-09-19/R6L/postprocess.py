#!/usr/bin/env python3
"""R6L: apply exactly the R6L_BODY_LINK / R6L_BOOT page transformation to an existing bundle (timing twins;
also the identity oracle for the emitter build).  usage: postprocess.py <src-bundle> <dst-bundle> [--no-body-link] [--no-boot]
Copies index.html + runtime.css (transformed) + manifest.json (+ r6l keys); fonts stay relative (dst must sit in bundles/)."""
import json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
os.environ.setdefault("R6L_BODY_LINK", "0" if "--no-body-link" in sys.argv else "1")
os.environ.setdefault("R6L_BOOT", "0" if "--no-boot" in sys.argv else "1")
import r6l_boot as r6l  # noqa: E402

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
html = (src / "index.html").read_text()
old = r6l.LINK_HTML + "</head><body>"
assert html.count(old) == 1, html.count(old)
html = html.replace(old, r6l.head_html() + "</head><body>" + r6l.body_prefix())
(dst / "index.html").write_text(html)
css = (src / "runtime.css").read_text()
assert not css.endswith(r6l.css_tail())
(dst / "runtime.css").write_text(r6l.finish_css(css))
m = json.loads((src / "manifest.json").read_text()); m.update(r6l.manifest()); m["r6lPostprocessedFrom"] = str(src)
(dst / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
for extra in ("font-witnesses.json",):
    if (src / extra).exists(): shutil.copy(src / extra, dst / extra)
print("wrote", dst, "html", (dst / "index.html").stat().st_size, "css", (dst / "runtime.css").stat().st_size, r6l.manifest())
