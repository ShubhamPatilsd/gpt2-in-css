#!/bin/zsh
# R2H: after R2I restored the repo fonts — go back to the plain repo symlinks (as F4/R2C/R2F/R2D), rebuild combined3, expect the 09-19 build byte-for-byte.
set -e
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2H
[[ -L experiments ]] || { mv experiments experiments.local-overlay && mv experiments.repo-link experiments; }
[[ -L global-projection-assets ]] || { mv global-projection-assets global-projection-assets.local && mv global-projection-assets.f2-link global-projection-assets; }
ls -ld experiments global-projection-assets
./compile-combined3.sh combined3 > compile-combined3-rebuild3.log 2>&1
python3 /Users/shubhampatil/Documents/programming/gpt2-css/tools/launch_browser_gpt2.py --check --directory ../bundles/combined3 | tail -3
for f in runtime.css index.html; do cmp prev-build/$f ../bundles/combined3/$f && echo "$f byte-identical to the 09-19 build"; done
python3 - <<'PY'
import json, re
a = json.load(open("prev-build/font-witnesses.json")); b = json.load(open("../bundles/combined3/font-witnesses.json"))
strip = lambda d: {k: {x: y for x, y in v.items() if x != "mtime"} for k, v in d.items()}
print("witness keys identical:", set(a) == set(b), "values identical modulo mtime:", strip(a) == strip(b))
PY
echo "F2 assets: $(ls ../F2/global-projection-assets | wc -l | tr -d ' ') (expect 144)"
