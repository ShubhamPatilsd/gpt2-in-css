#!/bin/zsh
# R2C correctness run (copy of F4/run_correctness.sh) (NOT a timing run) of a bundle under the Chromium mutex. usage: run_correctness.sh [bundle-name]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=${1:-R2C}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/R2C/run-$bundle; mkdir -p $out; cp $dir/manifest.json $out/manifest.json
logline() { echo "- $(date '+%F %T') [correctness/$bundle] $*" >> $W/R2C.log.md; echo "$*"; }
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
logline "START correctness run url=$url waited=${waited}s"
R2C_URL=$url R2C_OUT=$out R2C_CAPACITY=8 R2C_CAP_MS=1200000 caffeinate -dims $NODE $W/R2C/correctness_run.mjs > $out/harness.log 2>&1
rc=$?
kill $spid 2>/dev/null; spid=
sleep 1
pgrep -f "Google Chrome --" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "Google Chrome --"; sleep 2; }
rmdir $W/CHROME.lock 2>/dev/null; trap - EXIT INT TERM
logline "END chrome rc=$rc; $(grep '"final"' $out/harness.log | cut -c1-400)"
cd $W/R2C && OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
logline "verify rc=$? $(tail -c 600 $out/verify.log | tr '\n' ' ')"
touch $out/DONE
exit $rc
