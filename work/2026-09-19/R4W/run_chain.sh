#!/bin/zsh
# R4W Chrome chain under ONE CHROME.lock acquisition (R4M/run_c32.sh lock discipline; owner "R4W chain <pid> <time>"; toucher every 30 s;
# rmdir ONLY if the owner marker is mine; poll every 5 s while held; AC power required, checked every 30 s):
#   1. 2-layer smoke pair smoke-R4W-2L (R4W_V_PRECAT=1) vs smoke-R4W-2L-ref (=0) with R4W/run_bundle.mjs (= R4T's; ids readback, no trace)
#      -> ids must be identical and non-empty, else STOP.
#   2. ONE passive 32-token run of bundles/combined4-c32d, B0_PROMPT_TOKEN=40 vs R4P/reference_ids_32_40.json, keyboard trigger, heap=1,
#      trace=0 (R4W/bench_native.mjs = R4M's), vm_stat + memory_pressure before/after, summarize32.
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
CHROME_RE='^/Applications/.*Google Chrome .*--headless'
label=${1:-c32d-run1}; capms=${2:-2400000}
logline() { echo "- $(date '+%F %T') [R4W chain] $*" >> $W/R4W.log.md; echo "$(date '+%F %T') $*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
on_ac || { logline "NOT on AC power — refusing to run"; exit 9; }
OWNER="R4W chain $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R4W chain $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner'))"; fi; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($( [[ -f $W/CHROME.lock ]] && echo 'plain FILE — waiting' || cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner marker')), polling every 5 s"; sleep 5; waited=$((waited+5)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f "$CHROME_RE" >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f "$CHROME_RE" >/dev/null || break
  logline "lock acquired but a foreign Chrome is still running after 90 s — releasing lock, back to polling"; release; sleep 5
done
trap 'release; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null' EXIT INT TERM
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
logline "LOCK ACQUIRED after ${waited}s; load=$(sysctl -n vm.loadavg) free_pages=$(vm_stat | awk '/Pages free/{print $3}')"

serve() { # $1 bundle -> sets url, spid
  local dir=$W/bundles/$1 rel=work/2026-09-19/bundles/$1 log=$2
  port=$((47000 + RANDOM % 2000))
  python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $log 2>&1 & spid=$!
  url="http://127.0.0.1:$port/$rel/index.html"
  for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && return 0; sleep 2; done
  return 1
}

# ---- 1. smoke pair
typeset -A smoke_ids
for bundle in smoke-R4W-2L-ref smoke-R4W-2L; do
  out=$W/R4W/runs/$bundle; mkdir -p $out; cp $W/bundles/$bundle/manifest.json $out/
  serve $bundle $out/server.log || { logline "server did not serve $bundle"; exit 4; }
  logline "SMOKE START $bundle url=$url load=$(sysctl -n vm.loadavg)"
  R2F_URL=$url R2F_OUT=$out R2F_TRACE=0 R2F_POLL_MS=2000 R2F_CAP_MS=300000 caffeinate -dims $NODE $W/R4W/run_bundle.mjs > $out/harness.log 2>&1 &
  npid=$!; t0=$(date +%s)
  while kill -0 $npid 2>/dev/null; do sleep 5; (( $(date +%s) - t0 >= 420 )) && { logline "WATCHDOG smoke wall cap — killing $npid"; pkill -P $npid; kill $npid; sleep 2; kill -9 $npid 2>/dev/null; break; }; on_ac || { logline "POWER FLIPPED TO BATTERY during smoke — run INVALID"; touch $out/INVALID-battery; }; done
  wait $npid 2>/dev/null; r=$?
  kill $spid 2>/dev/null; spid=; sleep 1
  pgrep -f "$CHROME_RE" >/dev/null && { pkill -f "$CHROME_RE"; sleep 2; }
  ids=$(python3 -c "
import json,sys
for line in open('$out/harness.log'):
    try: d=json.loads(line)
    except Exception: continue
    if d.get('event')=='final': print(json.dumps(d.get('tokens'))); break
" 2>/dev/null)
  smoke_ids[$bundle]="$ids"
  logline "SMOKE END $bundle rc=$r ids=$ids $(grep '"final"' $out/harness.log | cut -c1-200)"
done
if [[ -z ${smoke_ids[smoke-R4W-2L]} || ${smoke_ids[smoke-R4W-2L]} == "null" || ${smoke_ids[smoke-R4W-2L]} != ${smoke_ids[smoke-R4W-2L-ref]} ]]; then
  logline "SMOKE FAIL: on=${smoke_ids[smoke-R4W-2L]} off=${smoke_ids[smoke-R4W-2L-ref]} — NOT running the 32-token run"; touch $W/R4W/SMOKE-FAIL; exit 5
fi
logline "SMOKE PASS: identical ids ${smoke_ids[smoke-R4W-2L]}"; touch $W/R4W/SMOKE-PASS

# ---- 2. 32-token run
bundle=combined4-c32d; out=$W/R4W/run-$bundle; mkdir -p $out; cp $W/bundles/$bundle/manifest.json $out/manifest.json
serve $bundle $out/$label.server.log || { logline "server did not serve $bundle"; exit 4; }
vm_stat > $out/$label.vm_stat.before.txt; memory_pressure -Q > $out/$label.memory_pressure.before.txt 2>&1
logline "START passive 32-token run $bundle prompt=40 ref=R4P/reference_ids_32_40.json url=$url cap_ms=$capms trigger=keyboard heap=1 trace=0 power='$(pmset -g batt | sed -n 2p | tr -s "\t" " ")' load=$(sysctl -n vm.loadavg) free_pages=$(vm_stat | awk '/Pages free/{print $3}') top=$(ps -Ao %cpu,rss,comm -r | sed -n 2,4p | awk '{printf "%s:%dMB:%s ", $1, $2/1024, substr($3, length($3)-18)}')"
B0_PROMPT_TOKEN=40 B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=1 B0_TRACE=0 B0_CAP_MS=$capms B0_CAPACITY=32 B0_TRIGGER=keyboard B0_INVALIDATION=0 \
  caffeinate -dims $NODE $W/R4W/bench_native.mjs > $out/$label.stdout.log 2>&1 &
npid=$!
WALL_CAP_S=$(( capms / 1000 + 300 )); t0=$(date +%s); seen_chrome=0; gone_since=0; why=""; lastpow=$t0
while kill -0 $npid 2>/dev/null; do
  sleep 5; now=$(date +%s)
  if pgrep -f "$CHROME_RE" >/dev/null; then seen_chrome=1; gone_since=0
  elif (( seen_chrome )); then (( gone_since == 0 )) && gone_since=$now; (( now - gone_since >= 60 )) && { why="Chrome gone for 60 s, node still alive"; break; }
  fi
  (( now - t0 >= WALL_CAP_S )) && { why="wall clock cap ${WALL_CAP_S}s"; break; }
  if (( now - lastpow >= 30 )); then lastpow=$now; on_ac || { why="POWER FLIPPED TO BATTERY — run INVALID"; touch $out/$label.INVALID-battery; break; }; fi
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing node $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
kill $spid 2>/dev/null; spid=; sleep 1
pgrep -f "$CHROME_RE" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "$CHROME_RE"; sleep 2; }
vm_stat > $out/$label.vm_stat.after.txt; memory_pressure -Q > $out/$label.memory_pressure.after.txt 2>&1
release; trap - EXIT INT TERM
logline "END node rc=$rc power='$(pmset -g batt | sed -n 2p | tr -s "\t" " ")' load=$(sysctl -n vm.loadavg) json=$(ls $out/$label.json 2>/dev/null)"
python3 $W/R4W/summarize32.py $out/$label.json $W/R4P/reference_ids_32_40.json > $out/$label.summary.md 2>&1 && logline "summary -> $out/$label.summary.md"
touch $out/DONE
exit $rc
