#!/bin/zsh
# R4M chain C (coordinator 02:5x): after run_chain7.sh finishes (run B), run C = bundles/combined4-c32c with B0_PROMPT_TOKEN=40 vs R4P/reference_ids_32_40.json
# (same protocol; summary R4M/run-combined4-c32c/c32c-runC-p40.summary.md); append the verdict to bundles/combined4-c32c/READY on 32/32. Then the final CHAIN7-DONE.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R4M
log() { echo "- $(date '+%F %T') [R4M chainC] $*" >> $W/R4M.log.md; echo "$(date '+%T') $*"; }
while [[ ! -f $R/CHAIN7-DONE ]]; do sleep 20; done
mv $R/CHAIN7-DONE $R/CHAIN7-AB-DONE; log "chain C start (runs A/B done)"
B0_PROMPT_TOKEN=40 REF_JSON=$W/R4P/reference_ids_32_40.json $R/run_c32.sh combined4-c32c c32c-runC-p40 2400000 32; log "combined4-c32c run C (prompt 40) rc=$?"
s=$R/run-combined4-c32c/c32c-runC-p40.summary.md
if grep -q '^ids 32/32 vs reference' $s 2>/dev/null; then echo "R4M run C $(date '+%F %T'): prompt 40 'I' (B0_PROMPT_TOKEN=40) 32/32 vs R4P/reference_ids_32_40.json; $(grep '^total' $s) (machine in active user use, load 8-30 — absolute times inflated; R4M/run-combined4-c32c/c32c-runC-p40.summary.md)" >> $W/bundles/combined4-c32c/READY; log "run C 32/32 — verdict appended to bundles/combined4-c32c/READY: $(grep '^total' $s)"; else log "run C NOT 32/32: $(sed -n 3,4p $s | tr '\n' ' ' | cut -c1-300) — READY untouched"; fi
log "chain C done"; touch $R/CHAIN7-DONE
