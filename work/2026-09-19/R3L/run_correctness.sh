#!/bin/zsh
# R3L correctness run (adapted from R2D/run_correctness.sh: same watchdog + wall cap, R2H paths). usage: run_correctness.sh [bundle-name]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=${1:-R3L}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/R3L/run-$bundle; mkdir -p $out; cp $dir/manifest.json $out/manifest.json
logline() { echo "- $(date '+%F %T') [R3L correctness/$bundle] $*" >> $W/R3L.log.md; echo "$*"; }
waited=0
# R2H: harness Chromes are matched by binary path + --headless (a plain "Google Chrome --" pattern matched other agents' poll shells)
# R2H: acquire the lock, then wait up to 90 s for the previous holder's Chrome to finish exiting; if one is still
# running, release the lock and keep polling (the R2D version aborted here, which lost the lock to the next poller).
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 3 s"; sleep 3; waited=$((waited+3)); done
  for _ in $(seq 1 30); do pgrep -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless' >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless' >/dev/null || break
  logline "lock acquired but a foreign Chrome is still running after 90 s — releasing lock, back to polling"
  rmdir $W/CHROME.lock 2>/dev/null; sleep 3
done
trap '[[ -n ${tpid:-} ]] && kill $tpid 2>/dev/null; rmdir $W/CHROME.lock 2>/dev/null; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null' EXIT INT TERM
# R2H: ground rule — touch the lock every 30 s while held (lets others tell a live holder from a stale one)
( while [[ -d $W/CHROME.lock ]]; do touch $W/CHROME.lock; sleep 30; done ) & tpid=$!
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 &
spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
# R2H: wait up to 90 s for the static server (R2D's fixed 2 s failed at 15:03 under B0's trace-parsing load)
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}\n" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
curl -s -o /dev/null -w "%{http_code}\n" "$url" | grep -q 200 || { logline "server did not serve $url after 90 s"; exit 4; }
logline "START correctness run url=$url waited=${waited}s power=$(pmset -g batt | head -1 | tr -d "\n") $(pmset -g batt | sed -n 2p | tr -s "\t" " ") load=$(sysctl -n vm.loadavg)"
F4_URL=$url F4_OUT=$out F4_CAPACITY=8 F4_CAP_MS=1200000 caffeinate -dims $NODE $W/R3L/correctness_run.mjs > $out/harness.log 2>&1 &
npid=$!
# Watchdog (see R2D/ab/run_ab.sh): hard wall clock (default 900 s = load + 8 x 90 s + readback) and Chrome-exit (node alive 60 s after Chrome vanished -> hung in close).
WALL_CAP_S=${WALL_CAP_S:-900}; t0=$(date +%s); seen_chrome=0; gone_since=0; why=""
while kill -0 $npid 2>/dev/null; do
  sleep 5
  now=$(date +%s)
  if pgrep -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless' >/dev/null; then seen_chrome=1; gone_since=0
  elif (( seen_chrome )); then (( gone_since == 0 )) && gone_since=$now; (( now - gone_since >= 60 )) && { why="Chrome gone for 60 s, node still alive (hung in close)"; break; }
  fi
  (( now - t0 >= WALL_CAP_S )) && { why="wall clock cap ${WALL_CAP_S}s"; break; }
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing node $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
kill $spid 2>/dev/null; spid=
sleep 1
pgrep -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless' >/dev/null && { logline "Chrome still alive, killing"; pkill -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless'; sleep 2; }
kill $tpid 2>/dev/null; rmdir $W/CHROME.lock 2>/dev/null; trap - EXIT INT TERM
logline "END chrome rc=$rc; $(grep '"final"' $out/harness.log | cut -c1-400)"
cd $W/R3L && OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
logline "verify rc=$? $(tail -c 600 $out/verify.log | tr '\n' ' ')"
touch $out/DONE
exit $rc
