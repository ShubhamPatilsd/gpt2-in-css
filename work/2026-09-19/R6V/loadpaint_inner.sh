#!/bin/zsh
# R6V: load-time UX probe of one bundle (serve, loadpaint.mjs, screenshots) -> R6V/runs/loadpaint-<bundle>/. usage: loadpaint_inner.sh <bundle> <run 0|1>
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; dorun=${2:-0}; out=$W/R6V/runs/loadpaint-$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') url=$url load=$(sysctl -n vm.loadavg) swap=$(sysctl -n vm.swapusage)"
R6V_URL=$url R6V_OUT=$out R6V_RUN=$dorun caffeinate -dims $NODE $W/R6V/loadpaint.mjs > $out/harness.log 2>&1
rc=$?
kill $spid 2>/dev/null
grep -h '"state"\|"load-event"\|"fonts-loaded"' $out/harness.log | cut -c1-300
exit $rc
