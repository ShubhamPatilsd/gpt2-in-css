#!/bin/zsh
# R6X: serves bundles/<bundle>, ONE passive 8-token run with R4M's correctness_run.mjs (5 s poll, heap flag), 1 Hz renderer RSS sampler,
# then verify_browser_gpt2_runtime.py with the MERGED tools (R4M's verify_wrapper.py fallback if the V-half readback is null). usage: correctness_inner.sh <bundle>
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; out=$W/R6X/run-$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out; cp $dir/manifest.json $out/manifest.json
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') url=$url load=$(sysctl -n vm.loadavg) swap=$(sysctl -n vm.swapusage)"
# renderer RSS sampler (1 Hz, absolute timestamps): max RSS over Chrome helper (renderer) processes
( while true; do echo "$(date '+%s') $(ps -Ao rss,command | grep -E 'Google Chrome Helper \(Renderer\)|Google Chrome Helper$' | grep -v grep | awk '{if($1>m)m=$1} END{print int(m/1024)}')"; sleep 1; done ) > $out/rss-renderer.log 2>&1 & rpid=$!
F4_URL=$url F4_OUT=$out F4_CAPACITY=8 F4_CAP_MS=1200000 caffeinate -dims $NODE $W/R6X/correctness_run.mjs > $out/harness.log 2>&1
rc=$?
kill $rpid $spid 2>/dev/null
grep '"final"' $out/harness.log | cut -c1-600
cd $W/R6X && OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $out > $out/verify.log 2>&1
vrc=$?
if (( vrc != 0 )) && grep -q "null" $out/verification-vectors.json 2>/dev/null; then
  echo "verify rc=$vrc with nulls in the vectors -> R4M verify_wrapper.py (NaN the V half, K-half errors)"
  cd $W/R6X && OPENBLAS_NUM_THREADS=1 PYTHONPATH=tools uv run --with numpy --with fonttools --with pillow --with brotli python verify_wrapper.py $out > $out/verify-wrapper.log 2>&1; vrc=$?
fi
echo "verify rc=$vrc $(tail -c 700 $out/verify.log | tr '\n' ' ')"
echo "RSS renderer peak MB: $(awk '$2>m{m=$2} END{print m}' $out/rss-renderer.log)"
touch $out/DONE
exit $rc
