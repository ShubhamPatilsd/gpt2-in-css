#!/bin/zsh
# R4T 2-layer smoke under the Chromium mutex (R3M lock protocol as run_r4t.sh): serve bundles/<b>, run run_bundle.mjs (light trace), frames.py.
# usage: run_smoke.sh <tag> <bundle> [<bundle> ...]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
tag=$1; shift
logline() { echo "- $(date '+%F %T') [R4T smoke/$tag] $*" >> $W/R4T.log.md; echo "$*"; }
OWNER="R4T smoke $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R4T smoke $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine"; fi; }
waited=0
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
  out=$W/R4T/runs/$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle; mkdir -p $out; cp $dir/manifest.json $out/
  port=$((45000 + RANDOM % 2000))
  python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
  url="http://127.0.0.1:$port/$rel/index.html"
  for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
  R2F_URL=$url R2F_OUT=$out R2F_TRACE=${TRACE:-1} R2F_POLL_MS=2000 R2F_CAP_MS=${CAP_MS:-300000} caffeinate -dims $NODE $W/R4T/run_bundle.mjs > $out/harness.log 2>&1 &
  npid=$!; t0=$(date +%s)
  while kill -0 $npid 2>/dev/null; do sleep 5; (( $(date +%s) - t0 >= ${WALL_CAP_S:-420} )) && { logline "WATCHDOG wall cap — killing $npid"; pkill -P $npid; kill $npid; sleep 2; kill -9 $npid 2>/dev/null; break; }; done
  wait $npid 2>/dev/null; r=$?; (( r != 0 )) && rc=$r
  kill $spid 2>/dev/null; spid=
  logline "$bundle rc=$r $(grep '"final"' $out/harness.log | cut -c1-300)"
  [[ -f $out/trace.json.gz ]] && python3 $W/R4T/frames.py $out > $out/frames.log 2>&1
done
pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null && { logline "Chrome still alive, killing"; pkill -f '^/Applications/.*Google Chrome .*--headless'; sleep 2; }
release; trap - EXIT INT TERM
logline "END rc=$rc"; touch $W/R4T/runs/$tag.DONE
exit $rc
