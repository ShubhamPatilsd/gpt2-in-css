#!/bin/zsh
# B6 round-5 interleaved PAIRED bench queue (2026-09-24). ref = bundles/combined7 (16.0 s/token paired, B5).
# Queue (priority order, poll 60 s for READY): R5H, R5C, R5E, R5M, then any bundles/combined8*/ (R5X merge, 4 pairs). Skips smoke-*, *c32*, B6/benched6.txt.
# Protocol = B5/paired5.sh (round 4): ONE CHROME.lock hold per PAIR (owner "B6 pair <cand>-<k>", touch -c every 30 s, rmdir only own, poll 5 s),
# ref then cand back-to-back through B6/run_bench6.sh (heap=1, untraced, B0_TRIGGER=keyboard both arms, AC required), pair VALID iff ref→cand
# START gap <= 10 min, 3 valid pairs per candidate (4 for combined8*), verdict = paired Δ median with range vs the largest adjacent-ref swing.
# Round 5: MACHINE GATE (AC + disk >= 3.0 GB + swap used < 3000 MB) before the pair (here, poll 60 s, lock NOT held) and again inside the harness
# before every launch (rc 8 if it stays closed > 10 min while we hold the lock → release, wait here, retry). Disk/swap logged per run START/END.
# Labels: bench/runs/combined7/paired6-ref-<cand>-<k>.json, bench/runs/<cand>/paired6-<k>.json. After each candidate: B6/analyze6.py →
# bench/paired-round5.md (+ RSS columns) + one "<cand> (paired vs combined7)" row in bench/results.md; verdict line → B6/verdicts.txt (watched by
# the agent, which relays it to the coordinator). Budget B6_BUDGET_S (default 6 h) from start; STOP file bench/STOP6 (any mtime) halts between runs.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; B=$W/B0; D=$W/B6
REF=combined7
export B0_TRIGGER=keyboard
BUDGET=${B6_BUDGET_S:-21600}
start=$(date +%s)
log() { echo "- $(date '+%F %T') $*" >> $W/B6.log.md; echo "$(date '+%T') $*"; }
prog() { echo "- $(date '+%F %T') $*" >> $W/B6.md; }
budget_ok() { (( $(date +%s) - start < BUDGET )); }
stop_req() { [[ -f $W/bench/STOP6 ]]; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
disk_kb() { df -k / | tail -1 | awk '{print $4}'; }
swap_mb() { sysctl -n vm.swapusage | awk '{print $6}' | tr -d 'M' | cut -d. -f1; }
gate_state() { echo "AC=$(on_ac && echo 1 || echo 0) disk_free_MB=$(( $(disk_kb) / 1024 )) swap_used_MB=$(swap_mb) load1=$(sysctl -n vm.loadavg | awk '{print $2}')"; }
# coordinator 2026-09-24 16:0x (swap flickered 3.0–3.6 GB after every renderer and stalled the queue): gate = AC AND ( (disk >= 4.0 GB AND swap < 4000 MB) OR (disk >= 3.0 GB AND swap < 3000 MB) )
gate_ok() { on_ac || return 1; local d=$(disk_kb) s=$(swap_mb); { (( d >= 4194304 )) && (( s < 4000 )); } || { (( d >= 3145728 )) && (( s < 3000 )); }; }
wait_gate() {  # rc 2 on STOP/budget
  local n=0
  while ! gate_ok; do
    (( n % 10 == 0 )) && { log "B6: machine gate CLOSED ($(gate_state)); need AC + (disk >= 4.0 GB && swap < 4000 MB) or (disk >= 3.0 GB && swap < 3000 MB) — waiting (poll 60 s, lock not held)"; prog "machine gate closed ($(gate_state)) — waiting"; }
    stop_req && return 2; budget_ok || return 2
    sleep 60; n=$((n+1))
  done
  (( n > 0 )) && log "B6: machine gate OPEN again after $((n))×60 s ($(gate_state))"
  return 0
}
touch $D/benched6.txt $D/verdicts.txt
log "B6: driver started (pid $$, budget ${BUDGET}s → ends $(date -v+${BUDGET}S '+%F %T')); ref=$REF; queue R5H R5C R5E R5M combined8*; one CHROME.lock hold per pair; trigger=keyboard both arms; heap=1; machine gate AC + (disk>=4GB && swap<4000MB | disk>=3GB && swap<3000MB) before every launch; STOP file bench/STOP6; gate now: $(gate_state)"
# ---- per-PAIR lock: acquire once, ref then cand back-to-back (Chrome exits between them), release after ----
LOCK=$W/CHROME.lock; lock_owner=""; hb_pid=""
acquire_lock() {  # acquire_lock <owner-string>; mkdir fails on a dir OR a file → held; polls 5 s; never removes a foreign lock; rc 2 on STOP
  local waited=0
  while ! mkdir $LOCK 2>/dev/null; do
    (( waited == 0 )) && log "B6: CHROME.lock held ($(cat $LOCK/owner 2>/dev/null || echo 'no marker / lock file')) — waiting to start the pair (poll 5 s)"
    (( waited > 0 && waited % 900 == 0 )) && log "B6: still waiting for CHROME.lock (${waited}s; holder: $(cat $LOCK/owner 2>/dev/null || echo ?))"
    stop_req && return 2
    sleep 5; waited=$((waited+5))
  done
  echo "$1" > $LOCK/owner; lock_owner="$1"
  ( while [[ -d $LOCK ]] && kill -0 $$ 2>/dev/null; do touch -c $LOCK; sleep 30; done ) & hb_pid=$!
  log "B6: CHROME.lock acquired for '$1' after ${waited}s ($(gate_state))"
}
release_lock() {
  [[ -n $hb_pid ]] && kill $hb_pid 2>/dev/null; hb_pid=""
  if [[ -n $lock_owner && -d $LOCK && "$(cat $LOCK/owner 2>/dev/null)" == "$lock_owner" ]]; then
    rm -f $LOCK/owner; rmdir $LOCK 2>/dev/null && log "B6: CHROME.lock released ('$lock_owner')" || log "B6: rmdir CHROME.lock failed: $(ls -la $LOCK 2>&1 | tr '\n' ' ')"
  fi
  lock_owner=""
}
on_term() { log "B6: TERM/INT — stopping the harness child (it kills its node/Chrome), releasing the pair lock"; pkill -TERM -f "$D/run_bench6.sh" 2>/dev/null; sleep 3; release_lock; }
trap 'on_term; exit 130' INT TERM
# ---- one run through the harness under the pair lock (single attempt; any failure abandons the pair) ----
run_step_held() {  # run_step_held <bundle> <label> <stepdesc>
  local bundle=$1 label=$2 desc=$3 rc
  log "B6: $desc — run_bench6.sh $bundle $label 1 0 600000 (pair lock '$lock_owner'; $(gate_state))"
  B0_FORCE=0 B6_LOCK_HELD=1 B6_LOCK_OWNER="$lock_owner" $D/run_bench6.sh $bundle $label 1 0 600000 > $D/$bundle-$label.out 2>&1; rc=$?
  if (( rc == 0 )); then
    local one=$(python3 $D/analyze6.py --oneline $bundle $label 2>&1 | tail -1 | cut -c1-320)
    log "B6: $desc done rc=0: $one"; prog "$desc → \`$bundle/$label\`: $one"; return 0; fi
  log "B6: $desc rc=$rc (tail: $(tail -2 $D/$bundle-$label.out | tr '\n' ' ' | cut -c1-200))"
  prog "$desc FAILED rc=$rc (pair abandoned; rc 8 = machine gate closed > 10 min under the lock, 4 = battery/server, 3 = foreign Chrome, 7 = lock not ours) — see B6/$bundle-$label.out"
  return $rc
}
valid_pairs() { python3 $D/analyze6.py --no-append --valid-count $1 2>/dev/null | tail -1; }
max_k() { local c=$1 m=0 f k; for f in $W/bench/runs/$REF/paired6-ref-$c-<->.json(N) $W/bench/runs/$c/paired6-<->.json(N); do k=${${f:t:r}##*-}; [[ $k == <-> ]] && (( k > m )) && m=$k; done; echo $m; }
npairs() { [[ $1 == combined8* ]] && echo 4 || echo 3; }
# ---- one candidate: pairs (each under one lock hold) until np VALID pairs, then analysis ----
bench_cand() {
  local cand=$1 np=$(npairs $1) k v attempts=0 rc
  local bdir=$W/bundles/$cand
  log "B6: candidate $cand — until $np valid pairs (valid on disk now: $(valid_pairs $cand)); READY: '$(head -1 $bdir/READY 2>/dev/null | cut -c1-160)'; index.html mtime $(stat -f '%Sm' $bdir/index.html)"
  prog ""; prog "### $cand — started $(date '+%F %T'), until $np valid pairs (ref $REF; one CHROME.lock hold per pair); valid on disk now: $(valid_pairs $cand); READY: '$(head -1 $bdir/READY 2>/dev/null | cut -c1-160)'"
  k=$(max_k $cand)
  while true; do
    v=$(valid_pairs $cand); (( v >= np )) && { log "B6: $cand — $v valid pairs, done"; break; }
    stop_req && { log "B6: bench/STOP6 present — stopping $cand (valid $v/$np)"; prog "STOP6 during $cand (valid $v/$np)"; return 2; }
    budget_ok || { log "B6: budget elapsed — stopping $cand (valid $v/$np)"; prog "Budget elapsed during $cand (valid $v/$np)"; return 2; }
    attempts=$((attempts+1)); (( attempts > np + 5 )) && { log "B6: $cand — giving up after $attempts pair attempts (valid $v/$np)"; prog "$cand: gave up after $attempts pair attempts (valid $v/$np)"; break; }
    [[ -f $W/bundles/$REF/index.html ]] || { log "B6: bundles/$REF/index.html missing — cannot run the reference; abort"; return 1; }
    wait_gate || { log "B6: STOP6/budget while waiting for the machine gate"; return 2; }
    k=$((k+1))
    acquire_lock "B6 pair $cand-$k" || { log "B6: STOP6 while waiting for the lock"; prog "STOP6 while waiting for the lock before pair $k of $cand"; return 2; }
    run_step_held $REF paired6-ref-$cand-$k "$cand pair $k ref (valid so far $v/$np)"; rc=$?
    (( rc == 0 )) && { run_step_held $cand paired6-$k "$cand pair $k cand"; rc=$?; }
    release_lock
    (( rc != 0 )) && sleep 60
  done
  log "B6: $cand — running analyze6.py"
  python3 $D/analyze6.py $cand > $D/analyze-$cand.out 2>&1; local arc=$?
  log "B6: analyze6.py $cand rc=$arc → bench/paired-round5.md + results.md row (B6/analyze-$cand.out)"
  echo $cand >> $D/benched6.txt
  { echo ""; echo "#### $cand — result ($(date '+%F %T'))"; echo ""; grep -E "^\|(---| bundle \|)" $W/bench/results.md; grep -F "| $cand (paired vs $REF) |" $W/bench/results.md | tail -1; echo "";
    sed -n "/^\*\*$cand — /,/^$/p" $W/bench/paired-round5.md; grep -F "Machine state" $W/bench/paired-round5.md | grep -F "[$cand]" | tail -1;
    echo "Per-run table: \`bench/paired-round5.md\`; runs: \`bench/runs/$REF/paired6-ref-$cand-*\`, \`bench/runs/$cand/paired6-*\`."; } >> $W/B6.md
  python3 $D/analyze6.py --no-append --verdict $cand >> $D/verdicts.txt 2>/dev/null
}
# ---- the queue ----
STATIC=(R5H R5C R5E R5M)
queue() { local q=("${STATIC[@]}") d; for d in $W/bundles/combined8*(N/); do [[ ${d:t} == *c32* ]] && continue; q+=(${d:t}); done; echo ${q[@]}; }
benched() { grep -qx "$1" $D/benched6.txt; }
n=0
while true; do
  stop_req && { log "B6: bench/STOP6 present — exiting"; prog "STOP6 — queue exited $(date '+%F %T')"; break; }
  budget_ok || { log "B6: budget elapsed — exiting"; prog "Budget elapsed — queue exited $(date '+%F %T')"; break; }
  picked=""
  for c in $(queue); do
    [[ $c == smoke-* || $c == *c32* ]] && continue
    [[ -f $W/bundles/$c/READY && -f $W/bundles/$c/index.html ]] && ! benched $c && { picked=$c; break; }
  done
  if [[ -n $picked ]]; then bench_cand $picked; rc=$?; (( rc == 2 )) && break; continue; fi
  all=1; for c in $(queue); do benched $c || all=0; done
  (( all )) && [[ -n $(ls -d $W/bundles/combined8* 2>/dev/null) ]] && { log "B6: all candidates (incl. combined8*) benched — exiting"; prog "All candidates benched — queue exited $(date '+%F %T')"; break; }
  (( n % 10 == 0 )) && log "B6: idle — waiting for READY candidates (benched: $(tr '\n' ' ' < $D/benched6.txt); READY now: $(for r in $W/bundles/*/READY(N); do echo -n "${r:h:t} "; done); lock: $(cat $W/CHROME.lock/owner 2>/dev/null || echo free); $(gate_state))"
  sleep 60; n=$((n+1))
done
touch $D/DONE
log "B6: DONE"
