#!/bin/zsh
# R6L: serve bundles/<bundle> with the repo's strict launcher (--no-open, same server the user runs), then N cold loads with load_native.mjs.
# usage: load_inner.sh <bundle> <label> <n> [trace=0]   → R6L/loads/<bundle>/<label>-{1..n}.json (+ trace for run 1 if trace=1)
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19; NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; label=$2; n=$3; trace=${4:-0}; out=$W/R6L/loads/$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out; port=$((47000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') $bundle url=$url swap: $(sysctl -n vm.swapusage) load=$(sysctl -n vm.loadavg)" | tee -a $out/$label.memstate.txt
rc=0
for i in $(seq 1 $n); do
  tr=0; (( i == 1 && trace == 1 )) && tr=1
  B0_URL=$url B0_LABEL=$label-$i B0_OUT=$out B0_TRACE=$tr B0_HEAP=1 ${B0_HEADED:+B0_HEADED=$B0_HEADED} caffeinate -dims $NODE $W/R6L/load_native.mjs > $out/$label-$i.stdout.log 2>&1 || rc=$?
  grep '"summary"' $out/$label-$i.stdout.log | tail -1
  sleep 3
done
kill $spid 2>/dev/null
echo "$(date '+%T') done rc=$rc swap: $(sysctl -n vm.swapusage)" | tee -a $out/$label.memstate.txt
exit $rc
