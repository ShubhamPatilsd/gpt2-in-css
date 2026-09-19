#!/bin/zsh
# usage: serve_and_run.sh <bundle-name> <out-subdir> [trace 0/1]  -- serves the bundle, runs run_bundle.mjs, then verify_browser_gpt2_runtime.py
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; out=$W/F3b/runs/$2; trace=${3:-0}
dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out; cp $dir/manifest.json $out/manifest.json
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 &
spid=$!
sleep 2
url="http://127.0.0.1:$port/$rel/index.html"
curl -s -o /dev/null -w "%{http_code}\n" "$url" | grep -q 200 || { echo "server did not serve $url"; kill $spid; exit 4; }
F3B_URL=$url F3B_OUT=$out F3B_TRACE=$trace F3B_POLL_MS=${F3B_POLL_MS:-5000} F3B_CAP_MS=${F3B_CAP_MS:-1200000} caffeinate -dims $NODE $W/F3b/run_bundle.mjs > $out/harness.log 2>&1
rc=$?
kill $spid 2>/dev/null
grep '"final"' $out/harness.log | cut -c1-600
cd $W/F3b && OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
echo "verify rc=$? $(tail -c 700 $out/verify.log | tr '\n' ' ')"
exit $rc
