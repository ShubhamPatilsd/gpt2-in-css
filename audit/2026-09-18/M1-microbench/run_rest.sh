#!/bin/zsh
# Remaining phases after the host switched to battery at ~22:09Z (coordinator: note it, use --allow-battery).
set -u; cd "$(dirname "$0")"
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
LOG=results/run_all.log
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }
say "POWER: $(pmset -g batt | tr '\n' ' ' | cut -c1-120)"
for spec in "MB3|--filter ^mb3-" "MB4|--filter ^mb4-"; do
  name=${spec%%|*}; args=${spec#*|}
  say "START $name (battery, --allow-battery): $args"
  caffeinate -dims $NODE run.mjs --trials 3 --warmup 1 --allow-battery ${=args} >> "$LOG" 2>&1
  say "END $name rc=$?"
done
say "START COLD-INLINE (battery)"
caffeinate -dims $NODE run.mjs --trials 3 --warmup 0 --trigger inline --allow-battery --filter '^mb2-a-|^mb5-' --out results-cold --traces traces-cold >> "$LOG" 2>&1
say "END COLD-INLINE rc=$?"
say "ALL DONE"
