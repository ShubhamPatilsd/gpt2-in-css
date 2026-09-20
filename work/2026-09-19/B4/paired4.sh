#!/bin/zsh
# B4 round-3 interleaved PAIRED bench queue (2026-09-20). ref = bundles/R2F (current best, 23.6 s/token).
# Ordering gate: do NOT bench until B3/DONE exists AND (R3A.md has a "Results"/"Summary" heading OR 45 min passed since B3/DONE).
# Then for each READY candidate among bundles/R3F, bundles/R3L (as they appear; poll 60 s) and bundles/combined4 (last, 4 pairs):
#   ref, cand, ref, cand, ref, cand   (3 pairs; combined4: 4 pairs) as untraced runs through the UNCHANGED B0/run_bench.sh harness
#   (heap=1, mouseoff default, passive, AC required, disk >= 1.5 GB, quiet gate load<3 up to 15 min then CONTENDED, 30 s power
#   watchdog, stale-lock guard; CHROME.lock taken per run by run_bench.sh and released as soon as Chrome exits).
# Labels: bench/runs/R2F/paired4-ref-<cand>-<k>.json and bench/runs/<cand>/paired4-<k>.json. After each candidate: B4/analyze4.py
# → row "<cand> (paired vs R2F)" in bench/results.md + per-run table in bench/paired-round3.md. Progress → B4.md after every run.
# Budget: B4_BUDGET_S (default 5 h) from start, or bench/STOP.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; B=$W/B0; D=$W/B4
BUDGET=${B4_BUDGET_S:-18000}
start=$(date +%s)
log() { echo "- $(date '+%F %T') $*" >> $W/B4.log.md; echo "$(date '+%T') $*"; }
prog() { echo "- $(date '+%F %T') $*" >> $W/B4.md; }
b0lines=$(wc -l < $W/B0.log.md)
mirror() { local n=$(wc -l < $W/B0.log.md); if (( n > b0lines )); then { echo "  (mirrored from B0.log.md, written by B0/run_bench.sh; B4 labels are paired4-*)"; tail -n +$((b0lines+1)) $W/B0.log.md | grep -F 'paired4-' | sed 's/^/  /'; } >> $W/B4.log.md; b0lines=$n; fi; }
budget_ok() { (( $(date +%s) - start < BUDGET )); }
stop_req() { [[ -f $W/bench/STOP ]]; }
r3a_done() { [[ -f $W/R3A.md ]] && grep -qiE '^#+ .*(Results|Summary)' $W/R3A.md; }
touch $D/benched4.txt
# ---- 1. ordering gate ----
log "B4: started (pid $$, budget ${BUDGET}s → ends $(date -v+${BUDGET}S '+%F %T')); waiting for B3/DONE AND (R3A.md Results/Summary OR 45 min after B3/DONE); poll 60 s"
n=0
while true; do
  stop_req && { log "B4: bench/STOP present during the ordering gate — exiting"; prog "STOP during ordering gate; nothing benched."; exit 0; }
  budget_ok || { log "B4: budget elapsed during the ordering gate — exiting (nothing benched)"; prog "Budget elapsed during ordering gate; nothing benched."; exit 0; }
  if [[ -f $W/B3/DONE ]]; then
    done_at=$(stat -f %m $W/B3/DONE); since=$(( $(date +%s) - done_at ))
    if r3a_done; then log "B4: gate open — B3/DONE ($((since/60)) min ago) and R3A.md has a Results/Summary heading"; break; fi
    if (( since > 2700 )); then log "B4: gate open — B3/DONE $((since/60)) min ago and R3A.md still has no Results/Summary heading (45 min grace elapsed)"; break; fi
  fi
  (( n % 10 == 0 )) && log "B4: gate wait — B3/DONE=$([[ -f $W/B3/DONE ]] && echo yes || echo no) R3A.md=$([[ -f $W/R3A.md ]] && echo present || echo absent) r3a_results=$(r3a_done && echo yes || echo no) READY: $(for r in $W/bundles/*/READY(N); do echo -n "${r:h:t} "; done); B3 last: $(grep -F 'B3:' $W/B3.log.md | tail -1 | cut -c1-120)"
  sleep 60; n=$((n+1))
