#!/bin/zsh
# R6X: serve a bundle (bundles/<b> or R6X/<b>) and run ordering.mjs. usage: ordering_inner.sh <bundle> <label> [zoom-steps=0] [tokens=5]
set -u; ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19; NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; label=$2; zoom=${3:-0}; tokens=${4:-5}; out=$W/R6X/runs/ordering-$bundle-$label; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
[[ -d $dir ]] || { dir=$W/R6X/$bundle; rel=work/2026-09-19/R6X/$bundle; }
mkdir -p $out; port=$((47000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"; for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
R6X_URL=$url R6X_OUT=$out R6X_TYPED="${R6X_TYPED:-Shubham was}" R6X_ZOOM_STEPS=$zoom R6X_TOKENS=$tokens caffeinate -dims $NODE $W/R6X/ordering.mjs > $out/harness.log 2>&1; rc=$?
kill $spid 2>/dev/null; grep -h '"typed"\|"after-click"\|"winners"' $out/harness.log | cut -c1-400; exit $rc
