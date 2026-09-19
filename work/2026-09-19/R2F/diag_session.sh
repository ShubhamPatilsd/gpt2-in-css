#!/bin/zsh
# usage: diag_session.sh <label> <bundle1,bundle2> ; serves repo root, runs diag_load.mjs (under run_chrome.sh mutex)
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19; NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
label=$1; bundles=(${(s:,:)2}); out=$W/R2F/runs/$label; mkdir -p $out
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $W/bundles/${bundles[1]} > $out/server.log 2>&1 &
spid=$!; sleep 2
urls=""; for b in $bundles; do urls="$urls,http://127.0.0.1:$port/work/2026-09-19/bundles/$b/index.html"; done; urls=${urls#,}
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" "${urls%%,*}" | tee $out/curl.txt
pmset -g batt | head -1 > $out/power.txt
R2F_URLS=$urls R2F_SECS=${R2F_SECS:-90} caffeinate -dims $NODE $W/R2F/diag_load.mjs > $out/diag.log 2>&1
rc=$?; kill $spid 2>/dev/null; cat $out/diag.log | cut -c1-400; exit $rc
