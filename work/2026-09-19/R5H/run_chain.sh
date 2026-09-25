#!/bin/zsh
# R5H Chrome chain: waits for >= 3 GB free disk (PLAN-round5 rule), then under CHROME.lock (with_lock.sh: AC required, owner marker,
# touch -c 30 s, 5 s poll): (1) smoke trio smoke-R5H-2L / -r4s / -off (light trace, one lock hold), (2) ONE 8-token correctness run of
# bundles/R5H (+ verify), (3) ONE 32-token prompt-40 run of bundles/R5H-c32 (bench_native.mjs, RSS per token). Retries on disk/battery refusals.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W
logline() { echo "- $(date '+%F %T') [R5H chain] $*" >> $W/R5H.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { (( $(df -g $W | tail -1 | awk '{print $4}') >= ${MIN_FREE_GB:-3} )) && (( $(swap_used_mb) < ${MAX_SWAP_MB:-3000} )) && on_ac; }
# coordinator 12:5x: no Chrome until free disk >= 3.0 GB AND swap used < 3,000 MB AND AC (swap files grew to 6.4 GB and crashed R5A's Chrome); poll 60 s
wait_disk() { local said=0; while ! gate_ok; do (( said == 0 )) && { logline "gate: waiting for disk >= ${MIN_FREE_GB:-3} GB (now $(df -g $W | tail -1 | awk '{print $4}')), swap used < ${MAX_SWAP_MB:-3000} MB (now $(swap_used_mb)), AC ($(pmset -g batt | head -1 | grep -c 'AC Power')); polling every 60 s"; said=1; }; sleep 60; done; logline "gate open: disk $(df -g $W | tail -1 | awk '{print $4}') GB, swap used $(swap_used_mb) MB, AC"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_disk; $W/R5H/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: disk/battery) — retrying in 60 s"; sleep 60; done; }
logline "chain (re-armed; gate disk >= ${MIN_FREE_GB:-3} GB, swap used < ${MAX_SWAP_MB:-3000} MB, AC) start; swap=$(sysctl -n vm.swapusage) disk_free_GB=$(df -g $W | tail -1 | awk '{print $4}') lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"
run smoke-trio 1200 zsh -c 'for b in smoke-R5H-2L smoke-R5H-2L-r4s smoke-R5H-2L-off; do echo "== $b"; TRACE=1 CAP_MS=240000 /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R5H/smoke_inner.sh $b $b 2; done' > $W/R5H/logs/chain-smoke.out 2>&1
logline "smoke trio rc=$? -> R5H/logs/chain-smoke.out"; touch $W/R5H/SMOKE-DONE
run correctness-R5H 1500 $W/R5H/correctness_inner.sh R5H > $W/R5H/logs/chain-correctness.out 2>&1
crc=$?; logline "correctness rc=$crc -> R5H/logs/chain-correctness.out"; touch $W/R5H/CORRECTNESS-DONE
# READY only on 8/8 ids + verify rc 0 (as planned)
ids=$(grep -o '"tokens":\[[^]]*\]' $W/R5H/run-R5H/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $W/R5H/logs/chain-correctness.out | tail -1)
if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then
  echo "R5H READY $(date '+%F %T'): ids 8/8 [11,314,1101,7926,11,475,314,1101], $vrc, run R5H/run-R5H (harness.log, verify.log)" > $W/bundles/R5H/READY; logline "bundles/R5H/READY created ($ids $vrc)"
else logline "NO READY: ids=$ids $vrc"; fi
# smoke trace hygiene: traces are gzipped by run_bundle.mjs; warn if any exceeds 200 MB
for t in $W/R5H/runs/*/trace.json.gz; do [[ -f $t ]] && (( $(stat -f %z $t) > 200000000 )) && logline "WARNING trace $t > 200 MB"; done; rm -f $W/R5H/runs/*/trace.json 2>/dev/null
B0_PROMPT_TOKEN=40 REF_JSON=$W/R4P/reference_ids_32_40.json run c32-R5H-c32 2760 $W/R5H/c32_inner.sh R5H-c32 c32-p40 2400000 > $W/R5H/logs/chain-c32.out 2>&1
c32rc=$?; logline "c32 rc=$c32rc -> R5H/logs/chain-c32.out"
# append the c32 verdict to R5H.md §5
sm=$W/R5H/run-R5H-c32/c32-p40.summary.md
if [[ -f $sm ]]; then
  { echo; echo "### 5.4 c32 run (auto-appended by run_chain.sh $(date '+%F %T'); node rc=$c32rc)"; echo; sed -n 1,4p $sm; echo; echo "RecalcStyleCount per token (must be flat ≈ 84): $(grep -E '^\| *[0-9]+ \|' $sm | awk -F'|' '{printf "%s ", $7}')"; echo; echo "RSS max MB per token: $(grep -E '^\| *[0-9]+ \|' $sm | awk -F'|' '{printf "%s ", $12}')"; echo; echo "Memory state (before/after, R5H/run-R5H-c32/c32-p40.memstate.txt):"; echo '```'; cat $W/R5H/run-R5H-c32/c32-p40.memstate.txt; echo '```'; echo; echo "Full table: \`R5H/run-R5H-c32/c32-p40.summary.md\`."; } >> $W/R5H.md
  logline "c32 verdict appended to R5H.md §5"
else logline "c32: no summary produced"; fi
touch $W/R5H/CHAIN-DONE
