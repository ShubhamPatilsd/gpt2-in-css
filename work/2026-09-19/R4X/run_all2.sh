#!/bin/sh
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
R=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4X
cd "$R" || exit 1
echo "[run_all2] start $(date -u +%FT%TZ)"
caffeinate -dims $NODE probe/run_probe.mjs "$R/probe/support.html" "$R/probe/support-results-2.json" > results/probe-2.out 2>&1; echo "[run_all2] probe exit $?"
caffeinate -dims $NODE /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F3/proto_run.mjs --trials 3 --warmup 1 --out results/scores-2.jsonl \
  pages/scores-T-timeline.json pages/scores-M-metric.json pages/scores-C-chain.json > results/scores-2.out 2>&1; echo "[run_all2] scores exit $?"
echo "[run_all2] done $(date -u +%FT%TZ)"
