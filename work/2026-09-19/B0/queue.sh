#!/bin/zsh
# B0 bench queue: every 60 s, bench any work/2026-09-19/bundles/*/READY not yet benched. Stops on bench/STOP or after 5 h.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
B=$W/B0; mkdir -p $W/bench/runs
HEAP=${B0_QUEUE_HEAP:-1}
start=$(date +%s)
touch $W/bench/benched.txt
while true; do
  [[ -f $W/bench/STOP ]] && { echo "- $(date '+%F %T') queue: STOP file found, exiting" >> $W/B0.log.md; exit 0; }
  (( $(date +%s) - start > 18000 )) && { echo "- $(date '+%F %T') queue: 5 h elapsed, exiting" >> $W/B0.log.md; exit 0; }
  # priority order (coordinator): F5, F2, F3, combined, then anything else READY
  for name in F5 F2 F3 combined ${(f)"$(for r in $W/bundles/*/READY(N); do echo ${r:h:t}; done)"}; do
    ready=$W/bundles/$name/READY; [[ -f $ready ]] || continue
    grep -qx "$name" $W/bench/benched.txt && continue
    [[ $name == baseline || $name == combined-pre ]] && continue  # combined-pre: not to be benched unless asked (coordinator)
    echo "- $(date '+%F %T') queue: found READY bundle $name" >> $W/B0.log.md
    $B/bench_bundle.sh $name $HEAP; rc=$?
    if (( rc == 2 )); then echo "- $(date '+%F %T') queue: $name deferred (disk guard); retry in 5 min" >> $W/B0.log.md; sleep 300; continue; fi
    if (( rc != 0 )); then echo "- $(date '+%F %T') queue: $name bench_bundle rc=$rc (killed/aborted) — NOT marked benched; retry in 2 min" >> $W/B0.log.md; sleep 120; continue; fi
    echo "$name" >> $W/bench/benched.txt
  done
  sleep 60
done
