#!/bin/zsh
# Full protocol for one bundle: 3 untraced + 1 light trace, then aggregate into bench/results.md + bench/<bundle>.md
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; B=$W/B0
name=$1; heap=${2:-1}; cap=${3:-600000}
out=$W/bench/runs/$name
# B0_TAG (optional): re-bench a bundle under a new config without touching its earlier runs: labels <name>-<tag>-u1.., row "<name> (<tag>)", detail bench/<name>-<tag>.md
tag=${B0_TAG:-}; lab=$name${tag:+-$tag}; rowname="$name (heap=$heap${tag:+, $tag})"; [[ -n $tag ]] && rowname="$name ($tag)"; detail=$W/bench/$lab.md
mo=${B0_MOUSEOFF:-off}; case $mo in 0) mnote="config: heap=$heap, mouse left on #run (legacy)";; corner) mnote="config: heap=$heap, mouseoff (pointer parked on blank body corner 890,290 after the Run click)";; *) mnote="config: heap=$heap, mouseoff (pointer parked off-viewport -50,-50 after the Run click)";; esac
notes="$mnote${B0_NOTES:+; $B0_NOTES}"
if [[ $name != pinned && ! -f $W/bundles/$name/index.html ]]; then echo "- $(date '+%F %T') bench_bundle: $name has no index.html, skipping" >> $W/B0.log.md; exit 1; fi
run() { while true; do $B/run_bench.sh "$@"; rc=$?; (( rc == 4 )) && { echo "- $(date '+%F %T') bench_bundle: $2 invalid (battery) — will redo from scratch" >> $W/B0.log.md; continue; }; return $rc; done; }
for i in 1 2 3; do run $name $lab-u$i $heap 0 $cap; rc=$?; (( rc == 2 )) && { echo "- $(date '+%F %T') bench_bundle: $name blocked by disk guard — will retry later" >> $W/B0.log.md; exit 2; }; done
run $name $lab-t1 $heap 1 $cap; rc=$?; (( rc == 2 )) && exit 2
if [[ ! -f $out/$lab-t1-summary.json ]]; then
  echo "- $(date '+%F %T') bench_bundle: light trace of $name failed; retrying with full categories (invalidationTracking)" >> $W/B0.log.md
  B0_INVALIDATION=1 run $name $lab-t1 $heap 1 $cap
fi
row=$(python3 $B/aggregate.py "$rowname" $detail $out/$lab-u1.json $out/$lab-u2.json $out/$lab-u3.json --trace $out/$lab-t1-summary.json --notes "$notes")
echo "$row" >> $W/bench/results.md
echo "- $(date '+%F %T') bench_bundle: $lab done → $row" >> $W/B0.log.md
