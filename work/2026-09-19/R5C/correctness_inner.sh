#!/bin/zsh
# serves bundles/<bundle>, runs R4M's correctness_run.mjs (passive, 5 s poll, heap flag, R4D per-head V readback), then verify_browser_gpt2_runtime.py
# usage: correctness_inner.sh <bundle>   -> R5C/run-<bundle>/
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; out=$W/R5C/run-$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out; cp $dir/manifest.json $out/manifest.json
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') url=$url"
( while kill -0 $$ 2>/dev/null; do echo "$(date '+%T') rss=$(ps -o rss= -p $(pgrep -f '^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--type=renderer' 2>/dev/null | head -1) 2>/dev/null | tr -d ' ') load=$(sysctl -n vm.loadavg | cut -c3-20) $(sysctl -n vm.swapusage | cut -c1-50) free=$(df -g $W | awk 'NR==2{print $4}')G" >> $out/rss.log; sleep 5; done ) 2>/dev/null & rpid=$!
F4_URL=$url F4_OUT=$out F4_CAPACITY=8 F4_CAP_MS=1200000 caffeinate -dims $NODE $W/R5C/correctness_run.mjs > $out/harness.log 2>&1
rc=$?
kill $spid $rpid 2>/dev/null
grep '"final"' $out/harness.log | cut -c1-500
cd $W/R5C && PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
echo "verify rc=$? $(tail -c 700 $out/verify.log | tr '\n' ' ')"
touch $out/DONE
exit $rc
