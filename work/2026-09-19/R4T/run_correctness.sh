#!/bin/zsh
# R3M correctness run (= R2H/run_correctness.sh with R3M paths; R2D watchdog + wall cap 1500 s, 3 s lock poll, 30 s lock toucher).
# R3M lock fixes (coordinator 22:08, R3L.md item 10): owner marker CHROME.lock/owner; release = kill toucher FIRST, then rmdir ONLY if the marker is mine;
# an existing CHROME.lock FILE is treated as held and never removed; the toucher uses `touch -c` so it can never create a file. usage: run_correctness.sh [bundle-name]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=${1:-R4T}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/R4T/run-$bundle; mkdir -p $out; cp $dir/manifest.json $out/manifest.json
logline() { echo "- $(date '+%F %T') [R4T correctness/$bundle] $*" >> $W/R4T.log.md; echo "$*"; }
waited=0
# R2H: harness Chromes are matched by binary path + --headless (a plain "Google Chrome --" pattern matched other agents' poll shells)
# R2H: acquire the lock, then wait up to 90 s for the previous holder's Chrome to finish exiting; if one is still
# running, release the lock and keep polling (the R2D version aborted here, which lost the lock to the next poller).
# R3M (coordinator 22:08 / R3L.md item 10): an existing CHROME.lock FILE counts as "held" — never rm it (the orchestrator's fixer handles it);
# `mkdir` fails on a file as on a directory, so the poll below already treats it as held. After a successful mkdir, stamp CHROME.lock/owner.
OWNER="R4T run_correctness $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R4T run_correctness $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }   # toucher FIRST, so it cannot recreate the lock as a file
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner'))"; fi; }
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($( [[ -f $W/CHROME.lock ]] && echo 'plain FILE — waiting for the fixer' || cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner marker')), polling every 3 s"; sleep 3; waited=$((waited+3)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless' >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless' >/dev/null || break
  logline "lock acquired but a foreign Chrome is still running after 90 s — releasing lock, back to polling"
  release; sleep 3
done
trap 'release; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null' EXIT INT TERM
# R2H: ground rule — touch the lock every 30 s while held (lets others tell a live holder from a stale one).
# R3M: `touch -c` never creates a file if the directory has vanished; touch the owner marker too (also -c).
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 &
spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
# R2H: wait up to 90 s for the static server (R2D's fixed 2 s failed at 15:03 under B0's trace-parsing load)
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}\n" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
curl -s -o /dev/null -w "%{http_code}\n" "$url" | grep -q 200 || { logline "server did not serve $url after 90 s"; exit 4; }
logline "START correctness run url=$url waited=${waited}s power=$(pmset -g batt | head -1 | tr -d "\n") $(pmset -g batt | sed -n 2p | tr -s "\t" " ") load=$(sysctl -n vm.loadavg)"
F4_URL=$url F4_OUT=$out F4_CAPACITY=8 F4_CAP_MS=1200000 caffeinate -dims $NODE $W/R4T/correctness_run.mjs > $out/harness.log 2>&1 &
npid=$!
# Watchdog (see R2D/ab/run_ab.sh): hard wall clock (default 900 s = load + 8 x 90 s + readback) and Chrome-exit (node alive 60 s after Chrome vanished -> hung in close).
WALL_CAP_S=${WALL_CAP_S:-1500}; t0=$(date +%s); seen_chrome=0; gone_since=0; why=""
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
release; trap - EXIT INT TERM
logline "END chrome rc=$rc; $(grep '"final"' $out/harness.log | cut -c1-400)"
cd $W/R4T && OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
logline "verify rc=$? $(tail -c 600 $out/verify.log | tr '\n' ' ')"
touch $out/DONE
exit $rc
