#!/bin/zsh
# R2D correctness run (NOT a timing run) of a bundle under the Chromium mutex. usage: run_correctness.sh [bundle-name]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=${1:-combined}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/R2D/run-$bundle; mkdir -p $out; cp $dir/manifest.json $out/manifest.json
logline() { echo "- $(date '+%F %T') [R2D correctness/$bundle] $*" >> $W/R2D.log.md; echo "$*"; }
waited=0
while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 15 s"; sleep 15; waited=$((waited+15)); done
trap 'rmdir $W/CHROME.lock 2>/dev/null; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null' EXIT INT TERM
if pgrep -f "Google Chrome --" >/dev/null; then logline "another Chrome is running — abort"; exit 3; fi
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 &
spid=$!
sleep 2
url="http://127.0.0.1:$port/$rel/index.html"
curl -s -o /dev/null -w "%{http_code}\n" "$url" | grep -q 200 || { logline "server did not serve $url"; exit 4; }
logline "START correctness run url=$url waited=${waited}s power=$(pmset -g batt | head -1 | tr -d "\n") $(pmset -g batt | sed -n 2p | tr -s "\t" " ") load=$(sysctl -n vm.loadavg)"
F4_URL=$url F4_OUT=$out F4_CAPACITY=8 F4_CAP_MS=1200000 caffeinate -dims $NODE $W/R2D/correctness_run.mjs > $out/harness.log 2>&1 &
npid=$!
# Watchdog (see R2D/ab/run_ab.sh): hard wall clock (default 900 s = load + 8 x 90 s + readback) and Chrome-exit (node alive 60 s after Chrome vanished -> hung in close).
WALL_CAP_S=${WALL_CAP_S:-900}; t0=$(date +%s); seen_chrome=0; gone_since=0; why=""
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
logline "END chrome rc=$rc; $(grep '"final"' $out/harness.log | cut -c1-400)"
cd $W/R2D && OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
logline "verify rc=$? $(tail -c 600 $out/verify.log | tr '\n' ' ')"
touch $out/DONE
exit $rc
