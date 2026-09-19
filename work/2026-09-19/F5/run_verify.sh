#!/bin/zsh
# F5 correctness run under the Chromium mutex (PLAN.md). usage: run_verify.sh [bundle-name]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=${1:-F5}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
out=$W/F5/verify; mkdir -p $out
logline() { echo "- $(date '+%F %T') [verify/$bundle] $*" >> $W/F5.log.md; echo "$*"; }
waited=0
while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held, polling every 15 s"; sleep 15; waited=$((waited+15)); done
trap 'rmdir $W/CHROME.lock 2>/dev/null; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null' EXIT INT TERM
if pgrep -f "Google Chrome --" >/dev/null; then logline "another Chrome is running — abort"; exit 3; fi
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$bundle.server.log 2>&1 &
spid=$!
sleep 2
url="http://127.0.0.1:$port/$rel/index.html"
curl -s -o /dev/null -w "%{http_code}\n" "$url" | grep -q 200 || { logline "server did not serve $url"; exit 4; }
logline "START correctness run (not a timing run) url=$url waited=${waited}s"
F5_URL=$url F5_OUT=$out/$bundle.json F5_CAPACITY=8 caffeinate -dims $NODE $W/F5/verify_run.mjs > $out/$bundle.stdout.log 2>&1
rc=$?
kill $spid 2>/dev/null; spid=
sleep 1
pgrep -f "Google Chrome --" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "Google Chrome --"; sleep 2; }
rmdir $W/CHROME.lock 2>/dev/null; trap - EXIT INT TERM
logline "END rc=$rc $(python3 -c "import json;r=json.load(open('$out/$bundle.json'));print('ids',r['ids'],'stop',r['stop'],'wall',round(r['wallSeconds']),'s')" 2>&1)"
exit $rc
