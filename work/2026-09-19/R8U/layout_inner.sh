#!/bin/zsh
# R8U: serve one bundle and run layout_probe.mjs. usage: layout_inner.sh <bundle-dir-abs> <out-dir-abs> <WxH>   (env R8U_TYPED R8U_SHOTS R8U_FULL R8U_CAPACITY)
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
dir=$1; out=$2; vp=$3; rel=${dir#$ROOT/}
mkdir -p $out
port=$((47000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') url=$url viewport=$vp load=$(sysctl -n vm.loadavg) swap=$(sysctl -n vm.swapusage)"
R8U_URL=$url R8U_OUT=$out R8U_VIEWPORT=$vp caffeinate -dims $NODE $W/R8U/layout_probe.mjs > $out/harness.log 2>&1; rc=$?
kill $spid 2>/dev/null
grep -o '"event":"\(ready\|load-event\)"[^}]*' $out/harness.log
exit $rc
