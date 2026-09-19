#!/bin/sh
# usage: ./with_lock.sh <command...>  -- holds work/2026-09-19/CHROME.lock while running
LOCK=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/CHROME.lock
n=0
while ! mkdir "$LOCK" 2>/dev/null; do
  n=$((n+1)); [ $n -eq 1 ] && echo "[lock] held, polling every 15 s" >&2
  sleep 15
  [ $n -gt 240 ] && { echo "[lock] gave up after 60 min" >&2; exit 3; }
done
echo "F3 $(date -u +%FT%TZ) $*" > "$LOCK/owner"
trap 'rm -rf "$LOCK"' EXIT INT TERM
if pgrep -f "Google Chrome --" >/dev/null; then echo "[lock] WARNING: another Chrome is running:" >&2; pgrep -fl "Google Chrome --" | head -3 >&2; fi
"$@"
