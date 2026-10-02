#!/bin/sh
# R7S lock helper: mkdir CHROME.lock; owner "R7S <what> <pid> <time>"; touch -c every 30 s; poll 5 s; rmdir only ours.
LOCK=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/CHROME.lock
WHAT=$1; shift
n=0
while ! mkdir "$LOCK" 2>/dev/null; do
  n=$((n+1)); [ $n -eq 1 ] && echo "[lock] held by: $(cat "$LOCK/owner" 2>/dev/null); polling every 5 s" >&2
  sleep 5
  [ $n -gt 2160 ] && { echo "[lock] gave up after 3 h" >&2; exit 3; }
done
echo "R7S $WHAT $$ $(date -u +%FT%TZ)" > "$LOCK/owner"
( while sleep 30; do touch -c "$LOCK" "$LOCK/owner" 2>/dev/null || exit 0; done ) & TOUCHER=$!
release() { kill $TOUCHER 2>/dev/null; if grep -q '^R7S ' "$LOCK/owner" 2>/dev/null; then rm -f "$LOCK/owner"; rmdir "$LOCK" 2>/dev/null; fi; }
trap 'release' EXIT INT TERM
# gate: AC and disk >= 4 GB and swap used < 4000 MB, and no foreign headless Chrome
pmset -g batt | grep -q "AC Power" || { echo "[gate] not on AC" >&2; exit 5; }
free=$(df -g /Users | tail -1 | awk '{print $4}'); [ "$free" -ge 4 ] || { echo "[gate] disk $free GB < 4" >&2; exit 5; }
swap=$(sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1); [ "$swap" -lt 4000 ] || { echo "[gate] swap used ${swap} MB" >&2; exit 5; }
if pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null; then echo "[lock] REFUSING: another headless Chrome is running" >&2; exit 4; fi
echo "[gate] AC ok, disk ${free} GB, swap ${swap} MB" >&2
"$@"
