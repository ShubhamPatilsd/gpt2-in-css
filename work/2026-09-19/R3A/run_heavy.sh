#!/bin/zsh
# R3A heavy-trace driver (mirrors B0/run_bench.sh gates; one traced 8-token session of a bundle).
# usage: run_heavy.sh <bundle> <label> <cats> [from_token=2] [cap_ms=900000]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; label=$2; cats=$3; from=${4:-2}; cap=${5:-900000}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/R3A/runs; mkdir -p $out
CHROME_RE='^/Applications/.*Google Chrome .*--headless'
logline() { echo "- $(date '+%Y-%m-%d %H:%M:%S') [$label] $*" >> $W/R3A.log.md; echo "$*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
chrome_alive() { pgrep -f "$CHROME_RE" >/dev/null; }
held=0
cleanup() { (( held )) && rmdir $W/CHROME.lock 2>/dev/null; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null; [[ -n ${wpid:-} ]] && kill $wpid 2>/dev/null; }
trap 'cleanup' EXIT
trap 'cleanup; trap - EXIT; exit 130' INT TERM
while true; do
  n=0; while ! on_ac; do (( n % 5 == 0 )) && logline "ON BATTERY — waiting for AC"; sleep 60; n=$((n+1)); done
  waited=0
  while ! mkdir $W/CHROME.lock 2>/dev/null; do
    (( waited == 0 )) && logline "CHROME.lock held, polling 30 s"
    if [[ -d $W/CHROME.lock ]] && ! chrome_alive; then
      age=$(( $(date +%s) - $(stat -f %m $W/CHROME.lock 2>/dev/null || date +%s) ))
      if (( age > 1200 )); then logline "STALE CHROME.lock (mtime $((age/60)) min, no Chrome) — removing"; rmdir $W/CHROME.lock 2>/dev/null; continue; fi
    fi
    sleep 30; waited=$((waited+30))
  done
  held=1; logline "CHROME.lock taken (waited $waited s)"
  for try in {1..120}; do chrome_alive || break; (( try == 1 || try % 20 == 0 )) && logline "foreign Chrome alive — waiting 15 s ($try/120)"; touch $W/CHROME.lock; sleep 15; done
  if chrome_alive; then logline "foreign Chrome still alive after 30 min — abort"; exit 3; fi
  avail_kb=$(df -k / | tail -1 | awk '{print $4}')
  if (( avail_kb < 3145728 )); then logline "disk $((avail_kb/1024)) MB free < 3 GB — abort"; exit 2; fi
  contended=""
  for try in {1..30}; do
    load1=$(sysctl -n vm.loadavg | awk '{print $2}')
    hog=$(ps -Ao %cpu,pid,comm -r | sed -n 2p | awk '{printf "%s:%s", $1, substr($3, length($3)-24)}')
    hogcpu=${hog%%:*}
    if (( $(echo "$load1 < 3.0" | bc -l) )) && (( $(echo "${hogcpu:-0} < 50" | bc -l) )); then contended=""; break; fi
    contended="load1=$load1 top=$hog"
    (( try == 1 || try % 6 == 0 )) && logline "quiet gate: $contended — waiting 30 s ($try/30)"
    touch $W/CHROME.lock; sleep 30
  done
  if [[ -n $contended ]]; then logline "quiet gate timed out; proceeding CONTENDED ($contended)"; echo "$contended" > $out/$label.contended; else rm -f $out/$label.contended; fi
  if on_ac; then break; fi
  logline "power flipped to battery — releasing lock"; rmdir $W/CHROME.lock 2>/dev/null; held=0
done
port=$((43000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 &
spid=$!
sleep 2
url="http://127.0.0.1:$port/$rel/index.html"
if ! curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q 200; then logline "server did not serve $url"; cat $out/$label.server.log; exit 4; fi
sysinfo() { echo "load=$(sysctl -n vm.loadavg | tr -d '{}') swap=$(sysctl -n vm.swapusage | awk '{print $6}') top=$(ps -Ao %cpu,comm -r | sed -n 2,4p | awk '{printf "%s:%s ", $1, substr($2, length($2)-24)}')"; }
logline "START bundle=$bundle heap=1 trace=1 from_token=$from mouseoff=off cap=$cap cats=$cats url=$url disk_free_MB=$((avail_kb/1024)) batt='$(pmset -g batt | sed -n 2p | tr -s '\t' ' ')' $(sysinfo)"
B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=1 B0_TRACE=1 B0_CAP_MS=$cap B0_MOUSEOFF=off R3A_CATS=$cats R3A_TRACE_FROM_TOKEN=$from B0_BUFFER_KB=${R3A_BUFFER_KB:-1500000} \
  caffeinate -dims $NODE $W/R3A/trace_heavy.mjs > $out/$label.stdout.log 2>&1 &
npid=$!
# watchdog: touch the lock every 30 s; battery → kill + mark invalid; also kill if the harness outlives cap + 15 min
t_start=$(date +%s)
( while kill -0 $npid 2>/dev/null; do touch $W/CHROME.lock; sleep 30
    if ! pmset -g batt | head -1 | grep -q "AC Power"; then echo "$(date '+%F %T') battery" > $out/$label.INVALID-battery; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 1; pkill -f "$CHROME_RE" 2>/dev/null; break; fi
    if (( $(date +%s) - t_start > cap/1000 + 900 )); then echo "$(date '+%F %T') wallclock" > $out/$label.INVALID-wallclock; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 1; pkill -f "$CHROME_RE" 2>/dev/null; break; fi
  done ) &
wpid=$!
wait $npid; rc=$?
kill $wpid 2>/dev/null; wpid=
kill $spid 2>/dev/null; spid=
sleep 1
if chrome_alive; then logline "WARNING: Chrome still alive after run, killing"; pkill -f "$CHROME_RE"; sleep 2; fi
rmdir $W/CHROME.lock 2>/dev/null; held=0
trap - EXIT INT TERM
[[ -f $out/$label.INVALID-battery ]] && logline "INVALID: power flipped to battery mid-run"
[[ -f $out/$label.INVALID-wallclock ]] && logline "INVALID: wall-clock cap hit"
logline "END rc=$rc $(python3 -c "
import json,sys
try:
  d=json.load(open('$out/$label.json'))
  print('tokens', [round(t['tokenSeconds'],1) for t in d['tokenEvents']], 'stop', d['stopReason'], 'traceMB', round(d['traceBytes']/1048576), 'dataLoss', d.get('dataLossOccurred'), 'traceStart', d.get('tTraceStart'))
except Exception as e: print('no result json:', e)
") $(sysinfo)"
exit $rc
