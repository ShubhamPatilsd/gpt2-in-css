#!/usr/bin/env bash
# Stage the GPT-2-in-CSS bundle for the Cloudflare Worker deploy.
#   ./public/  <- the bundle minus the two files over 25 MiB, plus _headers (static assets)
#   prints     <- the two large files, to upload to the R2 bucket gpt2-css-large
# Usage: ./stage.sh [BUNDLE_DIR]   (default: the R8D upload folder)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BUNDLE="${1:-${BUNDLE:-$HERE/../../work/2026-09-19/R8D/out/model}}"
BUNDLE="$(cd "$BUNDLE" && pwd)"
PUB="$HERE/public"
LARGE=(runtime.css fonts/embedding-lookup.woff2)
LIMIT=$((25 * 1024 * 1024))

[ -f "$BUNDLE/index.html" ] && [ -f "$BUNDLE/runtime.css" ] || { echo "ERROR: $BUNDLE is not the model bundle" >&2; exit 1; }

rm -rf "$PUB"; mkdir -p "$PUB"
rsync -a --exclude '/runtime.css' --exclude '/fonts/embedding-lookup.woff2' \
  --exclude '.DS_Store' --exclude '*.br' --exclude '*.gz' "$BUNDLE/" "$PUB/"
cp "$HERE/_headers" "$PUB/_headers"

fail=0
echo "== checks"
n=$(find "$PUB" -type f ! -name _headers | wc -l | tr -d ' ')
echo "files in public/: $n (expected 286 = 288 minus 2 large)"
[ "$n" -le 20000 ] || { echo "FAIL: more than 20000 files"; fail=1; }
big=$(find "$PUB" -type f -size +$((LIMIT / 1024))k)
if [ -n "$big" ]; then echo "FAIL: files over 25 MiB in public/:"; echo "$big"; fail=1; else echo "ok: no file in public/ over 25 MiB"; fi
users=$(grep -rl --binary-files=text '/Users/' "$PUB" || true)
if [ -n "$users" ]; then echo "FAIL: '/Users/' found in:"; echo "$users"; fail=1; else echo "ok: no '/Users/' strings in public/"; fi
# Every url() in runtime.css must resolve to a staged file or to one of the large files.
missing=0
while read -r u; do
  p="${u%%\?*}"
  [ -f "$PUB/$p" ] || [ "$p" = "fonts/embedding-lookup.woff2" ] || { echo "FAIL: runtime.css refers to missing $p"; missing=1; }
done < <(grep -o 'url("[^"]*")' "$BUNDLE/runtime.css" | sed 's/^url("//; s/")$//' | grep -v '^data:' | sort -u)
[ $missing -eq 0 ] && echo "ok: every url() in runtime.css resolves" || fail=1
# Fonts with no ?v= and no hash in the name must get a short cache in _headers (not immutable).
while read -r p; do
  case "$p" in *-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) continue;; esac
  [ "$p" = "fonts/embedding-lookup.woff2" ] && continue
  grep -qx "/$p" "$HERE/_headers" || { echo "WARN: /$p is unversioned but gets 'immutable' from /fonts/*; add a rule to _headers"; }
done < <(grep -o 'url("fonts/[^"?]*")' "$BUNDLE/runtime.css" | sed 's/^url("//; s/")$//' | sort -u)
[ "$(grep -c '^/' "$HERE/_headers")" -le 100 ] || { echo "FAIL: _headers has more than 100 rules"; fail=1; }

echo "== upload these to R2 bucket gpt2-css-large (key = file name):"
for f in "${LARGE[@]}"; do
  sz=$(stat -f %z "$BUNDLE/$f" 2>/dev/null || stat -c %s "$BUNDLE/$f")
  printf '  %-12s %10s B  sha256 %s\n    %s\n' "$(basename "$f")" "$sz" "$(shasum -a 256 "$BUNDLE/$f" | cut -c1-16)" "$BUNDLE/$f"
done
echo "== public/: $(du -sh "$PUB" | cut -f1)"
[ $fail -eq 0 ] && echo "STAGE OK" || { echo "STAGE FAILED"; exit 1; }
