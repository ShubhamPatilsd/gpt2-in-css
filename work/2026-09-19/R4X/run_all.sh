#!/bin/sh
# R4X combined fixture run: support probe + 3-arm scores hop (T timeline / M metric / C chain), one lock hold.
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
R=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4X
cd "$R" || exit 1
echo "[run_all] start $(date -u +%FT%TZ)"
caffeinate -dims $NODE probe/run_probe.mjs "$R/probe/support.html" "$R/probe/support-results.json" > results/probe.out 2>&1; echo "[run_all] probe exit $?"
caffeinate -dims $NODE /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F3/proto_run.mjs --trials 3 --warmup 1 --out results/scores.jsonl \
  pages/scores-T-timeline.json pages/scores-M-metric.json pages/scores-C-chain.json > results/scores.out 2>&1; echo "[run_all] scores exit $?"
echo "[run_all] done $(date -u +%FT%TZ)"
