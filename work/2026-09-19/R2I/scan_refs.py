#!/usr/bin/env python3
"""Resolve every url(...) / href / src reference in each bundle's runtime.css + index.html; report missing files and digest mismatches."""
import hashlib, re, sys
from pathlib import Path
ROOT = Path("/Users/shubhampatil/Documents/programming/gpt2-css")
BUNDLES = ROOT / "work/2026-09-19/bundles"
url_re = re.compile(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)')
attr_re = re.compile(r'(?:href|src)=["\']([^"\']+)["\']')
summary = {}
for bundle in sorted(p for p in BUNDLES.iterdir() if p.is_dir()):
    missing, mismatch, ok = [], [], 0
    seen = set()
    for fname in ("runtime.css", "index.html"):
        f = bundle / fname
        if not f.exists():
            missing.append(f"(bundle file absent) {fname}")
            continue
        text = f.read_text(errors="replace")
        refs = url_re.findall(text) + attr_re.findall(text)
        for ref in refs:
            if ref.startswith(("data:", "http:", "https:", "#", "about:")):
                continue
            path_part, _, query = ref.partition("?")
            path_part = path_part.split("#")[0]
            if not path_part:
                continue
            key = (fname, path_part, query)
            if key in seen:
                continue
            seen.add(key)
            target = (bundle / path_part).resolve()
            if not target.exists():
                missing.append(f"{fname}: {ref} -> {target}")
                continue
            ok += 1
            m = re.match(r"v=([0-9a-f]{12})$", query)
            if m and target.is_file():
                digest = hashlib.sha256(target.read_bytes()).hexdigest()[:12]
                if digest != m.group(1):
                    mismatch.append(f"{fname}: {ref} actual={digest}")
    summary[bundle.name] = (ok, missing, mismatch)
    print(f"== {bundle.name}: resolved_ok={ok} missing={len(missing)} digest_mismatch={len(mismatch)}")
    for m in missing[:400]:
        print("   MISSING", m)
    for m in mismatch[:400]:
        print("   DIGEST ", m)
