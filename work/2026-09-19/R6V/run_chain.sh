#!/bin/zsh
# R6V Chrome chain (= R5X/run_chain.sh protocol): waits for the machine gate (AC AND ((disk >= 4 GB AND swap < 4,000 MB) OR (disk >= 3 GB AND swap < 3,000 MB)); poll 60 s),
# then, each under its own CHROME.lock hold (with_lock.sh: owner "R6V <label> <pid> <time>", touch -c 30 s, 5 s poll, rmdir only own):
# (1) smoke trio smoke-R6V-2L-ref / smoke-R6V-2L / smoke-R6V-2L-nosmooth (2 layers, 2 tokens, light trace, screenshots) -> R6V/runs/<b>/frames.md;
# (2) load-paint probe of combined8-ui (+ Run, mid-token screenshots) and of combined8 (reference load) -> R6V/runs/loadpaint-*;
# (3) ONE passive 8-token correctness run of bundles/combined8-ui (+ verify with R6V tools) -> READY only on 8/8 ids + verify rc 0.
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
logline() { echo "- $(date '+%F %T') [R6V chain] $*" >> $W/R6V.log.md; echo "$(date '+%T') $*"; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
gate_ok() { on_ac && { { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); } || { (( $(free_gb) >= 3 )) && (( $(swap_used_mb) < 3000 )); }; }; }
state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB lock=$(cat $W/CHROME.lock/owner 2>/dev/null || echo free)"; }
wait_gate() { local n=0; while ! gate_ok; do (( n % 10 == 0 )) && logline "gate closed, waiting ($(state)); poll 60 s"; n=$((n+1)); sleep 60; done; logline "gate open ($(state))"; }
run() { local label=$1 cap=$2; shift 2; while true; do wait_gate; $W/R6V/with_lock.sh $label $cap "$@"; local rc=$?; (( rc == 8 || rc == 9 )) || return $rc; logline "$label refused (rc=$rc: gate/battery) — retrying in 60 s"; sleep 60; done; }
logline "chain armed ($(state))"
if [[ ! -f $W/R6V/SMOKE-DONE ]]; then
  run smoke-trio 1500 zsh -c 'for b in smoke-R6V-2L-ref smoke-R6V-2L smoke-R6V-2L-nosmooth; do echo "== $b"; TRACE=1 CAP_MS=240000 /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6V/smoke_inner.sh $b $b 2; done' > $W/R6V/logs/chain-smoke.out 2>&1
  logline "smoke trio rc=$? -> R6V/logs/chain-smoke.out: $(grep -h '"final"' $W/R6V/runs/smoke-R6V-2L*/harness.log | grep -o '"tokens":\[[^]]*\]' | tr '\n' ' ')"; touch $W/R6V/SMOKE-DONE
  { echo; echo "## 4a. Chrome results — smoke trio (auto-appended by R6V/run_chain.sh $(date '+%F %T'); runs R6V/runs/smoke-R6V-2L{-ref,,-nosmooth}/: harness.log, frames.md, shot-*.png)"; echo; python3 $W/R6V/compare_smoke.py $W/R6V/runs/smoke-R6V-2L-ref $W/R6V/runs/smoke-R6V-2L $W/R6V/runs/smoke-R6V-2L-nosmooth 2>&1; } >> $W/R6V.md
fi
if [[ ! -f $W/R6V/LOADPAINT-DONE ]]; then
  run loadpaint 900 zsh -c 'for a in "combined8-ui 1" "combined8 0"; do echo "== $a"; /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6V/loadpaint_inner.sh ${=a}; done' > $W/R6V/logs/chain-loadpaint.out 2>&1
  logline "loadpaint rc=$? -> R6V/logs/chain-loadpaint.out"; touch $W/R6V/LOADPAINT-DONE
  { echo; echo "## 4b. Chrome results — load-paint probe (auto-appended $(date '+%F %T'); screenshots R6V/runs/loadpaint-combined8-ui/shot-*.png, R6V/runs/loadpaint-combined8/shot-*.png)"; echo; echo '```'; for b in combined8-ui combined8; do echo "== $b"; grep -h '"state"\|"load-event"\|"fonts-loaded"\|"screenshot"' $W/R6V/runs/loadpaint-$b/harness.log | cut -c1-400; done; echo '```'; } >> $W/R6V.md
fi
run correctness-combined8-ui 1500 $W/R6V/correctness_inner.sh combined8-ui > $W/R6V/logs/chain-correctness.out 2>&1
crc=$?; logline "correctness rc=$crc -> R6V/logs/chain-correctness.out"; touch $W/R6V/CORRECTNESS-DONE
ids=$(grep -o '"tokens":\[[^]]*\]' $W/R6V/run-combined8-ui/harness.log | tail -1); vrc=$(grep -o 'verify rc=[0-9]*' $W/R6V/logs/chain-correctness.out | tail -1)
if [[ $ids == '"tokens":[11,314,1101,7926,11,475,314,1101]' && $vrc == "verify rc=0" ]]; then
  echo "combined8-ui READY $(date '+%F %T'): ids 8/8 [11,314,1101,7926,11,475,314,1101], $vrc, run R6V/run-combined8-ui (harness.log, verify.log); = combined8 + R6V progress UI (display-only)" > $W/bundles/combined8-ui/READY; logline "bundles/combined8-ui/READY created ($ids $vrc)"
else logline "NO READY for combined8-ui: ids=$ids $vrc"; fi
{ echo; echo "## 4c. Chrome results — ONE 8-token correctness run of combined8-ui (auto-appended $(date '+%F %T'); R6V/run-combined8-ui/)"; echo; echo '```'; grep -h '"loaded"\|"token-captured"\|"metrics-after"\|"final"' $W/R6V/run-combined8-ui/harness.log | cut -c1-500; echo "verify: $(grep -o 'verify rc=[0-9]*.*' $W/R6V/logs/chain-correctness.out | tail -1 | cut -c1-400)"; echo "RSS renderer peak MB: $(awk '$2>m{m=$2} END{print m}' $W/R6V/run-combined8-ui/rss-renderer.log)"; echo "READY: $(cat $W/bundles/combined8-ui/READY 2>/dev/null || echo none)"; echo '```'; } >> $W/R6V.md
touch $W/R6V/CHAIN-DONE
