#!/bin/sh
# usage: ./with_lock.sh <command...>  -- holds work/2026-09-19/CHROME.lock (owner R4X) while running; touches every 30 s; rmdir only if ours.
LOCK=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/CHROME.lock
n=0
while ! mkdir "$LOCK" 2>/dev/null; do
  n=$((n+1)); [ $n -eq 1 ] && { echo "[lock] held by: $(cat "$LOCK/owner" 2>/dev/null); polling every 15 s" >&2; }
  sleep 15
  [ $n -gt 480 ] && { echo "[lock] gave up after 120 min" >&2; exit 3; }
done
echo "R4X $(date -u +%FT%TZ) $*" > "$LOCK/owner"
( while sleep 30; do touch "$LOCK" "$LOCK/owner" 2>/dev/null || exit 0; done ) & TOUCHER=$!
release() { kill $TOUCHER 2>/dev/null; if grep -q '^R4X ' "$LOCK/owner" 2>/dev/null; then rm -f "$LOCK/owner"; rmdir "$LOCK" 2>/dev/null; fi; }
trap 'release' EXIT INT TERM
if pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null; then echo "[lock] REFUSING: another headless Chrome is running:" >&2; pgrep -fl '^/Applications/.*Google Chrome .*--headless' | head -3 >&2; exit 4; fi
"$@"
