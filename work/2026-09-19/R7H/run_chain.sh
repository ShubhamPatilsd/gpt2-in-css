#!/bin/zsh
# R7H chain: builds under the lock, offline checks, .r7h bundles, then the Chrome steps (each under R7H/with_lock.sh). Log: R7H/logs/chain.out
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R7H; cd $W; mkdir -p $R/logs
logline() { echo "- $(date '+%F %T') [R7H chain] $*" >> $W/R7H.log.md; echo "$(date '+%T') $*"; }
gate_ok() { pmset -g batt | head -1 | grep -q "AC Power" && (( $(sysctl -n vm.loadavg | awk '{print int($2)}') < 6 )) && { d=$(df -g $W | tail -1 | awk '{print $4}'); sw=$(sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1); { (( d >= 6 )) && (( sw < 6000 )); } || { (( d >= 4 )) && (( sw < 4000 )); }; }; }
wait_gate() { local n=0; while ! gate_ok || [[ -e $W/CHROME.lock ]]; do (( n % 15 == 0 )) && logline "waiting for gate open AND lock free ($(sysctl -n vm.loadavg) lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free))"; sleep 60; n=$((n+1)); done; }
run() { local label=$1 cap=$2; shift 2; $R/with_lock.sh $label $cap "$@"; }
okrc() { (( $1 != 8 && $1 != 9 && $1 != 127 )); }
REF2=$W/R6X/reference_ids_shubham_was_2layers.json; TYPED=(B0_TYPED_PROMPT="Shubham was" B0_TYPED_IDS='[2484,549,2763,373]')
if [[ ! -f $R/DONE-build ]]; then
  run build 900 $R/build_all.sh > $R/logs/chain-build.out 2>&1; brc=$?; okrc $brc || { logline "build gate refused rc=$brc — chain stops"; exit 1; }; logline "builds rc=$brc $(grep -c '^### .* build ' $R/logs/chain-build.out) started, $(grep -c 'MB$' $R/logs/chain-build.out) finished"
  for b in demo-c32 demo-8; do python3 $W/R6X/compare_rules.py $R/twin-$b-off bundles/$b > $R/logs/compare-$b-off.log 2>&1; logline "flag-off $b vs shipped: $(head -1 $R/logs/compare-$b-off.log) / $(grep -m1 -o 'rules.*' $R/logs/compare-$b-off.log | cut -c1-120)"; done
  for b in demo-c32 demo-8; do python3 $R/check_guard_diff.py $R/twin-$b-on bundles/$b > $R/logs/guard-diff-$b.log 2>&1; logline "guard-on $b vs shipped: $(grep RESULT $R/logs/guard-diff-$b.log) $(grep '^rules:' $R/logs/guard-diff-$b.log | cut -c1-120)"; done
  python3 $R/check_guard_diff.py $R/twin-smoke-2L-on $R/twin-smoke-2L-off > $R/logs/guard-diff-smoke.log 2>&1; logline "guard-on smoke vs off: $(grep RESULT $R/logs/guard-diff-smoke.log)"
  cmp -s $R/twin-smoke-2L-off/index.html $W/R6X/smoke-demo-2L/index.html && logline "smoke-off html == R6X/smoke-demo-2L (v3 twin; css differs by v4-v6 display/scrollbar rules only, not checked)"
  for b in demo-c32 demo-8; do
    python3 $W/../../tools/launch_browser_gpt2.py --check --directory $R/twin-$b-on > $R/logs/static-check-$b-on.log 2>&1; logline "static check $b-on rc=$? $(tr -d '\n' < $R/logs/static-check-$b-on.log | cut -c1-160)"
    rm -rf bundles/$b.r7h; mv $R/twin-$b-on bundles/$b.r7h && cp bundles/$b/BUILD.md bundles/$b.r7h/BUILD.md && logline "bundles/$b.r7h = guard-on build (not swapped in)"
  done
  [[ -d bundles/demo-c32.r7h && -d bundles/demo-8.r7h ]] && touch $R/DONE-build || { logline "build step incomplete — chain stops"; exit 1; }
