#!/bin/zsh
# R2D short A/B frame probe (NOT a timing run): B0's harness, 2 tokens, light trace. usage: run_ab.sh <bundle-name> <label>
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; label=$2; cap=${3:-420000}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/R2D/ab/runs; mkdir -p $out
logline() { echo "- $(date '+%F %T') [R2D ab/$label] $*" >> $W/R2D.log.md; echo "$*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
cleanup() { rmdir $W/CHROME.lock 2>/dev/null; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null; }
trap 'cleanup' EXIT
trap 'cleanup; trap - EXIT; exit 130' INT TERM
on_ac || { logline "on battery — refusing"; exit 6; }
waited=0
while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 15 s"; sleep 15; waited=$((waited+15)); done
for try in {1..40}; do pgrep -f "Google Chrome --" >/dev/null || break; (( try == 1 )) && logline "foreign Chrome alive — waiting"; sleep 15; done
pgrep -f "Google Chrome --" >/dev/null && { logline "foreign Chrome still alive — abort"; exit 3; }
avail_kb=$(df -k / | tail -1 | awk '{print $4}'); (( avail_kb >= 1572864 )) || { logline "disk < 1.5 GB — abort"; exit 2; }
port=$((47000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 &
spid=$!
sleep 2
url="http://127.0.0.1:$port/$rel/index.html"
curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q 200 || { logline "server did not serve $url"; exit 4; }
logline "START bundle=$bundle 2 tokens light trace url=$url waited=${waited}s load=$(sysctl -n vm.loadavg) top=$(ps -Ao %cpu,comm -r | sed -n 2p | awk '{printf "%s:%s", $1, substr($2, length($2)-20)}')"
B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=1 B0_TRACE=1 B0_CAP_MS=$cap B0_CAPACITY=2 \
  caffeinate -dims $NODE $W/B0/bench_native.mjs > $out/$label.stdout.log 2>&1 &
npid=$!
# Watchdog (after the 02:58 hang: node stayed in browser.close() for 3 h holding the lock):
#  (a) hard wall clock: load + 2 tokens x 90 s + trace export = 60 + 180 + 120 s -> WALL_CAP_S (default 420 s);
#  (b) Chrome-exit: once Chrome has been launched, if no Chrome process exists for 60 s while node is alive, node is hung -> kill.
WALL_CAP_S=${WALL_CAP_S:-420}; t0=$(date +%s); seen_chrome=0; gone_since=0; why=""
while kill -0 $npid 2>/dev/null; do
  sleep 5
  now=$(date +%s)
  if pgrep -f "Google Chrome --" >/dev/null; then seen_chrome=1; gone_since=0
  elif (( seen_chrome )); then (( gone_since == 0 )) && gone_since=$now; (( now - gone_since >= 60 )) && { why="Chrome gone for 60 s, node still alive (hung in close)"; break; }
  fi
  (( now - t0 >= WALL_CAP_S )) && { why="wall clock cap ${WALL_CAP_S}s"; break; }
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing node $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
kill $spid 2>/dev/null; spid=
sleep 1
pgrep -f "Google Chrome --" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "Google Chrome --"; sleep 2; }
rmdir $W/CHROME.lock 2>/dev/null; trap - EXIT INT TERM
logline "END rc=$rc $(python3 $W/B0/summarize_run.py $out/$label.json --oneline 2>&1 | tail -1)"
if [[ -f $out/$label-trace.json.gz ]]; then
  sz=$(stat -f%z $out/$label-trace.json.gz); logline "parsing trace ($((sz/1048576)) MB gz)"
  python3 $W/B0/parse_trace.py $out/$label-trace.json.gz $out/$label.json $out/$label > $out/$label.parse.log 2>&1 && ( cd $out && python3 $W/B0/make_tables.py $label > $label-tables.md 2>>$label.parse.log ) && logline "trace parsed -> $out/$label-tables.md" || logline "trace parse FAILED (see $out/$label.parse.log)"
  logline "raw trace kept for frame_anatomy ($((sz/1048576)) MB gz)"
fi
exit $rc
