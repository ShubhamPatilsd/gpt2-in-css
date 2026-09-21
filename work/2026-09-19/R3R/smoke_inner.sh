#!/bin/zsh
# serves bundles/<bundle>, runs run_bundle.mjs (light trace), writes runs/<out>/; usage: smoke_inner.sh <bundle> <out>
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; out=$W/R3R/runs/$2; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out; cp $dir/manifest.json $out/manifest.json
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
R2F_URL=$url R2F_OUT=$out R2F_TRACE=${TRACE:-1} R2F_POLL_MS=2000 R2F_CAP_MS=${CAP_MS:-240000} caffeinate -dims $NODE $W/R3R/run_bundle.mjs > $out/harness.log 2>&1
rc=$?
kill $spid 2>/dev/null
grep '"final"' $out/harness.log | cut -c1-500
exit $rc
