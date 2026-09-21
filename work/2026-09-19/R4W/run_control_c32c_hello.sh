#!/bin/zsh
# R4W control: bundles/combined4-c32c with the DEFAULT Hello prompt (no B0_PROMPT_TOKEN), same protocol as c32d-run1
# (R4M lock discipline, keyboard trigger, heap=1, trace=0, AC checked every 30 s, vm_stat + swapusage + memory_pressure before/after).
# Output R4W/run-combined4-c32c/c32c-runD-hello-late.*  usage: run_control_c32c_hello.sh [label] [cap_ms]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
CHROME_RE='^/Applications/.*Google Chrome .*--headless'
bundle=combined4-c32c; label=${1:-c32c-runD-hello-late}; capms=${2:-2400000}
out=$W/R4W/run-$bundle; mkdir -p $out; cp $W/bundles/$bundle/manifest.json $out/manifest.json
logline() { echo "- $(date '+%F %T') [R4W control/$label] $*" >> $W/R4W.log.md; echo "$(date '+%F %T') $*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
on_ac || { logline "NOT on AC power — refusing to run"; exit 9; }
OWNER="R4W control $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R4W control $$ " $W/CHROME.lock/owner; }
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
port=$((47000 + RANDOM % 2000)); dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q 200 || { logline "server did not serve $url"; exit 4; }
{ vm_stat; sysctl vm.swapusage; } > $out/$label.vm_stat.before.txt; memory_pressure -Q > $out/$label.memory_pressure.before.txt 2>&1
logline "START passive 32-token CONTROL run $bundle prompt=default(15496 Hello) ref=R4C/reference_ids_32.json url=$url waited=${waited}s cap_ms=$capms trigger=keyboard heap=1 trace=0 power='$(pmset -g batt | sed -n 2p | tr -s "\t" " ")' load=$(sysctl -n vm.loadavg) swap='$(sysctl -n vm.swapusage)' free_pages=$(vm_stat | awk '/Pages free/{print $3}') top=$(ps -Ao %cpu,rss,comm -r | sed -n 2,4p | awk '{printf "%s:%dMB:%s ", $1, $2/1024, substr($3, length($3)-18)}')"
B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=1 B0_TRACE=0 B0_CAP_MS=$capms B0_CAPACITY=32 B0_TRIGGER=keyboard B0_INVALIDATION=0 \
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
{ vm_stat; sysctl vm.swapusage; } > $out/$label.vm_stat.after.txt; memory_pressure -Q > $out/$label.memory_pressure.after.txt 2>&1
release; trap - EXIT INT TERM
logline "END node rc=$rc power='$(pmset -g batt | sed -n 2p | tr -s "\t" " ")' load=$(sysctl -n vm.loadavg) swap='$(sysctl -n vm.swapusage)' json=$(ls $out/$label.json 2>/dev/null)"
python3 $W/R4W/summarize32.py $out/$label.json $W/R4C/reference_ids_32.json > $out/$label.summary.md 2>&1 && logline "summary -> $out/$label.summary.md"
touch $out/DONE
exit $rc