done
prog "Ordering gate opened at $(date '+%F %T') (B3/DONE present; R3A Results/Summary: $(r3a_done && echo yes || echo 'no — 45 min grace')). Bench starts."
# ---- 2. one run through the harness (idempotent: run_bench skips complete labels when B0_FORCE=0) ----
run_step() {  # run_step <bundle> <label> <stepdesc>
  local bundle=$1 label=$2 desc=$3 tries=0 rc
  while true; do
    tries=$((tries+1))
    log "B4: $desc — run_bench.sh $bundle $label 1 0 600000 (try $tries)"
    B0_FORCE=0 $B/run_bench.sh $bundle $label 1 0 600000 > $D/$bundle-$label.out 2>&1; rc=$?
    mirror
    if (( rc == 0 )); then
      local one=$(python3 $B/summarize_run.py $W/bench/runs/$bundle/$label.json --oneline 2>&1 | tail -1 | cut -c1-260)
      log "B4: $desc done rc=0: $one"; prog "$desc → \`$bundle/$label\`: $one"; return 0; fi
    if (( rc == 4 )); then log "B4: $desc invalid (battery mid-run) — redo"; continue; fi
    if (( rc == 2 )); then log "B4: $desc blocked by disk guard — retry in 5 min"; sleep 300; continue; fi
    log "B4: $desc rc=$rc (tail: $(tail -2 $D/$bundle-$label.out | tr '\n' ' ' | cut -c1-200))"
    (( tries >= 3 )) && { log "B4: $desc FAILED 3x — giving up on this run"; prog "$desc FAILED 3x (rc=$rc) — see B4/$bundle-$label.out"; return 1; }
    sleep 120
  done
}
# ---- 3. one candidate: interleaved pairs, then analysis ----
bench_cand() {
  local cand=$1 np=3 k; [[ $cand == combined4 ]] && np=4
  log "B4: candidate $cand — $np pairs (ref R2F first in each pair); READY: $(cat $W/bundles/$cand/READY 2>/dev/null | head -1 | cut -c1-120)"
  prog ""; prog "### $cand — started $(date '+%F %T'), $np pairs (ref, cand)×$np"
  for k in $(seq 1 $np); do
    stop_req && { log "B4: bench/STOP present — stopping $cand before pair $k"; prog "STOP before pair $k of $cand"; break; }
    budget_ok || { log "B4: budget elapsed — stopping $cand before pair $k"; prog "Budget elapsed before pair $k of $cand"; break; }
    [[ -f $W/bundles/R2F/index.html ]] || { log "B4: bundles/R2F/index.html missing — cannot run the reference; abort"; return 1; }
    run_step R2F paired4-ref-$cand-$k "$cand pair $k/$np ref"
    run_step $cand paired4-$k "$cand pair $k/$np cand"
  done
  log "B4: $cand — running analyze4.py"
  python3 $D/analyze4.py $cand > $D/analyze-$cand.out 2>&1; local arc=$?
  log "B4: analyze4.py $cand rc=$arc → bench/paired-round3.md + results.md row (B4/analyze-$cand.out)"
  echo $cand >> $D/benched4.txt
  { echo ""; echo "#### $cand — result ($(date '+%F %T'))"; echo ""; grep -E "^\|(---| bundle \|)" $W/bench/results.md; grep -F "| $cand (paired vs R2F) |" $W/bench/results.md | tail -1; echo "";
    sed -n "/^\*\*$cand — /,/^$/p" $W/bench/paired-round3.md; echo "Per-run table: \`bench/paired-round3.md\`; runs: \`bench/runs/R2F/paired4-ref-$cand-*\`, \`bench/runs/$cand/paired4-*\`."; } >> $W/B4.md
}
# ---- 4. the queue: R3F/R3L as they become READY, combined4 last ----
benched() { grep -qx "$1" $D/benched4.txt; }
n=0
while true; do
  stop_req && { log "B4: bench/STOP present — exiting"; prog "STOP — queue exited $(date '+%F %T')"; break; }
  budget_ok || { log "B4: budget elapsed — exiting"; prog "Budget elapsed — queue exited $(date '+%F %T')"; break; }
  picked=""
  for c in R3R R3L R3P R3F; do [[ -f $W/bundles/$c/READY && -f $W/bundles/$c/index.html ]] && ! benched $c && { picked=$c; break; }; done
  if [[ -z $picked && -f $W/bundles/combined4/READY && -f $W/bundles/combined4/index.html ]] && ! benched combined4; then picked=combined4; fi
  if [[ -n $picked ]]; then bench_cand $picked; continue; fi
  if benched R3R && benched R3L && benched R3P && benched R3F && benched combined4; then log "B4: all candidates benched — exiting"; prog "All candidates benched — queue exited $(date '+%F %T')"; break; fi
  (( n % 10 == 0 )) && log "B4: idle — waiting for READY candidates (benched: $(tr '\n' ' ' < $D/benched4.txt); READY: $(for r in $W/bundles/*/READY(N); do echo -n "${r:h:t} "; done))"
  sleep 60; n=$((n+1))
done
touch $D/DONE
log "B4: DONE"
