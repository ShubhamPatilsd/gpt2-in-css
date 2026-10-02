#!/bin/zsh
# R7B (= R6X/c32_inner.sh + B0_SEED/B0_TEMP (select overrides) + B0_STOP_TOKEN (expected last captured token) + R7B/summarize.py)
# R6X (= R5X/c32_inner.sh + typed prompt): serves bundles/<bundle>, ONE passive run with R6X/bench_native.mjs (keyboard trigger, heap=1, trace=0),
# B0_TYPED_PROMPT typed into #tk-editor pre-Run (B0_TYPED_IDS asserted live), then summarize32.py vs REF_JSON (key freeRunningReference = the 32 winners).
# usage: [B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS='[7454,2402,257,640]' | B0_PROMPT_TOKEN=40] REF_JSON=... c32_inner.sh <bundle> <label> [cap_ms=2400000] [capacity=32]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; label=$2; capms=${3:-2400000}; cap=${4:-32}; out=$W/R7B/run-$bundle; dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle
[[ -d $dir ]] || { dir=$W/R7B/$bundle; rel=work/2026-09-19/R7B/$bundle; }  # R7B: smoke twins live under R7B/
[[ -d $dir ]] || { echo "no bundle $dir"; exit 2; }
mkdir -p $out; cp $dir/manifest.json $out/manifest.json
port=$((46000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/$rel/index.html"
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 2; done
echo "$(date '+%T') url=$url headed=${B0_HEADED:-0} viewport=${B0_VIEWPORT:-900x300} typed=${B0_TYPED_PROMPT:-none} ids=${B0_TYPED_IDS:-} prompt=${B0_PROMPT_TOKEN:-default} vm_stat: $(vm_stat | awk '/Pages free|Pages occupied by compressor|Pageouts/{printf "%s ", $0}' | tr -s ' ') swap: $(sysctl -n vm.swapusage)" | tee $out/$label.memstate.txt
B0_SEED=${B0_SEED:-} B0_TEMP=${B0_TEMP:-} B0_STOP_TOKEN=${B0_STOP_TOKEN:-} B0_TYPED_PROMPT=${B0_TYPED_PROMPT:-} B0_TYPED_IDS=${B0_TYPED_IDS:-} B0_PROMPT_SLOTS=4 B0_PROMPT_TOKEN=${B0_PROMPT_TOKEN:-} B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=1 B0_TRACE=0 B0_CAP_MS=$capms B0_CAPACITY=$cap B0_TRIGGER=keyboard B0_INVALIDATION=0 \
  caffeinate -dims $NODE $W/R7B/bench_native.mjs > $out/$label.stdout.log 2>&1
rc=$?
kill $spid 2>/dev/null
echo "$(date '+%T') node rc=$rc vm_stat after: $(vm_stat | awk '/Pages free|Pages occupied by compressor|Pageouts/{printf "%s ", $0}' | tr -s ' ') swap: $(sysctl -n vm.swapusage)" | tee -a $out/$label.memstate.txt
python3 $W/R7B/summarize.py $out/$label.json ${REF_JSON:?} > $out/$label.summary.md 2>&1 && head -5 $out/$label.summary.md
touch $out/DONE-$label
exit $rc
