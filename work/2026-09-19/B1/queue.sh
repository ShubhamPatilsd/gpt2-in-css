#!/bin/zsh
# B1 bench queue (round 2). Reuses B0/bench_bundle.sh + B0/run_bench.sh (protocol unchanged; 02:5x: +mouseoff config, +B0_TAG re-bench support).
# Schedules 'combined (mouseoff)' (new reference row, coordinator/R2A §1) before any READY bundle.
# Every 60 s: bench any work/2026-09-19/bundles/*/READY not in bench/benched.txt.
# Priority: R2C, R2D, then combined3*/R2*, then others. Skips baseline, combined-pre, smoke-*.
# Stops on bench/STOP or after 4 h. Logs to B1.log.md (and mirrors run_bench's B0.log.md lines).
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
B=$W/B0; mkdir -p $W/bench/runs
HEAP=${B1_QUEUE_HEAP:-1}
BUDGET=${B1_BUDGET_S:-14400}
start=$(date +%s)
touch $W/bench/benched.txt
log() { echo "- $(date '+%F %T') $*" >> $W/B1.log.md; echo "$(date '+%T') $*"; }
b0lines=$(wc -l < $W/B0.log.md)
mirror() { local n=$(wc -l < $W/B0.log.md); if (( n > b0lines )); then { echo "  (mirrored from B0.log.md, written by the unchanged B0/run_bench.sh)"; tail -n +$((b0lines+1)) $W/B0.log.md | sed 's/^/  /'; } >> $W/B1.log.md; b0lines=$n; fi; }
typeset -A fails
# bench_one <bundle> [tag]: run B0/bench_bundle.sh (unchanged protocol), then record row + comparison in B1.md. Returns 0 when a row was written.
bench_one() {
  local name=$1 tag=${2:-} key rowname rc row cmp
  key=$name${tag:+-$tag}; rowname="$name (heap=$HEAP)"; [[ -n $tag ]] && rowname="$name ($tag)"
  log "queue: benching $key (row '$rowname', mouseoff=${B0_MOUSEOFF:-off})"
  B0_TAG=$tag $B/bench_bundle.sh $name $HEAP; rc=$?
  mirror
  if (( rc == 2 )); then log "queue: $key deferred (disk guard); retry in 5 min"; sleep 300; return 1; fi
  if (( rc != 0 )); then fails[$key]=$(( ${fails[$key]:-0} + 1 )); log "queue: $key bench_bundle rc=$rc (killed/aborted) — NOT marked benched; failure ${fails[$key]}/3; retry in 2 min"; (( fails[$key] >= 3 )) && { log "queue: $key FAILED 3x — skipping; needs manual fix"; echo "- $(date '+%F %T') **$key: harness failed 3x (rc=$rc) — see B1.log.md; not benched**" >> $W/B1.md; }; sleep 120; return 1; fi
  echo "$key" >> $W/bench/benched.txt
  row=$(grep -F "| $rowname |" $W/bench/results.md | tail -1)
  cmp=$(python3 - "$row" <<'PY2'
import sys
row=sys.argv[1]; cells=[c.strip() for c in row.strip().strip('|').split('|')]
try:
    med=float(cells[3]); print(f"median {med:.1f} s/token: {med-30.3:+.1f} s vs combined (30.3, {100*(med-30.3)/30.3:+.0f} %), {med-40.2:+.1f} s vs baseline (40.2, {100*(med-40.2)/40.2:+.0f} %)")
except Exception as e: print(f"(could not parse median: {e})")
PY2
)
  log "queue: $key done → $row"
  log "queue: $key — $cmp"
  { echo ""; echo "### $rowname — $(date '+%F %T')"; echo ""; grep -E "^\|(---| bundle \|)" $W/bench/results.md; echo "$row"; echo ""; echo "$cmp. Detail: \`bench/$key.md\`; runs: \`bench/runs/$name/$key-*\`."; } >> $W/B1.md
  return 0
}
log "queue: started (heap=$HEAP, budget ${BUDGET}s, pid $$, mouseoff=${B0_MOUSEOFF:-off})"
while true; do
  [[ -f $W/bench/STOP ]] && { mirror; log "queue: STOP file found, exiting"; exit 0; }
  (( $(date +%s) - start > BUDGET )) && { mirror; log "queue: 4 h budget elapsed, exiting"; exit 0; }
  # 0. new reference row first (coordinator, R2A §1): combined under the mouseoff config
  if ! grep -qx "combined-mouseoff" $W/bench/benched.txt && (( ${fails[combined-mouseoff]:-0} < 3 )); then bench_one combined mouseoff; continue; fi
  ready=(${(f)"$(for r in $W/bundles/*/READY(N); do echo ${r:h:t}; done)"})
  ordered=(R2C R2D ${(oM)ready:#(combined3*|R2*)} ${(o)ready})
  for name in $ordered; do
    [[ -f $W/bundles/$name/READY ]] || continue
    grep -qx "$name" $W/bench/benched.txt && continue
    [[ $name == baseline || $name == combined-pre || $name == smoke-* ]] && continue
    (( ${fails[$name]:-0} >= 3 )) && continue
    log "queue: found READY bundle $name (order: ${ordered})"
    bench_one $name
    continue 2
  done
  sleep 60
done
