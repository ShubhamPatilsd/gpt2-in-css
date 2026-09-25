#!/bin/zsh
# R5C Chrome session under the Chromium mutex (PLAN.md + round-4/5 rules): mkdir CHROME.lock (poll 5 s), owner marker
# "R5C <what> <pid> <time>", touch -c every 30 s, rmdir ONLY if the marker is mine, refuse while a foreign headless Chrome runs.
# Round-5 gate (coordinator 12:5x): AC power AND free disk >= 3.0 GB AND vm.swapusage used < 3000 MB, polled every 60 s BEFORE taking the lock.
# usage: run_chrome.sh <label> <wall-cap-s> <command...>   (the command writes its own outputs)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
label=$1; cap=$2; shift 2
CHROME='^/Applications/Google Chrome.app/Contents/MacOS/Google Chrome .*--headless'
logline() { echo "- $(date '+%F %T') [R5C chrome/$label] $*" >> $W/R5C.log.md; echo "$(date '+%T') $*"; }
gate() {  # 0 = ok
  local free_gb swap_used ac
  free_gb=$(df -g $W | awk 'NR==2{print $4}')
  swap_used=$(sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1)
  ac=$(pmset -g batt | head -1 | grep -c "AC Power")
  GATE_MSG="free ${free_gb} GB, swap used ${swap_used} MB, AC=${ac}"
  (( free_gb >= 3 && swap_used < 3000 && ac == 1 ))
}
OWNER="R5C $label $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "^R5C $label $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner'))"; fi; }
waited=0; gwaited=0
while ! gate; do (( gwaited == 0 )) && logline "machine gate not met ($GATE_MSG), polling every 60 s"; sleep 60; gwaited=$((gwaited+60)); done
logline "machine gate met ($GATE_MSG) after ${gwaited}s"
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($( [[ -f $W/CHROME.lock ]] && echo 'plain FILE' || cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner')), polling every 5 s"; sleep 5; waited=$((waited+5)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f "$CHROME" >/dev/null || break; sleep 3; waited=$((waited+3)); done
  if pgrep -f "$CHROME" >/dev/null; then logline "lock acquired but a foreign Chrome still runs after 90 s — releasing, back to polling"; release; sleep 5; continue; fi
  if ! gate; then logline "lock acquired but the machine gate lapsed ($GATE_MSG) — releasing, back to the gate"; release; while ! gate; do sleep 60; done; continue; fi
  break
done
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
trap 'release; [[ -n ${npid:-} ]] && kill $npid 2>/dev/null' EXIT INT TERM
logline "START (waited lock ${waited}s) $GATE_MSG power=$(pmset -g batt | sed -n 2p | tr -s "\t" " " | cut -c1-60) load=$(sysctl -n vm.loadavg): $*"
"$@" & npid=$!
t0=$(date +%s); seen=0; gone=0; why=""
while kill -0 $npid 2>/dev/null; do
  sleep 5; now=$(date +%s)
  if pgrep -f "$CHROME" >/dev/null; then seen=1; gone=0
  elif (( seen )); then (( gone == 0 )) && gone=$now; (( now - gone >= 60 )) && { why="Chrome gone 60 s, node alive (hung close)"; break; }
  fi
  (( now - t0 >= cap )) && { why="wall cap ${cap}s"; break; }
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
pgrep -f "$CHROME" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "$CHROME"; sleep 2; }
release; trap - EXIT INT TERM
logline "END rc=$rc; free $(df -g $W | awk 'NR==2{print $4}') GB, $(sysctl -n vm.swapusage | cut -c1-60)"
exit $rc
