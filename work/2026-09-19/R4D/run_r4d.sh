#!/bin/zsh
# R4D: ONE passive run (capacity $cap) of bundles/$bundle — copy of R4C/run_c32.sh with R4D paths; usage: run_r4d.sh [bundle] [label] [cap_ms] [capacity] with B0/bench_native.mjs (B0_TRIGGER=keyboard per R3K, no mouse event, heap flag as
# combined4's bench rows: heap=1, trace=0). Lock discipline = R3M/run_correctness.sh (round-4 rules): mkdir CHROME.lock, stamp CHROME.lock/owner,
# touch -c every 30 s, an existing CHROME.lock FILE counts as held and is never removed, rmdir ONLY if the owner marker is mine (toucher killed first);
# Chrome matched by '^/Applications/.*Google Chrome .*--headless'. AC power required at start and checked every 30 s (battery -> abort, run INVALID).

set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=${1:-combined4-c32b}; label=${2:-c32b-run1}; capms=${3:-2400000}; cap=${4:-32}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/R4D/run-$bundle; mkdir -p $out; cp $dir/manifest.json $out/manifest.json
CHROME_RE='^/Applications/.*Google Chrome .*--headless'
logline() { echo "- $(date '+%F %T') [R4D run/$bundle/$label] $*" >> $W/R4D.log.md; echo "$(date '+%F %T') $*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
on_ac || { logline "NOT on AC power ($(pmset -g batt | tr '\n' ' ')) — refusing to run"; exit 9; }
OWNER="R4D run_r4d $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R4D run_r4d $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner'))"; fi; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($( [[ -f $W/CHROME.lock ]] && echo 'plain FILE — waiting' || cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner marker')), polling every 3 s"; sleep 3; waited=$((waited+3)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f "$CHROME_RE" >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f "$CHROME_RE" >/dev/null || break
  logline "lock acquired but a foreign Chrome is still running after 90 s — releasing lock, back to polling"; release; sleep 15
done
trap 'release; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null' EXIT INT TERM
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
port=$((46000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 &
spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}\n" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
curl -s -o /dev/null -w "%{http_code}\n" "$url" | grep -q 200 || { logline "server did not serve $url after 90 s"; exit 4; }
avail_kb=$(df -k / | tail -1 | awk '{print $4}')
logline "START passive $cap-token run url=$url waited=${waited}s cap_ms=$capms trigger=keyboard heap=1 trace=0 disk_free_MB=$((avail_kb/1024)) power='$(pmset -g batt | sed -n 2p | tr -s "\t" " ")' load=$(sysctl -n vm.loadavg) top=$(ps -Ao %cpu,comm -r | sed -n 2,3p | awk '{printf "%s:%s ", $1, substr($2, length($2)-20)}')"
B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=1 B0_TRACE=0 B0_CAP_MS=$capms B0_CAPACITY=$cap B0_TRIGGER=keyboard B0_INVALIDATION=0 \
  caffeinate -dims $NODE $W/B0/bench_native.mjs > $out/$label.stdout.log 2>&1 &
npid=$!
# watchdog: wall cap (cap_ms + 300 s for load/readback), Chrome-gone-60-s, power flip every 30 s
WALL_CAP_S=$(( capms / 1000 + 300 )); t0=$(date +%s); seen_chrome=0; gone_since=0; why=""; lastpow=$t0
while kill -0 $npid 2>/dev/null; do
  sleep 5; now=$(date +%s)
  if pgrep -f "$CHROME_RE" >/dev/null; then seen_chrome=1; gone_since=0
  elif (( seen_chrome )); then (( gone_since == 0 )) && gone_since=$now; (( now - gone_since >= 60 )) && { why="Chrome gone for 60 s, node still alive (hung in close)"; break; }
  fi
  (( now - t0 >= WALL_CAP_S )) && { why="wall clock cap ${WALL_CAP_S}s"; break; }
  if (( now - lastpow >= 30 )); then lastpow=$now; on_ac || { why="POWER FLIPPED TO BATTERY ($(pmset -g batt | sed -n 2p | tr -s '\t' ' ')) — run INVALID"; touch $out/$label.INVALID-battery; break; }; fi
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing node $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
kill $spid 2>/dev/null; spid=
sleep 1
pgrep -f "$CHROME_RE" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "$CHROME_RE"; sleep 2; }
release; trap - EXIT INT TERM
logline "END node rc=$rc power='$(pmset -g batt | sed -n 2p | tr -s "\t" " ")' load=$(sysctl -n vm.loadavg) json=$(ls $out/$label.json 2>/dev/null)"
python3 $W/R4C/summarize32.py $out/$label.json > $out/$label.summary.md 2>&1 && logline "summary -> $out/$label.summary.md"
touch $out/DONE
exit $rc
