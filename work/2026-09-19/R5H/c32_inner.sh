#!/bin/zsh
# serves bundles/<bundle>, ONE passive 32-token run with R4M's bench_native.mjs (keyboard trigger, heap=1, trace=0, prompt knob), then summarize32.py
# usage: [B0_PROMPT_TOKEN=40 REF_JSON=...] c32_inner.sh <bundle> <label> [cap_ms=2400000]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; label=$2; capms=${3:-2400000}; out=$W/R5H/run-$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
mkdir -p $out; cp $dir/manifest.json $out/manifest.json
port=$((46000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') url=$url prompt=${B0_PROMPT_TOKEN:-default} vm_stat: $(vm_stat | awk '/Pages free|Pages inactive|Pages speculative|Pages occupied by compressor|Pageouts/{printf "%s %s ", $0, ""}' | tr -s ' ') swap: $(sysctl -n vm.swapusage)" | tee $out/$label.memstate.txt
B0_PROMPT_TOKEN=${B0_PROMPT_TOKEN:-} B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=1 B0_TRACE=0 B0_CAP_MS=$capms B0_CAPACITY=32 B0_TRIGGER=keyboard B0_INVALIDATION=0 \
  caffeinate -dims $NODE $W/R5H/bench_native.mjs > $out/$label.stdout.log 2>&1
rc=$?
kill $spid 2>/dev/null
echo "$(date '+%T') node rc=$rc vm_stat after: $(vm_stat | awk '/Pages free|Pages occupied by compressor|Pageouts/{printf "%s ", $0}' | tr -s ' ') swap: $(sysctl -n vm.swapusage)" | tee -a $out/$label.memstate.txt
python3 $W/R5H/summarize32.py $out/$label.json ${REF_JSON:-$W/R4P/reference_ids_32_40.json} > $out/$label.summary.md 2>&1 && head -5 $out/$label.summary.md
touch $out/DONE
exit $rc
