#!/bin/zsh
# serves bundles/<bundle>, runs F4's correctness_run.mjs (passive, 5 s poll, heap flag), then verify_browser_gpt2_runtime.py; usage: correctness_inner.sh <bundle>
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; out=$W/R3F/run-$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out; cp $dir/manifest.json $out/manifest.json
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') url=$url"
F4_URL=$url F4_OUT=$out F4_CAPACITY=8 F4_CAP_MS=1200000 caffeinate -dims $NODE $W/R3F/correctness_run.mjs > $out/harness.log 2>&1
rc=$?
kill $spid 2>/dev/null
grep '"final"' $out/harness.log | cut -c1-500
cd $W/R3F && PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
echo "verify rc=$? $(tail -c 700 $out/verify.log | tr '\n' ' ')"
touch $out/DONE
exit $rc
