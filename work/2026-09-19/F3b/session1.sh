#!/bin/zsh
# F3b Chrome session 1 (under run_chrome.sh): level-1 chain probes, then the 2-layer smoke bundles (chain vs timeline), traced.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
cd $W/F3b
mkdir -p results runs
echo "== probes $(date)" 
caffeinate -dims $NODE $W/F3/proto_run.mjs --trials 2 --warmup 1 --out results/probe-level1.jsonl pages/l1-D384.json pages/l1-D384-fixedsrc.json pages/l1-D128.json 2>&1 | tee results/probe-level1.txt
echo "== smoke-F3-2L $(date)"
F3B_POLL_MS=1000 ./serve_and_run.sh smoke-F3-2L smoke-F3-2L 1 2>&1 | tee results/smoke-F3-2L.txt
echo "== smoke-TL-2L $(date)"
F3B_POLL_MS=1000 ./serve_and_run.sh smoke-TL-2L smoke-TL-2L 1 2>&1 | tee results/smoke-TL-2L.txt
echo "== done $(date)"
