#!/bin/zsh
# R7X Chrome chain (each step under R7X/with_lock.sh: gate AC AND load1<6 AND ((disk>=6 AND swap<6000) OR (disk>=4 AND swap<4000)); rc 8/9 -> retry in 60 s).
# Waits for R7B's two armed sampled runs (R7B/CHAIN-3-DONE, or R7B/run_chain3.sh gone) before its first Chrome. Steps resumable via DONE markers. Log: R7X.log.md; outputs R7X/run-*/.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7X; cd $W
logline() { echo "- $(date '+%F %T') [R7X chain] $*" >> $W/R7X.log.md; echo "$(date '+%T') $*"; }
run() { local label=$1 cap=$2; shift 2; local n=0; while true; do $R/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; (( n % 30 == 0 )) && logline "$label refused (rc=$rc: $( (( rc == 9 )) && echo battery || echo gate)) — retrying every 60 s"; n=$((n+1)); sleep 60; done; }
summ() { local f=$1; grep -h '^ids \|^NEW tokens\|^first mismatch' $f 2>/dev/null | tr '\n' ' ' | cut -c1-260; }
gs() { grep -o '"guard-state".*' $1 2>/dev/null | tail -1 | python3 -c "import sys,json,re; s=sys.stdin.read(); j=json.loads(s[s.index('{'):]) if '{' in s else {}; ts=j.get('tokenState',{}); print('fb-ok', ts.get('fbOk'), 'agree-all-1', all(a=='1' for a in ts.get('agree',[]) if a not in ('','0.0')) if ts.get('agree') else None, 'scroller', j.get('scroller',{}).get('clientWidth'), j.get('scroller',{}).get('scrollbarWidth'), 'warn', (j.get('warn') or {}).get('display'), 'status', j.get('status'))" 2>/dev/null; }
rs() { grep -o '"r7b-state".*' $1 2>/dev/null | tail -1 | cut -c1-330; }
n=0; while [[ ! -f $W/R7B/CHAIN-3-DONE ]] && pgrep -f "R7B/run_chain3.sh" >/dev/null; do (( n % 30 == 0 )) && logline "waiting for R7B's sampled runs (R7B/run_chain3.sh alive, CHAIN-3-DONE absent; power '$(pmset -g batt | sed -n 2p | tr -s '\t' ' ' | cut -c1-60)')"; n=$((n+1)); sleep 60; done
logline "R7B chain finished or gone ($( [[ -f $W/R7B/CHAIN-3-DONE ]] && echo CHAIN-3-DONE || echo 'run_chain3.sh not running')) — starting the R7X Chrome steps"
# 1. 2-layer merged smoke, HEADED + scrollbars, typed "Once upon a time" T=0 -> 35 epochs (guard + prefill skip + stop rule interplay, cheap)
if [[ ! -f $R/DONE-smoke ]]; then
  B0_TYPED_PROMPT="Once upon a time" B0_TYPED_IDS='[7454,2402,257,640]' B0_STOP_TOKEN=35 REF_JSON=$W/R7B/reference_once-upon-a-time_s0_t0_2L.json R7H_SHOW_SCROLLBARS=1 B0_HEADED=1 B0_VIEWPORT=1100x700 run smoke-once-headed 900 $R/inner.sh smoke-r7x-2L once-t0-headed-scrollbars 700000 36 > $R/logs/chain-smoke.out 2>&1; rc=$?
  logline "smoke-r7x-2L HEADED+scrollbars typed Once T=0 rc=$rc: $(summ $R/run-smoke-r7x-2L/once-t0-headed-scrollbars.summary.md) | $(gs $R/run-smoke-r7x-2L/once-t0-headed-scrollbars.stdout.log) | $(rs $R/run-smoke-r7x-2L/once-t0-headed-scrollbars.stdout.log)"; (( rc == 0 )) && touch $R/DONE-smoke
fi
# 2. demo-8.next dropdown Hello, headless -> 8/8
if [[ ! -f $R/DONE-demo8 ]]; then
  B0_STOP_TOKEN=8 REF_JSON=$W/R7B/reference_hello_s0_t0_cap8.json run demo8-hello 900 $R/inner.sh demo-8.next hello-headless 600000 8 > $R/logs/chain-demo8.out 2>&1; rc=$?
  logline "demo-8.next Hello headless rc=$rc: $(summ $R/run-demo-8.next/hello-headless.summary.md) | $(gs $R/run-demo-8.next/hello-headless.stdout.log) | $(rs $R/run-demo-8.next/hello-headless.stdout.log)"; (( rc == 0 )) && touch $R/DONE-demo8
