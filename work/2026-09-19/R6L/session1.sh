#!/bin/zsh
# R6L session 1: load-time attribution + first fix. baseline ×3 (run 1 traced), hidebody ×2 (run 1 traced), bodylink ×3 (run 1 traced).
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
cd $W && python3 R6L/postprocess.py bundles/combined8-c32 bundles/R6L-bodylink && python3 R6L/postprocess.py bundles/combined8-c32 bundles/R6L-hidebody --no-body-link  # twins regenerated (deleted at the end to save disk)
$W/R6L/load_inner.sh combined8-c32 base 3 1
$W/R6L/load_inner.sh R6L-hidebody hide 2 1
$W/R6L/load_inner.sh R6L-bodylink link 3 1
python3 $W/R6L/summarize_loads.py > /dev/null 2>&1; echo "- $(date "+%F %T") session1 loads done → R6L/loads/SUMMARY.md" >> $W/R6L.log.md
rm -rf $W/bundles/R6L-bodylink $W/bundles/R6L-hidebody
touch $W/R6L/loads/SESSION1-DONE
