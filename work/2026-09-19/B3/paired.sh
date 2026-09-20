#!/bin/zsh
# B3 interleaved paired confirmation bench. Waits for B2's sequential queue to finish, then runs
#   ref, combined3, ref, R2F, ref, combined3, ref, R2F, ref, combined3, ref, R2F   (ref = bundles/combined)
# as 12 untraced runs through the unchanged B0/run_bench.sh harness (heap=1, mouseoff default, AC gate, quiet gate <=15 min
# then CONTENDED, stale-lock guard, 30 s power watchdog; the lock is held only while a run is active). Then B3/analyze.py.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; B=$W/B0
log() { echo "- $(date '+%F %T') $*" >> $W/B3.log.md; echo "$(date '+%T') $*"; }
b0lines=$(wc -l < $W/B0.log.md)
mirror() { local n=$(wc -l < $W/B0.log.md); if (( n > b0lines )); then { echo "  (mirrored from B0.log.md, written by B0/run_bench.sh; B3 labels are paired-*)"; tail -n +$((b0lines+1)) $W/B0.log.md | grep -F 'paired-' | sed 's/^/  /'; } >> $W/B3.log.md; b0lines=$n; fi; }
queue_alive() { pgrep -f 'B2/queue[3].sh' >/dev/null; }
rows_done() { local r=$W/bench/results.md; grep -q '^| R2F (' $r && grep -q '^| combined3 (' $r && grep -q '^| R2D (' $r; }
# ---- 1. wait for B2 (poll 60 s, up to 3 h) ----
start=$(date +%s); n=0
log "B3: started (pid $$); waiting for B2's queue (pgrep B2/queue3.sh empty OR results.md rows for R2F, combined3, R2D); poll 60 s, up to 3 h"
while queue_alive && ! rows_done; do
  (( $(date +%s) - start > 10800 )) && { log "B3: 3 h wait budget elapsed — proceeding anyway (queue3 still alive: $(pgrep -f 'B2/queue[3].sh' | tr '\n' ' '))"; break; }
  (( n % 10 == 0 )) && log "B3: waiting — queue3 alive=$(queue_alive && echo yes || echo no); rows: R2F=$(grep -c '^| R2F (' $W/bench/results.md) combined3=$(grep -c '^| combined3 (' $W/bench/results.md) R2D=$(grep -c '^| R2D (' $W/bench/results.md); last B0 line: $(tail -1 $W/B0.log.md | cut -c1-140)"
  sleep 60; n=$((n+1))
done
log "B3: wait over after $(( ($(date +%s) - start)/60 )) min — queue3 alive=$(queue_alive && echo yes || echo no); rows R2F=$(grep -c '^| R2F (' $W/bench/results.md) combined3=$(grep -c '^| combined3 (' $W/bench/results.md) R2D=$(grep -c '^| R2D (' $W/bench/results.md); load=$(sysctl -n vm.loadavg) batt='$(pmset -g batt | head -1)'"
# wait for any in-flight harness of another agent to finish its current run (run_bench's own lock poll handles the rest)
# ---- 2. the interleaved sequence ----
seq=( combined:paired-ref-1 combined3:paired-1 combined:paired-ref-2 R2F:paired-1 combined:paired-ref-3 combined3:paired-2 combined:paired-ref-4 R2F:paired-2 combined:paired-ref-5 combined3:paired-3 combined:paired-ref-6 R2F:paired-3 )
i=0
for step in $seq; do
  i=$((i+1)); bundle=${step%%:*}; label=${step#*:}
  [[ -f $W/bench/STOP ]] && { log "B3: bench/STOP present — stopping before step $i ($bundle/$label)"; break; }
  [[ -f $W/bundles/$bundle/index.html ]] || { log "B3: $bundle has no index.html — skipping step $i"; continue; }
  tries=0
  while true; do
    tries=$((tries+1))
    log "B3: step $i/12 $bundle/$label (try $tries) — calling run_bench.sh $bundle $label 1 0 600000"
    B0_FORCE=0 $B/run_bench.sh $bundle $label 1 0 600000 > $W/B3/step-$i.out 2>&1; rc=$?
    mirror
    if (( rc == 0 )); then log "B3: step $i $bundle/$label done rc=0: $(python3 $B/summarize_run.py $W/bench/runs/$bundle/$label.json --oneline 2>&1 | tail -1 | cut -c1-260)"; break; fi
    if (( rc == 4 )); then log "B3: step $i $bundle/$label invalid (battery mid-run) — redo"; continue; fi
    if (( rc == 2 )); then log "B3: step $i $bundle/$label blocked by disk guard — retry in 5 min"; sleep 300; continue; fi
    log "B3: step $i $bundle/$label rc=$rc (tail: $(tail -2 $W/B3/step-$i.out | tr '\n' ' ' | cut -c1-200))"
    (( tries >= 3 )) && { log "B3: step $i $bundle/$label FAILED 3x — continuing with the sequence"; break; }
    sleep 120
  done
done
# ---- 3. analysis ----
log "B3: sequence finished; running analyze.py"
python3 $W/B3/analyze.py > $W/B3/analyze.out 2>&1; arc=$?
log "B3: analyze.py rc=$arc → bench/paired.md, results.md paired rows (see B3/analyze.out)"
touch $W/B3/DONE
