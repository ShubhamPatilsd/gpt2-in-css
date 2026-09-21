#!/bin/zsh
# B5 round-4 interleaved PAIRED bench queue (2026-09-21). ref = bundles/combined4 (18.2 s/token paired, B4).
# Queue (priority order, poll 60 s for READY): R4S, R4T, combined5, combined6, combined7, R4T2 (coordinator 02:1x / 03:0x).
# Lock: ONE CHROME.lock hold per PAIR (owner "B5 pair <cand>-<k>", touch -c every 30 s), ref then cand back-to-back, released after (coordinator 03:0x). Skips B5/benched5.txt, smoke-*, capacity-32 bundles.
# Per candidate: ref, cand, ref, cand, ref, cand until 3 VALID pairs (combined6/combined7: 4; valid = ref→cand start gap ≤ 10 min, else replaced) through B5/run_bench5.sh (= B0/run_bench.sh + round-4
# lock protocol), heap=1, untraced, B0_TRIGGER=keyboard for BOTH arms, no quiet-gate wait, AC required.
# Labels: bench/runs/combined4/paired5-ref-<cand>-<k>.json and bench/runs/<cand>/paired5-<k>.json. After each candidate: B5/analyze5.py
# → row "<cand> (paired vs combined4)" in bench/results.md + per-run table in bench/paired-round4.md. Progress → B5.md after every run.
# Budget: B5_BUDGET_S (default 8 h) from start, or bench/STOP with an mtime AT/AFTER this driver's start (a stale round-3 STOP from
# 2026-09-20 23:15 exists and is ignored; `touch bench/STOP` halts us).
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; B=$W/B0; D=$W/B5
export B0_TRIGGER=keyboard
BUDGET=${B5_BUDGET_S:-28800}
start=$(date +%s)
log() { echo "- $(date '+%F %T') $*" >> $W/B5.log.md; echo "$(date '+%T') $*"; }
prog() { echo "- $(date '+%F %T') $*" >> $W/B5.md; }
b0lines=$(wc -l < $W/B0.log.md)
mirror() { local n=$(wc -l < $W/B0.log.md); if (( n > b0lines )); then { echo "  (mirrored from B0.log.md, written by B5/run_bench5.sh; B5 labels are paired5-*)"; tail -n +$((b0lines+1)) $W/B0.log.md | grep -F 'paired5-' | sed 's/^/  /'; } >> $W/B5.log.md; b0lines=$n; fi; }
budget_ok() { (( $(date +%s) - start < BUDGET )); }
stop_req() { [[ -f $W/bench/STOP ]] && (( $(stat -f %m $W/bench/STOP) >= start )); }
touch $D/benched5.txt
log "B5: started (pid $$, budget ${BUDGET}s → ends $(date -v+${BUDGET}S '+%F %T')); ref=combined4; queue R4S R4T combined5 combined6 combined7 R4T2 R4T-b; one CHROME.lock hold per pair; trigger=keyboard both arms; STOP honoured only if mtime >= $(date -r $start '+%F %T')"
# ---- per-PAIR lock (coordinator 03:0x): acquire once, ref then cand back-to-back (Chrome exits between them), release after ----
LOCK=$W/CHROME.lock; lock_owner=""; hb_pid=""
acquire_lock() {  # acquire_lock <owner-string>; mkdir fails on a dir OR a file → held; polls 5 s; never removes a foreign lock; rc 2 on fresh STOP
  local waited=0
  while ! mkdir $LOCK 2>/dev/null; do
    (( waited == 0 )) && log "B5: CHROME.lock held ($(cat $LOCK/owner 2>/dev/null || echo 'no marker / lock file')) — waiting to start the pair (poll 5 s)"
    (( waited > 0 && waited % 900 == 0 )) && log "B5: still waiting for CHROME.lock (${waited}s; holder: $(cat $LOCK/owner 2>/dev/null || echo ?))"
    stop_req && return 2
    sleep 5; waited=$((waited+5))
  done
  echo "$1" > $LOCK/owner; lock_owner="$1"
  ( while [[ -d $LOCK ]] && kill -0 $$ 2>/dev/null; do touch -c $LOCK; sleep 30; done ) & hb_pid=$!
  log "B5: CHROME.lock acquired for '$1' after ${waited}s"
}
release_lock() {
  [[ -n $hb_pid ]] && kill $hb_pid 2>/dev/null; hb_pid=""
  if [[ -n $lock_owner && -d $LOCK && "$(cat $LOCK/owner 2>/dev/null)" == "$lock_owner" ]]; then
    rm -f $LOCK/owner; rmdir $LOCK 2>/dev/null && log "B5: CHROME.lock released ('$lock_owner')" || log "B5: rmdir CHROME.lock failed: $(ls -la $LOCK 2>&1 | tr '\n' ' ')"
  fi
  lock_owner=""
}
on_term() { log "B5: TERM/INT — stopping the harness child (it kills its node/Chrome), releasing the pair lock"; pkill -TERM -f "$D/run_bench5.sh" 2>/dev/null; sleep 3; release_lock; }
trap 'on_term; exit 130' INT TERM
# ---- one run through the harness under the pair lock (single attempt; any failure abandons the pair) ----
run_step_held() {  # run_step_held <bundle> <label> <stepdesc>
  local bundle=$1 label=$2 desc=$3 rc
  log "B5: $desc — run_bench5.sh $bundle $label 1 0 600000 (pair lock '$lock_owner')"
  B0_FORCE=0 B5_LOCK_HELD=1 B5_LOCK_OWNER="$lock_owner" $D/run_bench5.sh $bundle $label 1 0 600000 > $D/$bundle-$label.out 2>&1; rc=$?
  mirror
  if (( rc == 0 )); then
    local one=$(python3 $B/summarize_run.py $W/bench/runs/$bundle/$label.json --oneline 2>&1 | tail -1 | cut -c1-260)
    log "B5: $desc done rc=0: $one"; prog "$desc → \`$bundle/$label\`: $one"; return 0; fi
  log "B5: $desc rc=$rc (tail: $(tail -2 $D/$bundle-$label.out | tr '\n' ' ' | cut -c1-200))"
  prog "$desc FAILED rc=$rc (pair abandoned; rc 4 = battery/server, 2 = disk, 3 = foreign Chrome, 7 = lock not ours) — see B5/$bundle-$label.out"
  return $rc
}
bundle_of() { echo ${1%-b}; }          # "R4T-b" → bundle R4T (second block of pairs, coordinator 03:4x)
clabel() { [[ $1 == *-b ]] && echo paired5-b || echo paired5; }
valid_pairs() { python3 $D/analyze5.py --no-append --valid-count $1 2>/dev/null | tail -1; }
max_k() { local c=$1 m=0 f k; for f in $W/bench/runs/combined4/paired5-ref-$c-<->.json(N) $W/bench/runs/$(bundle_of $c)/$(clabel $c)-<->.json(N); do k=${${f:t:r}##*-}; [[ $k == <-> ]] && (( k > m )) && m=$k; done; echo $m; }
# ---- one candidate: pairs (each under one lock hold) until np VALID pairs, then analysis. Orphan refs from earlier protocol versions are never reused. ----
bench_cand() {
  local cand=$1 np=3 k v attempts=0 rc; [[ $cand == combined6 || $cand == combined7 ]] && np=4
  local bdir=$W/bundles/$(bundle_of $cand)
  log "B5: candidate $cand (bundle $(bundle_of $cand)) — until $np valid pairs (valid on disk now: $(valid_pairs $cand)); READY: '$(head -1 $bdir/READY 2>/dev/null | cut -c1-140)'; index.html mtime $(stat -f '%Sm' $bdir/index.html)"
  prog ""; prog "### $cand — started $(date '+%F %T'), until $np valid pairs (ref combined4, cand = bundle $(bundle_of $cand); one CHROME.lock hold per pair); valid on disk now: $(valid_pairs $cand); READY: '$(head -1 $bdir/READY 2>/dev/null | cut -c1-140)'"
  k=$(max_k $cand)
  while true; do
    v=$(valid_pairs $cand); (( v >= np )) && { log "B5: $cand — $v valid pairs, done"; break; }
    stop_req && { log "B5: bench/STOP (fresh) present — stopping $cand (valid $v/$np)"; prog "STOP during $cand (valid $v/$np)"; return 2; }
    budget_ok || { log "B5: budget elapsed — stopping $cand (valid $v/$np)"; prog "Budget elapsed during $cand (valid $v/$np)"; return 2; }
    attempts=$((attempts+1)); (( attempts > np + 4 )) && { log "B5: $cand — giving up after $attempts pair attempts (valid $v/$np)"; prog "$cand: gave up after $attempts pair attempts (valid $v/$np)"; break; }
    [[ -f $W/bundles/combined4/index.html ]] || { log "B5: bundles/combined4/index.html missing — cannot run the reference; abort"; return 1; }
    k=$((k+1))
    acquire_lock "B5 pair $cand-$k" || { log "B5: STOP while waiting for the lock"; prog "STOP while waiting for the lock before pair $k of $cand"; return 2; }
    run_step_held combined4 paired5-ref-$cand-$k "$cand pair $k ref (valid so far $v/$np)"; rc=$?
    (( rc == 0 )) && { run_step_held $(bundle_of $cand) $(clabel $cand)-$k "$cand pair $k cand"; rc=$?; }
    release_lock
    (( rc != 0 )) && sleep 60
  done
  log "B5: $cand — running analyze5.py"
  python3 $D/analyze5.py $cand > $D/analyze-$cand.out 2>&1; local arc=$?
  log "B5: analyze5.py $cand rc=$arc → bench/paired-round4.md + results.md row (B5/analyze-$cand.out)"
  echo $cand >> $D/benched5.txt
  { echo ""; echo "#### $cand — result ($(date '+%F %T'))"; echo ""; grep -E "^\|(---| bundle \|)" $W/bench/results.md; grep -F "| $cand (paired vs combined4) |" $W/bench/results.md | tail -1; echo "";
    sed -n "/^\*\*$cand — /,/^$/p" $W/bench/paired-round4.md; echo "Per-run table: \`bench/paired-round4.md\`; runs: \`bench/runs/combined4/paired5-ref-$cand-*\`, \`bench/runs/$(bundle_of $cand)/$(clabel $cand)-*\`."; } >> $W/B5.md
}
# ---- the queue ----
QUEUE=(R4S R4T combined5 combined6 combined7 R4T2 R4T-b)   # R4T-b = second block of 3 R4T pairs at the END (coordinator 03:4x)
benched() { grep -qx "$1" $D/benched5.txt; }
n=0
while true; do
  stop_req && { log "B5: bench/STOP (fresh) present — exiting"; prog "STOP — queue exited $(date '+%F %T')"; break; }
  budget_ok || { log "B5: budget elapsed — exiting"; prog "Budget elapsed — queue exited $(date '+%F %T')"; break; }
  picked=""
  for c in $QUEUE; do
    [[ $c == smoke-* || $c == *c32* ]] && continue
    [[ -f $W/bundles/$(bundle_of $c)/READY && -f $W/bundles/$(bundle_of $c)/index.html ]] && ! benched $c && { picked=$c; break; }
  done
  if [[ -n $picked ]]; then bench_cand $picked; rc=$?; (( rc == 2 )) && break; continue; fi
  all=1; for c in $QUEUE; do benched $c || all=0; done
  (( all )) && { log "B5: all candidates benched — exiting"; prog "All candidates benched — queue exited $(date '+%F %T')"; break; }
  (( n % 10 == 0 )) && log "B5: idle — waiting for READY candidates (benched: $(tr '\n' ' ' < $D/benched5.txt); READY now: $(for r in $W/bundles/*/READY(N); do echo -n "${r:h:t} "; done); lock: $(cat $W/CHROME.lock/owner 2>/dev/null || echo free))"
  sleep 60; n=$((n+1))
done
touch $D/DONE
log "B5: DONE"
