#!/bin/zsh
# R5G pair driver (2026-09-24): ONE CHROME.lock hold per pair — combined7 no-flag reference, then combined7 with the candidate flags, back-to-back.
# usage: CAND_JS_FLAGS='...' CAND_EXTRA_ARGS='...' pair.sh <label>
# Lock protocol (PLAN round 4/5): mkdir CHROME.lock (poll 5 s), owner "R5G pair <label> <pid> <time>", touch -c every 30 s, rmdir only own.
# Machine gate BEFORE the lock (poll 60 s; coordinator 16:0x rule: AC AND ((disk>=4GB AND swap<4000MB) OR (disk>=3GB AND swap<3000MB)))
# and again inside the harness before each launch (rc 8 after 10 min under the lock → release, wait outside, retry with a new label).
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; D=$W/R5G; LOCK=$W/CHROME.lock
label=$1; [[ -z $label ]] && { echo "usage: pair.sh <label>"; exit 2; }
export B0_TRIGGER=keyboard
log() { echo "- $(date '+%F %T') R5G[$label]: $*" >> $W/R5G.log.md; echo "$(date '+%T') $*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
disk_kb() { df -k / | tail -1 | awk '{print $4}'; }
swap_mb() { sysctl -n vm.swapusage | awk '{print $6}' | tr -d 'M' | cut -d. -f1; }
gate_state() { echo "AC=$(on_ac && echo 1 || echo 0) disk_free_MB=$(( $(disk_kb) / 1024 )) swap_used_MB=$(swap_mb) load1=$(sysctl -n vm.loadavg | awk '{print $2}')"; }
gate_ok() { on_ac || return 1; local d=$(disk_kb) s=$(swap_mb); { (( d >= 4194304 )) && (( s < 4000 )); } || { (( d >= 3145728 )) && (( s < 3000 )); }; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 10 == 0 )) && log "machine gate CLOSED ($(gate_state)) — waiting, lock not held (poll 60 s)"; sleep 60; n=$((n+1)); done; (( n > 0 )) && log "machine gate OPEN after ${n}×60 s ($(gate_state))"; }
lock_owner=""; hb_pid=""
acquire_lock() {
  local waited=0
  while ! mkdir $LOCK 2>/dev/null; do
    (( waited == 0 )) && log "CHROME.lock held ($(cat $LOCK/owner 2>/dev/null || echo 'no marker')) — waiting (poll 5 s)"
    (( waited > 0 && waited % 600 == 0 )) && log "still waiting for CHROME.lock (${waited}s; holder: $(cat $LOCK/owner 2>/dev/null || echo ?))"
    sleep 5; waited=$((waited+5))
  done
  lock_owner="R5G pair $1 $$ $(date '+%F %T')"; echo "$lock_owner" > $LOCK/owner
  ( while [[ -d $LOCK ]] && kill -0 $$ 2>/dev/null; do touch -c $LOCK; sleep 30; done ) & hb_pid=$!
  log "CHROME.lock acquired ('$lock_owner') after ${waited}s ($(gate_state))"
}
release_lock() {
  [[ -n $hb_pid ]] && kill $hb_pid 2>/dev/null; hb_pid=""
  if [[ -n $lock_owner && -d $LOCK && "$(cat $LOCK/owner 2>/dev/null)" == "$lock_owner" ]]; then
    rm -f $LOCK/owner; rmdir $LOCK 2>/dev/null && log "CHROME.lock released ('$lock_owner')" || log "rmdir CHROME.lock FAILED: $(ls -la $LOCK 2>&1 | tr '\n' ' ')"
  fi
  lock_owner=""
}
on_term() { log "TERM/INT — killing my harness child (it kills its node/Chrome), releasing the lock"; pkill -TERM -f "$D/run_bench_r5g.sh" 2>/dev/null; sleep 3; release_lock; }
trap 'on_term; exit 130' INT TERM
run_held() { # run_held <label> <arm: ref|flag>
  local l=$1 arm=$2 rc
  if [[ $arm == ref ]]; then
    log "$arm run — run_bench_r5g.sh combined7 $l 1 0 (no extra flags; $(gate_state))"
    env -u R5G_JS_FLAGS -u R5G_EXTRA_ARGS R5G_LOCK_HELD=1 R5G_LOCK_OWNER="$lock_owner" $D/run_bench_r5g.sh combined7 $l 1 0 600000 > $D/out-$l.txt 2>&1; rc=$?
  else
    log "$arm run — run_bench_r5g.sh combined7 $l 1 0 (R5G_JS_FLAGS='${CAND_JS_FLAGS-}' R5G_EXTRA_ARGS='${CAND_EXTRA_ARGS-}'; $(gate_state))"
    if [[ -n ${CAND_JS_FLAGS-} ]]; then export R5G_JS_FLAGS="$CAND_JS_FLAGS"; else unset R5G_JS_FLAGS; fi
    if [[ -n ${CAND_EXTRA_ARGS-} ]]; then export R5G_EXTRA_ARGS="$CAND_EXTRA_ARGS"; else unset R5G_EXTRA_ARGS; fi
    R5G_LOCK_HELD=1 R5G_LOCK_OWNER="$lock_owner" $D/run_bench_r5g.sh combined7 $l 1 0 600000 > $D/out-$l.txt 2>&1; rc=$?
    unset R5G_JS_FLAGS R5G_EXTRA_ARGS
  fi
  if (( rc == 0 )); then log "$arm run done rc=0: $(python3 $W/B0/summarize_run.py $D/runs/combined7/$l.json --oneline 2>&1 | tail -1 | cut -c1-300)"
  else log "$arm run rc=$rc (8 = gate closed >10 min under the lock, 4 = battery/server, 3 = foreign Chrome, 7 = lock not ours): $(tail -2 $D/out-$l.txt | tr '\n' ' ' | cut -c1-200)"; fi
  return $rc
}
for attempt in 1 2 3; do
  l=$label; (( attempt > 1 )) && l="$label-r$attempt"
  wait_gate
  acquire_lock $l
  run_held $l-ref ref; rc=$?
  (( rc == 0 )) && { run_held $l-flag flag; rc=$?; }
  release_lock
  (( rc == 0 )) && { log "pair $l complete"; exit 0; }
  log "pair $l failed (rc=$rc), attempt $attempt/3 — waiting 60 s before retry"
  sleep 60
done
log "pair $label ABANDONED after 3 attempts"; exit 1
