#!/usr/bin/env python3
"""Copy verified scratch fonts into experiments/gpt2-flat-12block-chain/layer01..10 (never layer11).
Restores original mtime_ns for .woff2 from bundle font-witnesses.json (witness cache key); .ttf gets its sibling woff2's mtime.
Refuses to overwrite an existing file whose bytes differ."""
import json, os, shutil, sys
from pathlib import Path
ROOT = Path("/Users/shubhampatil/Documents/programming/gpt2-css")
CHAIN = ROOT / "experiments/gpt2-flat-12block-chain"
SRC = Path(sys.argv[1]).resolve()
mtimes = {}
for b in (ROOT / "work/2026-09-19/bundles").iterdir():
    wj = b / "font-witnesses.json"
    if wj.exists():
        for key, info in json.loads(wj.read_text()).items():
            if "/gpt2-flat-12block-chain/layer" in key:
                mtimes.setdefault(Path(key).name, info["mtime"])
copied = restored_mtime = 0
for layer in range(1, 11):
    dst = CHAIN / f"layer{layer:02d}"
    assert dst.name != "layer11"
    files = sorted((SRC / f"layer{layer:02d}").glob(f"b{layer}-*rowbase*"))
    assert len(files) == 36, (layer, len(files))
    for f in files:
        target = dst / f.name
        if target.exists() and target.read_bytes() != f.read_bytes():
            sys.exit(f"refusing to overwrite differing file {target}")
        shutil.copyfile(f, target); copied += 1
    for f in files:
        target = dst / f.name
        woff2_name = f.with_suffix(".woff2").name
        if woff2_name in mtimes:
            ns = mtimes[woff2_name]; os.utime(target, ns=(ns, ns)); restored_mtime += 1
    print(f"layer{layer:02d}: copied {len(files)} files -> {dst}", flush=True)
print(f"copied={copied} mtime_restored={restored_mtime}")
