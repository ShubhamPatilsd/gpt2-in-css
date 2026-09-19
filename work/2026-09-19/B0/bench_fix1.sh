#!/bin/zsh
# Fix 1 arms on the baseline bundle: interleaved heap=1 / heap=0 untraced runs x3, then one light trace each; aggregate both arms.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; B=$W/B0; out=$W/bench/runs/baseline
for i in 1 2 3; do
  $B/run_bench.sh baseline heap10-u$i 1 0 600000
  $B/run_bench.sh baseline noheap-u$i 0 0 600000
done
$B/run_bench.sh baseline heap10-t1 1 1 660000
[[ -f $out/heap10-t1-summary.json ]] || B0_INVALIDATION=1 $B/run_bench.sh baseline heap10-t1 1 1 660000
$B/run_bench.sh baseline noheap-t1 0 1 660000
[[ -f $out/noheap-t1-summary.json ]] || B0_INVALIDATION=1 $B/run_bench.sh baseline noheap-t1 0 1 660000
python3 $B/aggregate.py "baseline heap=1 (--heap-growing-percent=10, as Codex ran)" $W/bench/baseline-heap10.md $out/heap10-u1.json $out/heap10-u2.json $out/heap10-u3.json --trace $out/heap10-t1-summary.json --notes "v2 rebuild; Fix 1 arm A" >> $W/bench/results.md
python3 $B/aggregate.py "baseline heap=0 (no GC flag)" $W/bench/baseline-noheap.md $out/noheap-u1.json $out/noheap-u2.json $out/noheap-u3.json --trace $out/noheap-t1-summary.json --notes "v2 rebuild; Fix 1 arm B" >> $W/bench/results.md
echo "- $(date '+%F %T') bench_fix1 done" >> $W/B0.log.md
