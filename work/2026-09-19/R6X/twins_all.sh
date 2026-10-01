#!/bin/zsh
# R6X offline twins, ONE build at a time, each deleted after its checks (disk). Logs: R6X/logs/compare-*.log, offline_check-*.log
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W
OFF_P="R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0"; OFF_V="R6V_PROGRESS_UI=0"
echo "### $(date '+%T') re-compare p32-alloff with the R6X comparer"; python3 R6X/compare_bundles.py R6X/twin-p32-alloff bundles/combined8-c32 | tee R6X/logs/compare-p32-alloff.log | cut -c1-400; rm -rf R6X/twin-p32-alloff
echo "### $(date '+%T') p8-alloff"; R6X/twin.sh p8-alloff 8 bundles/combined8 ${=OFF_P} ${=OFF_V} | cut -c1-400; rm -rf R6X/twin-p8-alloff
echo "### $(date '+%T') p32-r6ponly"; R6X/twin.sh p32-r6ponly 32 bundles/combined8-c32-prompt ${=OFF_V} | cut -c1-400
echo "### $(date '+%T') R6V/offline_check.py demo-c32 vs twin-p32-r6ponly (same depth)"; python3 R6V/offline_check.py bundles/demo-c32 R6X/twin-p32-r6ponly | tee R6X/logs/offline_check-r6v-demo-c32.log | cut -c1-600; rm -rf R6X/twin-p32-r6ponly
echo "### $(date '+%T') p32-r6vonly"; R6X/twin.sh p32-r6vonly 32 bundles/combined8-c32-ui ${=OFF_P} | cut -c1-400; rm -rf R6X/twin-p32-r6vonly
echo "### $(date '+%T') p8-r6ponly"; R6X/twin.sh p8-r6ponly 8 bundles/combined8-prompt ${=OFF_V} | cut -c1-400
echo "### $(date '+%T') R6V/offline_check.py demo-8 vs twin-p8-r6ponly"; python3 R6V/offline_check.py bundles/demo-8 R6X/twin-p8-r6ponly | tee R6X/logs/offline_check-r6v-demo-8.log | cut -c1-600; rm -rf R6X/twin-p8-r6ponly
echo "### $(date '+%T') p8-r6vonly"; R6X/twin.sh p8-r6vonly 8 bundles/combined8-ui ${=OFF_P} | cut -c1-400; rm -rf R6X/twin-p8-r6vonly
echo "### $(date '+%T') TWINS DONE"; touch R6X/TWINS-DONE
