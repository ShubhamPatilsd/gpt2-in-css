#!/bin/zsh
# B1 bench queue v2 (03:0x, coordinator adjustment). Reuses B0/bench_bundle.sh + B0/run_bench.sh (mouseoff config default).
# Order (coordinator reversal 09:4x, R2B MB7/MB8: R2C predicted −4.9 s/token): 1) 'combined (mouseoff)' reference row (recorded even if
#        an earlier queue's bench_bundle finishes it); 2) READY bundles in priority R2C, R2F, combined3, R2D, R2E, then others (alphabetical) —
#        skips baseline, combined-pre, smoke-*, benched.txt. (The 03:02 'R2C record-only when idle' rule is removed.)
# Stops on bench/STOP or when the budget (B1_BUDGET_S, anchored at 02:25) elapses. Logs to B1.log.md; mirrors run_bench's B0.log.md lines.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
B=$W/B0; mkdir -p $W/bench/runs
HEAP=${B1_QUEUE_HEAP:-1}
BUDGET=${B1_BUDGET_S:-14400}
start=$(date +%s)
touch $W/bench/benched.txt
log() { echo "- $(date '+%F %T') $*" >> $W/B1.log.md; echo "$(date '+%T') $*"; }
b0lines=$(wc -l < $W/B0.log.md)
mirror() { local n=$(wc -l < $W/B0.log.md); if (( n > b0lines )); then { echo "  (mirrored from B0.log.md, written by B0/run_bench.sh)"; tail -n +$((b0lines+1)) $W/B0.log.md | sed 's/^/  /'; } >> $W/B1.log.md; b0lines=$n; fi; }
typeset -A fails
compare() { python3 - "$1" <<'PY2'
import sys
row=sys.argv[1]; cells=[c.strip() for c in row.strip().strip('|').split('|')]
try:
    med=float(cells[3]); print(f"median {med:.1f} s/token: {med-30.3:+.1f} s vs combined (30.3, {100*(med-30.3)/30.3:+.0f} %), {med-40.2:+.1f} s vs baseline (40.2, {100*(med-40.2)/40.2:+.0f} %)")
except Exception as e: print(f"(could not parse median: {e})")
PY2
}
# record <key> <rowname> <name>: if the row exists in results.md and key is not in benched.txt → mark benched, append to B1.md. Returns 0 if recorded.
record() {
  local key=$1 rowname=$2 name=$3 row cmp
  grep -qx "$key" $W/bench/benched.txt && return 0
  row=$(grep -F "| $rowname |" $W/bench/results.md | tail -1); [[ -z $row ]] && return 1
  echo "$key" >> $W/bench/benched.txt
  cmp=$(compare "$row")
  log "queue: $key done → $row"
  log "queue: $key — $cmp"
  { echo ""; echo "### $rowname — $(date '+%F %T')"; echo ""; grep -E "^\|(---| bundle \|)" $W/bench/results.md; echo "$row"; echo ""; echo "$cmp. Detail: \`bench/$key.md\`; runs: \`bench/runs/$name/$key-*\`."; } >> $W/B1.md
  return 0
}
busy() { pgrep -f "$B/bench_bundle.sh|$B/run_bench.sh" >/dev/null; }
# bench_one <bundle> [tag]: full 3+1 protocol via B0/bench_bundle.sh, then record. Returns 0 when a row was written.
bench_one() {
  local name=$1 tag=${2:-} key rowname rc
  key=$name${tag:+-$tag}; rowname="$name (heap=$HEAP)"; [[ -n $tag ]] && rowname="$name ($tag)"
  log "queue: benching $key (row '$rowname', mouseoff=${B0_MOUSEOFF:-off})"
  B0_TAG=$tag $B/bench_bundle.sh $name $HEAP; rc=$?
  mirror; last_active=$(date +%s)
  if (( rc == 2 )); then log "queue: $key deferred (disk guard); retry in 5 min"; sleep 300; return 1; fi
  if (( rc != 0 )); then fails[$key]=$(( ${fails[$key]:-0} + 1 )); log "queue: $key bench_bundle rc=$rc (killed/aborted) — NOT marked benched; failure ${fails[$key]}/3; retry in 2 min"; (( fails[$key] >= 3 )) && { log "queue: $key FAILED 3x — skipping; needs manual fix"; echo "- $(date '+%F %T') **$key: harness failed 3x (rc=$rc) — see B1.log.md; not benched**" >> $W/B1.md; }; sleep 120; return 1; fi
  record $key "$rowname" $name || log "queue: $key finished rc=0 but no row '$rowname' found in results.md"
}
# one untraced R2C run for the record (idle rule)
r2c_record() {
  local rowname="R2C (heap=$HEAP, 1 untraced run, for the record)" row cmp rc
  log "queue: idle ≥ 20 min with nothing READY → ONE untraced R2C run for the record"
  $B/run_bench.sh R2C R2C-u1 $HEAP 0; rc=$?; mirror; last_active=$(date +%s)
  (( rc == 4 )) && { log "queue: R2C-u1 invalid (battery) — will retry when idle again"; return 1; }
  (( rc != 0 )) && { fails[R2C-record]=$(( ${fails[R2C-record]:-0} + 1 )); log "queue: R2C-u1 rc=$rc (failure ${fails[R2C-record]}/3)"; return 1; }
  row=$(python3 $B/aggregate.py "$rowname" $W/bench/R2C.md $W/bench/runs/R2C/R2C-u1.json --notes "config: heap=$HEAP, mouseoff (off-viewport); single untraced run — form-test bundle, no predicted gain (R2A R7); slope/median over 1 run")
  echo "$row" >> $W/bench/results.md; echo "R2C-record" >> $W/bench/benched.txt
  cmp=$(compare "$row"); log "queue: R2C-record done → $row"; log "queue: R2C-record — $cmp"
  { echo ""; echo "### $rowname — $(date '+%F %T')"; echo ""; grep -E "^\|(---| bundle \|)" $W/bench/results.md; echo "$row"; echo ""; echo "$cmp. Single untraced run; detail: \`bench/R2C.md\`."; } >> $W/B1.md
}
log "queue v3: started (heap=$HEAP, budget ${BUDGET}s, pid $$, mouseoff=${B0_MOUSEOFF:-off}, priority: combined(mouseoff) → R2C → R2F → combined3 → R2D → R2E → others; full 3+1 for all)"
last_active=$(date +%s)
while true; do
  [[ -f $W/bench/STOP ]] && { mirror; log "queue: STOP file found, exiting"; exit 0; }
  (( $(date +%s) - start > BUDGET )) && { mirror; log "queue: budget elapsed, exiting"; exit 0; }
  # 0. an earlier queue's bench_bundle may still be running (combined-mouseoff): wait for it, then record its row
  if busy; then last_active=$(date +%s); sleep 30; record combined-mouseoff "combined (mouseoff)" combined; continue; fi
  record combined-mouseoff "combined (mouseoff)" combined
  if ! grep -qx "combined-mouseoff" $W/bench/benched.txt && (( ${fails[combined-mouseoff]:-0} < 3 )); then bench_one combined mouseoff; continue; fi
  ready=(${(f)"$(for r in $W/bundles/*/READY(N); do echo ${r:h:t}; done)"})
  ordered=(R2C R2F combined3 R2D R2E ${(o)ready})  # coordinator 09:5x: combined3 (R2H: R2C+R2F+R2D on the F4 base) ahead of R2D as soon as it is READY
  picked=""
  for name in $ordered; do
    [[ -f $W/bundles/$name/READY ]] || continue
    grep -qx "$name" $W/bench/benched.txt && continue
    [[ $name == baseline || $name == combined-pre || $name == smoke-* ]] && continue
    (( ${fails[$name]:-0} >= 3 )) && continue
    picked=$name; break
  done
  if [[ -n $picked ]]; then log "queue: found READY bundle $picked (order: ${ordered})"; bench_one $picked; continue; fi
  sleep 60
done