fi
# (steps run sequentially through with_lock; inner.sh writes run-<bundle>/<label>.*)
for spec in \
  "smoke-off-headless|twin-smoke-2L-off|32|900|R7H_SHOW_SCROLLBARS=0 B0_HEADED=0" \
  "smoke-on-headless|twin-smoke-2L-on|32|900|R7H_SHOW_SCROLLBARS=0 B0_HEADED=0" \
  "smoke-on-headed-scrollbars|twin-smoke-2L-on|32|900|R7H_SHOW_SCROLLBARS=1 B0_HEADED=1 B0_VIEWPORT=1100x700" \
  "smoke-fault-headed-scrollbars|twin-smoke-2L-fault|32|400|R7H_SHOW_SCROLLBARS=1 B0_HEADED=1 B0_VIEWPORT=1100x700 R7H_HELD_S=90 B0_SHOTS=100" ; do
  IFS='|' read -r label bundle cap wall envs <<< "$spec"
  [[ -f $R/DONE-$label ]] && continue
  capms=$(( (wall - 60) * 1000 )); (( capms > 240000 )) || capms=240000
  env ${(z)envs} ${TYPED[@]} REF_JSON=$REF2 $R/with_lock.sh $label $wall $R/inner.sh $bundle $label $capms $cap > $R/logs/chain-$label.out 2>&1; rc=$?
  logline "$label rc=$rc: $(grep -h '^ids ' $R/run-$bundle/$label.summary.md 2>/dev/null | cut -c1-150) | $(grep -o '"guard-state".*' $R/run-$bundle/$label.stdout.log 2>/dev/null | tail -1 | cut -c1-420) | stop=$(grep -o '"stopReason":"[a-z-]*"' $R/run-$bundle/$label.stdout.log | tail -1)"
  okrc $rc && touch $R/DONE-$label
done
if [[ ! -f $R/DONE-stress ]]; then run stress 1800 $R/stress.sh > $R/logs/chain-stress.out 2>&1; rc=$?
  logline "stress rc=$rc: $(for t in off on; do for r in 1 2; do echo -n "$t-$r $(grep -h '^ids ' $R/run-twin-smoke-2L-$t/stress-$t-$r.summary.md 2>/dev/null | grep -o 'ids [0-9]*/[0-9]*') $(python3 -c "import json;d=json.load(open('$R/run-twin-smoke-2L-$t/stress-$t-$r.json'));e=d['tokenEvents'];print(f'{(e[-1][\"sinceRun\"]/1000/len(e)):.1f}s/tok' if e else 'no tokens')" 2>/dev/null); "; done; done)"; okrc $rc && touch $R/DONE-stress; fi
if [[ ! -f $R/DONE-demo8 ]]; then REF_JSON=$W/R4C/reference_ids_32.json R7H_SHOW_SCROLLBARS=0 B0_HEADED=0 $R/with_lock.sh demo8-hello 900 $R/inner.sh demo-8.r7h hello-headless 600000 8 > $R/logs/chain-demo8.out 2>&1; rc=$?
  logline "demo-8.r7h Hello headless rc=$rc: $(grep -h '^ids ' $R/run-demo-8.r7h/hello-headless.summary.md | cut -c1-150) | $(grep -o '"guard-state".*' $R/run-demo-8.r7h/hello-headless.stdout.log | tail -1 | cut -c1-300)"; okrc $rc && touch $R/DONE-demo8; fi
if [[ ! -f $R/DONE-c32-shubham ]]; then env ${TYPED[@]} REF_JSON=$W/R6X/reference_ids_shubham_was.json R7H_SHOW_SCROLLBARS=1 B0_HEADED=1 B0_VIEWPORT=1100x700 B0_SHOTS=30,300 $R/with_lock.sh c32-shubham-headed-scrollbars 2760 $R/inner.sh demo-c32.r7h shubham-headed-scrollbars 2400000 32 > $R/logs/chain-c32-shubham.out 2>&1; rc=$?
  logline "demo-c32.r7h HEADED+scrollbars 'Shubham was' rc=$rc: $(grep -h '^ids \|^first mismatch' $R/run-demo-c32.r7h/shubham-headed-scrollbars.summary.md | tr '\n' ' ' | cut -c1-200) | $(grep -o '"guard-state".*' $R/run-demo-c32.r7h/shubham-headed-scrollbars.stdout.log | tail -1 | cut -c1-300)"; okrc $rc && touch $R/DONE-c32-shubham; fi
if [[ ! -f $R/DONE-c32-I ]]; then B0_TYPED_PROMPT="I" B0_TYPED_IDS='[40]' REF_JSON=$W/R4P/reference_ids_32_40.json R7H_SHOW_SCROLLBARS=0 B0_HEADED=0 $R/with_lock.sh c32-I-headless 2760 $R/inner.sh demo-c32.r7h I-headless 2400000 32 > $R/logs/chain-c32-I.out 2>&1; rc=$?
  logline "demo-c32.r7h headless typed 'I' rc=$rc: $(grep -h '^ids \|^first mismatch' $R/run-demo-c32.r7h/I-headless.summary.md | tr '\n' ' ' | cut -c1-200)"; okrc $rc && touch $R/DONE-c32-I; fi
logline "chain done"; touch $R/CHAIN-DONE
