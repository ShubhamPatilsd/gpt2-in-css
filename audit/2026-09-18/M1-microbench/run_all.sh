#!/bin/zsh
# Ordered driver requested by the coordinator (2026-09-18): wait for P2's parser, then
# MB2 -> MB5 -> MB1 -> MB3 -> MB4 -> (if <60 min) cold/random cross-check of MB2(a)+MB5.
# Budget guard: a phase is skipped if elapsed > BUDGET_MIN before it starts.
set -u
cd "$(dirname "$0")"
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
BUDGET_MIN=${BUDGET_MIN:-80}
LOG=results/run_all.log
mkdir -p results
T0=$(date +%s)
el() { echo $(( ($(date +%s) - T0) / 60 )); }
say() { echo "[$(date -u +%H:%M:%S) +$(el)m] $*" | tee -a "$LOG"; }

say "waiting for P2 parse_trace.py to finish (max 600 s)"
for i in {1..40}; do pgrep -f "python.* parse_trace.py" >/dev/null || break; sleep 15; done
pgrep -f "python.* parse_trace.py" >/dev/null && say "WARNING: parse_trace.py still running after 10 min; proceeding anyway"
if ps -axo command= | grep -E "Chrom(e|ium)" | grep -v grep >/dev/null; then say "WARNING: Chrome processes present at start"; fi
T0=$(date +%s)   # budget starts at first timed trial

phase() {  # name, extra args...
  local name=$1; shift
  if [ "$(el)" -ge "$BUDGET_MIN" ]; then say "SKIP $name (elapsed $(el) min >= budget $BUDGET_MIN)"; echo "$name" >> results/skipped.txt; return; fi
  say "START $name: $*"
  caffeinate -dims $NODE run.mjs "$@" >> "$LOG" 2>&1
  say "END $name rc=$?"
}

phase MB2 --trials 3 --warmup 1 --filter '^mb2-'
phase MB5 --trials 3 --warmup 1 --filter '^mb5-'
phase MB1 --trials 3 --warmup 1 --filter '^mb1'
phase MB3 --trials 3 --warmup 1 --filter '^mb3-'
phase MB4 --trials 3 --warmup 1 --filter '^mb4-'
if [ "$(el)" -lt 60 ]; then
  phase COLD-INLINE --trials 3 --warmup 0 --trigger inline --filter '^mb2-a-|^mb5-' --out results-cold --traces traces-cold
else
  say "SKIP COLD-INLINE (elapsed $(el) min >= 60)"; echo "COLD-INLINE" >> results/skipped.txt
fi
say "ALL DONE"
