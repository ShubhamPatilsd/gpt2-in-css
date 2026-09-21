#!/bin/zsh
# R4M Chrome chain (each step takes CHROME.lock itself): combined6 correctness (8 tokens) -> finisher (READY on 8/8 + verify rc 0)
# -> combined6-c32 run 1 (Hello, vs R4C ref; READY on 32/32) -> run 2 (B0_PROMPT_TOKEN=40, vs R4P ref; not a READY gate)
# -> if run 2 mismatches: build combined6-c32-runs (default layout) and run 3 on prompt 40.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R4M
log() { echo "- $(date '+%F %T') [R4M chain] $*" >> $W/R4M.log.md; echo "$(date '+%T') $*"; }
log "chain start"
$R/run_correctness.sh combined6; log "correctness rc=$?"
$R/finish_after_run.sh; log "finisher: READY=$([[ -f $W/bundles/combined6/READY ]] && echo yes || echo no)"
$R/run_c32.sh combined6-c32 c32-run1 2400000 32; log "c32 run1 rc=$?"
s=$R/run-combined6-c32/c32-run1.summary.md
if grep -q '^ids 32/32 vs reference' $s 2>/dev/null; then echo "combined6-c32 READY $(date '+%F %T'): run 1 (Hello) $(sed -n 3p $s | cut -c1-40); $(grep '^total' $s)" > $W/bundles/combined6-c32/READY; log "READY created for combined6-c32 (run 1): $(grep '^total' $s)"; else log "run 1 NOT 32/32: $(sed -n 3,4p $s | tr '\n' ' ' | cut -c1-300) — no READY"; fi
B0_PROMPT_TOKEN=40 REF_JSON=$W/R4P/reference_ids_32_40.json $R/run_c32.sh combined6-c32 c32-run2-p40 2400000 32; log "c32 run2 (prompt 40) rc=$?"
s2=$R/run-combined6-c32/c32-run2-p40.summary.md
if grep -q '^ids 32/32 vs reference' $s2 2>/dev/null; then log "run 2 (prompt 40, widths) 32/32: $(grep '^total' $s2)"; echo "run 2 (prompt 40 'I', widths layout) also 32/32 vs R4P/reference_ids_32_40.json: $(grep '^total' $s2)" >> $W/bundles/combined6-c32/READY
else
  log "run 2 (prompt 40, widths) MISMATCH: $(sed -n 3,4p $s2 | tr '\n' ' ' | cut -c1-400) -> fallback run 3 with the default layout"
  VALUE_LAYOUT=runs NICE=0 $R/compile.sh $R/tools $W/bundles/combined6-c32-runs 32 > $R/compile-combined6-c32-runs.log 2>&1; log "built bundles/combined6-c32-runs rc=$?"
  python3 $R/compare_bundles.py $W/bundles/combined6-c32-runs $R/scratch/p32 > $R/compare-c32-runs.txt 2>&1
  B0_PROMPT_TOKEN=40 REF_JSON=$W/R4P/reference_ids_32_40.json $R/run_c32.sh combined6-c32-runs c32-run3-p40 2400000 32; log "c32 run3 (prompt 40, runs layout) rc=$?"
  s3=$R/run-combined6-c32-runs/c32-run3-p40.summary.md
  if grep -q '^ids 32/32 vs reference' $s3 2>/dev/null; then echo "combined6-c32-runs READY $(date '+%F %T'): run 3 (prompt 40 'I', default runs layout) 32/32 vs R4P/reference_ids_32_40.json; $(grep '^total' $s3)" > $W/bundles/combined6-c32-runs/READY; log "READY created for combined6-c32-runs (run 3): $(grep '^total' $s3)"; else log "run 3 NOT 32/32: $(sed -n 3,4p $s3 | tr '\n' ' ' | cut -c1-300)"; fi
fi
log "chain done"
touch $R/CHAIN-DONE
