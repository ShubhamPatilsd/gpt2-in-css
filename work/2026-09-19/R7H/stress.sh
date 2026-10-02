#!/bin/zsh
# R7H stress test: 6 `yes > /dev/null` busy processes (our own, killed on exit) while the 2-layer smoke twins run 8 tokens each,
# guard OFF and ON, 2 repeats (typed "Shubham was", 2-layer reference). usage: stress.sh   (run under with_lock.sh)
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7H
pids=(); for _ in 1 2 3 4 5 6; do yes > /dev/null & pids+=($!); done
trap 'kill ${pids[@]} 2>/dev/null; echo "$(date +%T) busy loops killed"' EXIT INT TERM
sleep 5; echo "$(date +%T) load with 6 yes: $(sysctl -n vm.loadavg)"
for rep in 1 2; do for t in off on; do
  B0_TYPED_PROMPT="Shubham was" B0_TYPED_IDS='[2484,549,2763,373]' REF_JSON=$W/R6X/reference_ids_shubham_was_2layers.json \
    $R/inner.sh twin-smoke-2L-$t stress-$t-$rep 900000 8 | tail -3
  echo "$(date +%T) load: $(sysctl -n vm.loadavg)"
done; done