fi
# 3. demo-c32.next HEADED 1100x700, scrollbars SHOWN, typed "Shubham was" T=0 -> 35 epochs (32 new tokens); shots mid-prefill + mid-run
if [[ ! -f $R/DONE-c32-shubham ]]; then
  B0_TYPED_PROMPT="Shubham was" B0_TYPED_IDS='[2484,549,2763,373]' B0_STOP_TOKEN=35 REF_JSON=$W/R7B/reference_shubham-was_s0_t0.json R7H_SHOW_SCROLLBARS=1 B0_HEADED=1 B0_VIEWPORT=1100x700 B0_SHOTS=8,20,30,300 run c32-shubham-headed 2760 $R/inner.sh demo-c32.next shubham-headed-scrollbars 2500000 36 > $R/logs/chain-c32-shubham.out 2>&1; rc=$?
  logline "demo-c32.next HEADED+scrollbars typed 'Shubham was' T=0 rc=$rc: $(summ $R/run-demo-c32.next/shubham-headed-scrollbars.summary.md) | $(gs $R/run-demo-c32.next/shubham-headed-scrollbars.stdout.log) | $(rs $R/run-demo-c32.next/shubham-headed-scrollbars.stdout.log) | $(grep -o 'total .*' $R/run-demo-c32.next/shubham-headed-scrollbars.summary.md)"; (( rc == 0 )) && touch $R/DONE-c32-shubham
fi
# 4. demo-c32.next headless typed "I" T=0 -> 32 epochs
if [[ ! -f $R/DONE-c32-I ]]; then
  B0_TYPED_PROMPT="I" B0_TYPED_IDS='[40]' B0_STOP_TOKEN=32 REF_JSON=$W/R7B/reference_I_s0_t0.json run c32-I-headless 2760 $R/inner.sh demo-c32.next I-headless 2500000 36 > $R/logs/chain-c32-I.out 2>&1; rc=$?
  logline "demo-c32.next headless typed 'I' T=0 rc=$rc: $(summ $R/run-demo-c32.next/I-headless.summary.md) | $(gs $R/run-demo-c32.next/I-headless.stdout.log) | $(rs $R/run-demo-c32.next/I-headless.stdout.log) | $(grep -o 'total .*' $R/run-demo-c32.next/I-headless.summary.md)"; (( rc == 0 )) && touch $R/DONE-c32-I
fi
# 5. demo-c32.next dropdown Hello, seed 17 T=1.0 (selects), HEADED + scrollbars -> 32 epochs vs R7X/reference_hello_s17_t1.0.json
if [[ ! -f $R/DONE-c32-hello-s17 ]]; then
  B0_SEED=17 B0_TEMP=1 B0_STOP_TOKEN=32 REF_JSON=$R/reference_hello_s17_t1.0.json R7H_SHOW_SCROLLBARS=1 B0_HEADED=1 B0_VIEWPORT=1100x700 B0_SHOTS=30 run c32-hello-s17-headed 2760 $R/inner.sh demo-c32.next hello-s17-t1-headed-scrollbars 2500000 36 > $R/logs/chain-c32-hello-s17.out 2>&1; rc=$?
  logline "demo-c32.next HEADED+scrollbars Hello seed 17 T=1.0 rc=$rc: $(summ $R/run-demo-c32.next/hello-s17-t1-headed-scrollbars.summary.md) | $(gs $R/run-demo-c32.next/hello-s17-t1-headed-scrollbars.stdout.log) | $(rs $R/run-demo-c32.next/hello-s17-t1-headed-scrollbars.stdout.log) | $(grep -o 'total .*' $R/run-demo-c32.next/hello-s17-t1-headed-scrollbars.summary.md)"; (( rc == 0 )) && touch $R/DONE-c32-hello-s17
fi
# 6. load-paint probe (R6X/loadpaint.mjs): Ready time, shot-ready (controls incl. seed/temperature), typed, mid-prefill shots 5/12/25/40 s ("absorbing prompt token k of N"), one head shot; stops after 70 s
if [[ ! -f $R/DONE-loadpaint ]]; then
  R6X_TYPED="Shubham was" R6X_SHOTS="5,12,25,40" R6X_WAIT_MS=70000 R6X_VIEWPORT=1100x700 R6X_HEAD_SHOTS=1 R6X_CAPACITY=36 run loadpaint 400 $R/loadpaint_inner.sh demo-c32.next 1 1100x700 > $R/logs/chain-loadpaint.out 2>&1; rc=$?
  logline "load-paint probe demo-c32.next rc=$rc: $(grep -h '"fonts-loaded"\|"load-event"' $R/run-loadpaint-demo-c32.next-1100x700/harness.log | cut -c1-200 | tr '\n' ' ') | states: $(grep -h '"state"' $R/run-loadpaint-demo-c32.next-1100x700/harness.log | grep -o '"tag":"[^"]*"\|"progress":"[^"]*"\|"status":"[^"]*"' | tr '\n' ' ' | cut -c1-500)"; (( rc == 0 )) && touch $R/DONE-loadpaint
fi
ok=1; for m in smoke demo8 c32-shubham c32-I c32-hello-s17 loadpaint; do [[ -f $R/DONE-$m ]] || ok=0; done
logline "chain done (all steps rc 0: $ok) — swap is manual after review"; touch $R/CHAIN-DONE
