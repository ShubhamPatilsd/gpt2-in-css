#!/bin/zsh
# B2 bench queue (round 2, taking over from B1/queue2.sh at 12:2x 2026-09-20). Reuses B0/bench_bundle.sh + B0/run_bench.sh unchanged
# (heap=1, mouseoff default, AC gate, quiet gate load<3 up to 15 min then CONTENDED, stale-lock guard, 30 s power watchdog).
# Order: 1) record the in-flight 'combined (mouseoff)' reference (bench_bundle pid 57785 from B1's queue, left running);
#        2) READY bundles in priority R2C, R2F, combined3, R2D, R2E, then others alphabetically.
# Skips: baseline, combined-pre, smoke-*, combined3-no*, combined3-alloff, R2C-qonly, R2D-lock*, R2D-allknobs, anything in bench/benched.txt.
# Stops on bench/STOP or when the budget (B2_BUDGET_S, default 6 h from start) elapses. Logs to B2.log.md (mirrors run_bench's B0.log.md lines); reports to B2.md.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
B=$W/B0; mkdir -p $W/bench/runs
HEAP=${B2_QUEUE_HEAP:-1}
BUDGET=${B2_BUDGET_S:-21600}
start=$(date +%s)
touch $W/bench/benched.txt
log() { echo "- $(date '+%F %T') $*" >> $W/B2.log.md; echo "$(date '+%T') $*"; }
b0lines=$(wc -l < $W/B0.log.md)
mirror() { local n=$(wc -l < $W/B0.log.md); if (( n > b0lines )); then { echo "  (mirrored from B0.log.md, written by B0/run_bench.sh)"; tail -n +$((b0lines+1)) $W/B0.log.md | sed 's/^/  /'; } >> $W/B2.log.md; b0lines=$n; fi; }
typeset -A fails
compare() { python3 - "$1" <<'PY2'
import sys
row=sys.argv[1]; cells=[c.strip() for c in row.strip().strip('|').split('|')]
try:
    med=float(cells[3]); print(f"median {med:.1f} s/token: {med-30.3:+.1f} s vs combined (30.3, {100*(med-30.3)/30.3:+.0f} %), {med-40.2:+.1f} s vs baseline (40.2, {100*(med-40.2)/40.2:+.0f} %)")
except Exception as e: print(f"(could not parse median: {e})")
PY2
}
# record <key> <rowname> <name>: if the row exists in results.md and key is not in benched.txt → mark benched, append to B2.md. Returns 0 if recorded.
record() {
  local key=$1 rowname=$2 name=$3 row cmp startload endload
  grep -qx "$key" $W/bench/benched.txt && return 0
  row=$(grep -F "| $rowname |" $W/bench/results.md | tail -1); [[ -z $row ]] && return 1
  echo "$key" >> $W/bench/benched.txt
  cmp=$(compare "$row")
  startload=$(grep -F "[$name/$key-" $W/B0.log.md | grep -F ' START ' | sed -E 's/.*\[[^]]*\/([^]]*)\].* load=([^ ]*) .*/\1:\2/' | tr '\n' ' ')
  endload=$(grep -F "[$name/$key-" $W/B0.log.md | grep -F ' END ' | sed -E 's/.*\[[^]]*\/([^]]*)\].* load=([^ ]*) .*/\1:\2/' | tr '\n' ' ')
  log "queue: $key done → $row"
  log "queue: $key — $cmp"
  { echo ""; echo "### $rowname — $(date '+%F %T')"; echo ""; grep -E "^\|(---| bundle \|)" $W/bench/results.md; echo "$row"; echo "";
    echo "$cmp. Detail: \`bench/$key.md\`; runs: \`bench/runs/$name/$key-*\`."; echo "";
    echo "Load (1-min avg, from run_bench START/END lines): START $startload; END $endload."; } >> $W/B2.md
  return 0
}
busy() { pgrep -f "$B/bench_bundle.sh|$B/run_bench.sh" >/dev/null; }
# bench_one <bundle> [tag]: full 3+1 protocol via B0/bench_bundle.sh, then record. Returns 0 when a row was written.
bench_one() {
  local name=$1 tag=${2:-} key rowname rc
  key=$name${tag:+-$tag}; rowname="$name (heap=$HEAP)"; [[ -n $tag ]] && rowname="$name ($tag)"
  log "queue: benching $key (row '$rowname', mouseoff=${B0_MOUSEOFF:-off})"
  B0_TAG=$tag $B/bench_bundle.sh $name $HEAP; rc=$?
  mirror
  if (( rc == 2 )); then log "queue: $key deferred (disk guard); retry in 5 min"; sleep 300; return 1; fi
  if (( rc != 0 )); then fails[$key]=$(( ${fails[$key]:-0} + 1 )); log "queue: $key bench_bundle rc=$rc (killed/aborted) — NOT marked benched; failure ${fails[$key]}/3; retry in 2 min"; (( fails[$key] >= 3 )) && { log "queue: $key FAILED 3x — skipping; needs manual fix"; echo "- $(date '+%F %T') **$key: harness failed 3x (rc=$rc) — see B2.log.md; not benched**" >> $W/B2.md; }; sleep 120; return 1; fi
  record $key "$rowname" $name || log "queue: $key finished rc=0 but no row '$rowname' found in results.md"
}
skip() { case $1 in baseline|combined-pre|combined-calc|smoke-*|combined3-no*|combined3-alloff|R2C-qonly|R2D-lock*|R2D-allknobs) return 0;; esac; return 1; }
log "queue B2: started (heap=$HEAP, budget ${BUDGET}s → ends $(date -v+${BUDGET}S '+%F %T'), pid $$, mouseoff=${B0_MOUSEOFF:-off}, order: combined(mouseoff, in-flight pid 57785) → R2C → R2F → combined3 → R2D → R2E → others; full 3+1 for all)"
while true; do
  [[ -f $W/bench/STOP ]] && { mirror; log "queue: STOP file found, exiting"; exit 0; }
  (( $(date +%s) - start > BUDGET )) && { mirror; log "queue: budget elapsed, exiting"; exit 0; }
  # 0. B1's bench_bundle (combined-mouseoff) is still running: wait for it, mirror its lines, then record its row
  if busy; then mirror; sleep 30; record combined-mouseoff "combined (mouseoff)" combined; continue; fi
  mirror
  record combined-mouseoff "combined (mouseoff)" combined
  if ! grep -qx "combined-mouseoff" $W/bench/benched.txt && (( ${fails[combined-mouseoff]:-0} < 3 )); then bench_one combined mouseoff; continue; fi
  ready=(${(f)"$(for r in $W/bundles/*/READY(N); do echo ${r:h:t}; done)"})
  ordered=(R2C R2F combined3 R2D R2E ${(o)ready})
  picked=""
  for name in $ordered; do
    [[ -f $W/bundles/$name/READY ]] || continue
    grep -qx "$name" $W/bench/benched.txt && continue
    skip $name && continue
    (( ${fails[$name]:-0} >= 3 )) && continue
    picked=$name; break
  done
  if [[ -n $picked ]]; then log "queue: found READY bundle $picked (READY: ${ready})"; bench_one $picked; continue; fi
  sleep 60
done
