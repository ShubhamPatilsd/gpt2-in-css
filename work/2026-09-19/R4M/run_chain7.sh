#!/bin/zsh
# R4M chain 7 (coordinator 01:4x): after CHAIN-DONE: combined7 correctness (8 tokens; READY on 8/8 + verify rc 0) -> combined7-c32 32-token run
# with prompt 40 if combined6-c32's run 2 (prompt 40) matched 32/32, else the Hello prompt vs R4C's reference; READY on 32/32. Marker R4M/CHAIN7-DONE.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R4M
log() { echo "- $(date '+%F %T') [R4M chain7] $*" >> $W/R4M.log.md; echo "$(date '+%T') $*"; }
while [[ ! -f $R/CHAIN-DONE ]]; do sleep 30; done
log "chain7 start (CHAIN-DONE seen)"
$R/run_correctness.sh combined7; log "combined7 correctness rc=$?"
# verify may have crashed on the V half if the harness copy's per-head fix did not cover it; the wrapper recomputes rc from the unchanged verify
if ! grep -q "\[R4M correctness/combined7\] verify rc=0" $W/R4M.log.md; then
  (cd $R && OPENBLAS_NUM_THREADS=1 PYTHONPATH=tools7 uv run --with numpy --with fonttools --with pillow --with brotli python verify_wrapper.py run-combined7 > run-combined7/verify-wrapper.log 2>&1); wrc=$?
  echo "- $(date '+%F %T') [R4M correctness/combined7] verify rc=$wrc (via R4M/verify_wrapper.py) $(grep -v Traceback run-combined7/verify-wrapper.log | grep tokens | tail -c 700 | tr '\n' ' ')" >> $W/R4M.log.md
fi
$R/finish_after_run7.sh combined7; log "finisher7: READY=$([[ -f $W/bundles/combined7/READY ]] && echo yes || echo no)"
# coordinator 01:5x: combined7-c32 (now WITHOUT R4S) runs prompt 40 first (the demo), then a Hello run vs the R4C reference for comparability with c32c/combined6-c32.
log "combined7-c32 run A: prompt 40 vs R4P/reference_ids_32_40.json"
B0_PROMPT_TOKEN=40 REF_JSON=$W/R4P/reference_ids_32_40.json $R/run_c32.sh combined7-c32 c32-runA-p40 2400000 32; log "combined7-c32 run A rc=$?"
sA=$R/run-combined7-c32/c32-runA-p40.summary.md
if grep -q '^ids 32/32 vs reference' $sA 2>/dev/null; then echo "combined7-c32 READY $(date '+%F %T'): run A (prompt 40 'I', no R4S, widths, R4T 64) 32/32 vs R4P/reference_ids_32_40.json; $(grep '^total' $sA)" > $W/bundles/combined7-c32/READY; log "READY created for combined7-c32 (run A): $(grep '^total' $sA)"; else log "combined7-c32 run A NOT 32/32: $(sed -n 3,4p $sA | tr '\n' ' ' | cut -c1-300) — no READY"; fi
log "combined7-c32 run B: Hello vs R4C/reference_ids_32.json"
REF_JSON=$W/R4C/reference_ids_32.json $R/run_c32.sh combined7-c32 c32-runB-hello 2400000 32; log "combined7-c32 run B rc=$?"
sB=$R/run-combined7-c32/c32-runB-hello.summary.md
if grep -q '^ids 32/32 vs reference' $sB 2>/dev/null; then log "run B (Hello) 32/32: $(grep '^total' $sB)"; [[ -f $W/bundles/combined7-c32/READY ]] && echo "run B (Hello, default prompt) also 32/32 vs R4C/reference_ids_32.json: $(grep '^total' $sB)" >> $W/bundles/combined7-c32/READY; else log "run B (Hello) NOT 32/32: $(sed -n 3,4p $sB | tr '\n' ' ' | cut -c1-300)"; fi
log "chain7 done"; touch $R/CHAIN7-DONE
