#!/bin/zsh
# R4T 2-layer smoke under the Chromium mutex (R3M lock protocol as run_r4t.sh): serve bundles/<b>, run run_bundle.mjs (light trace), frames.py.
# usage: run_smoke.sh <tag> <bundle> [<bundle> ...]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
tag=$1; shift
logline() { echo "- $(date '+%F %T') [R5E smoke/$tag] $*" >> $W/R5E.log.md; echo "$*"; }
OWNER="R5E smoke $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R5E smoke $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine (R5E))";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine"; fi; }
waited=0
# Coordinator gate (round 5, 12:5x): before ANY Chrome launch: free disk >= 3.0 GB AND `sysctl vm.swapusage` used < 3000 MB AND AC power; poll 60 s.
MIN_GB=${MIN_GB:-3}; MAX_SWAP_MB=${MAX_SWAP_MB:-3000}
while true; do
  free_kb=$(df -k /System/Volumes/Data | awk 'NR==2{print $4}'); on_ac=$(pmset -g batt | head -1 | grep -c "AC Power")
  swap_mb=$(sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1)
  (( free_kb >= MIN_GB * 1048576 && on_ac == 1 && swap_mb < MAX_SWAP_MB )) && break
  (( waited % 600 == 0 )) && logline "waiting for machine gate: free $((free_kb/1048576)) GB (need $MIN_GB), swap used ${swap_mb} MB (need < $MAX_SWAP_MB), AC=$on_ac"
  sleep 60; waited=$((waited+60))
done
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'file/no owner')), polling 5 s"; sleep 5; waited=$((waited+5)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null || break
  logline "foreign headless Chrome still running after 90 s — releasing, back to polling"; release; sleep 5
done
trap 'release; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null' EXIT INT TERM
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
logline "START (waited ${waited}s) load=$(sysctl -n vm.loadavg) bundles=$*"
rc=0
for bundle in "$@"; do
  out=$W/R5E/runs/$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle; mkdir -p $out; cp $dir/manifest.json $out/
  port=$((45000 + RANDOM % 2000))
  python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
  url="http://127.0.0.1:$port/$rel/index.html"
  for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
  R2F_URL=$url R2F_OUT=$out R2F_TRACE=${TRACE:-1} R2F_POLL_MS=2000 R2F_CAP_MS=${CAP_MS:-300000} caffeinate -dims $NODE $W/R5E/run_bundle.mjs > $out/harness.log 2>&1 &
  npid=$!; t0=$(date +%s)
  while kill -0 $npid 2>/dev/null; do sleep 5; (( $(date +%s) - t0 >= ${WALL_CAP_S:-420} )) && { logline "WATCHDOG wall cap — killing $npid"; pkill -P $npid; kill $npid; sleep 2; kill -9 $npid 2>/dev/null; break; }; done
  wait $npid 2>/dev/null; r=$?; (( r != 0 )) && rc=$r
  kill $spid 2>/dev/null; spid=
  logline "$bundle rc=$r $(grep '"final"' $out/harness.log | cut -c1-300)"
  [[ -f $out/trace.json.gz ]] && python3 $W/R5E/frames.py $out > $out/frames.log 2>&1
done
pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null && { logline "Chrome still alive, killing"; pkill -f '^/Applications/.*Google Chrome .*--headless'; sleep 2; }
release; trap - EXIT INT TERM
logline "END rc=$rc"; touch $W/R5E/runs/$tag.DONE
exit $rc
