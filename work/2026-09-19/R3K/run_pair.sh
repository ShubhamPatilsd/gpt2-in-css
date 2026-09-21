#!/bin/zsh
# R3K: under the Chromium mutex, run TWO 2-token light-traced sessions of one bundle with B0/bench_native.mjs:
#   trigger=click (+ mouseoff default) then trigger=keyboard. Lock: mkdir CHROME.lock (poll 15 s), refuse while a foreign
#   headless Chrome runs, touch every 30 s, per-run wall cap (B0_CAP_MS + outer watchdog), rmdir on exit.
# usage: run_pair.sh <bundle> [cap_s=240]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19; OUT=$W/R3K/runs
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
CHROME='^/Applications/.*Google Chrome .*--headless'
bundle=$1; cap=${2:-240}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
logline() { echo "- $(date '+%F %T') [R3K run_pair/$bundle] $*" >> $W/R3K.log.md; echo "$(date '+%T') $*"; }
mkdir -p $OUT
pmset -g batt | head -1 | grep -q "AC Power" || { logline "on battery — refusing"; exit 4; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($(cat $W/CHROME.lock/owner 2>/dev/null | head -c 80)), polling 15 s"; sleep 15; waited=$((waited+15)); done
  for _ in $(seq 1 12); do pgrep -f "$CHROME" >/dev/null || break; touch $W/CHROME.lock; sleep 5; waited=$((waited+5)); done
  pgrep -f "$CHROME" >/dev/null || break
  logline "lock acquired but a foreign Chrome still runs after 60 s — releasing, back to polling"; rmdir $W/CHROME.lock 2>/dev/null; sleep 15
done
echo "R3K $(date -u +%FT%TZ) run_pair $bundle" > $W/CHROME.lock/owner
( while [[ -d $W/CHROME.lock ]]; do touch $W/CHROME.lock; sleep 30; done ) & tpid=$!
spid=; npid=
cleanup() { [[ -n $npid ]] && { pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; }; pgrep -f "$CHROME" >/dev/null && { pkill -f "$CHROME"; sleep 2; }; [[ -n $spid ]] && kill $spid 2>/dev/null; kill $tpid 2>/dev/null; rm -rf $W/CHROME.lock; }
trap 'cleanup; logline "INTERRUPTED, lock released"; exit 130' INT TERM
logline "LOCK taken (waited ${waited}s) load=$(sysctl -n vm.loadavg) batt=$(pmset -g batt | sed -n 2p | tr -s '\t' ' ' | cut -c1-50)"
port=$((46000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $OUT/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 1; done
rc_all=0
for trig in click keyboard; do
  label=$bundle-$trig
  logline "START $label trace=1 tokens=2 cap=${cap}s url=$url"
  B0_URL=$url B0_LABEL=$label B0_OUT=$OUT B0_HEAP=1 B0_TRACE=1 B0_CAPACITY=2 B0_CAP_MS=$((cap*1000)) B0_TRIGGER=$trig \
    caffeinate -dims $NODE $W/B0/bench_native.mjs > $OUT/$label.stdout.log 2>&1 & npid=$!
  t0=$(date +%s); why=""
  while kill -0 $npid 2>/dev/null; do sleep 5; (( $(date +%s) - t0 >= cap + 120 )) && { why="outer watchdog $((cap+120))s"; break; }; done
  if [[ -n $why ]]; then logline "WATCHDOG $label: $why — killing"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
  npid=
  pgrep -f "$CHROME" >/dev/null && { logline "Chrome still alive after $label, killing"; pkill -f "$CHROME"; sleep 2; }
  logline "END $label rc=$rc $(grep -E '"event":"(token-captured|run-keyed|run-clicked|trace-saved)"' $OUT/$label.stdout.log | cut -c1-160 | tr '\n' ' ')"
  (( rc != 0 )) && rc_all=$rc
  sleep 3
done
kill $spid 2>/dev/null; spid=
kill $tpid 2>/dev/null; rm -rf $W/CHROME.lock; trap - INT TERM
logline "LOCK released rc=$rc_all"
exit $rc_all
