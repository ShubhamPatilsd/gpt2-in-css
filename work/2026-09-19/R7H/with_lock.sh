#!/bin/zsh
# R7H Chrome/build session under the Chromium mutex (= R6X/with_lock.sh with the R7H owner marker and the round-7 gate: AC AND load1 < 6 AND ((disk >= 6 GB AND swap < 6,000 MB) OR (disk >= 4 GB AND swap < 4,000 MB)))
# gate (before ANY Chrome): AC AND ((disk >= 4 GB AND swap used < 4,000 MB) OR (disk >= 3 GB AND swap used < 3,000 MB));
# lock: mkdir CHROME.lock (poll 5 s), owner marker "R6X <label> <pid> <time>", touch -c every 30 s, rmdir ONLY if the marker is mine
# (toucher killed first), an existing lock FILE counts as held and is never removed; refuse while a foreign headless Chrome runs;
# power re-checked every 30 s (battery -> abort = INVALID); watchdog (wall cap + Chrome-gone-60-s); kill own children on exit.
# usage: with_lock.sh <label> <wall-cap-s> <command...>   (waits for the gate, poll 60 s; rc 8 = gate closed after acquiring, rc 9 = battery; the command writes its own outputs)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
label=$1; cap=$2; shift 2
CHROME='^/Applications/.*Google Chrome .*--headless'
logline() { echo "- $(date '+%F %T') [R7H chrome/$label] $*" >> $W/R7H.log.md; echo "$(date '+%T') $*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
load1() { sysctl -n vm.loadavg | awk '{print int($2)}'; }
gate_ok() { on_ac && (( $(load1) < 6 )) && { { (( $(free_gb) >= 6 )) && (( $(swap_used_mb) < 6000 )); } || { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 4000 )); }; }; }  # coordinator 15:0x: swap is R7B's c36 renderer, disk is safe
gate_state() { echo "AC=$(on_ac && echo 1 || echo 0) disk=$(free_gb)GB swap_used=$(swap_used_mb)MB load1=$(load1)"; }
gw=0; while ! gate_ok; do (( gw % 15 == 0 )) && logline "waiting for the gate ($(gate_state) load=$(sysctl -n vm.loadavg))"; sleep 60; gw=$((gw+1)); done
on_ac || { logline "NOT on AC power — refusing"; exit 9; }
OWNER="R7H $label $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "^R7H $label $$ " $W/CHROME.lock/owner; }
tpid=; npid=
release() { [[ -n $tpid ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner is not mine ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner'))"; fi; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($( [[ -f $W/CHROME.lock ]] && echo 'plain FILE' || cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner')), polling every 5 s"; sleep 5; waited=$((waited+5)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f "$CHROME" >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f "$CHROME" >/dev/null || break
  logline "lock acquired but a foreign Chrome still runs after 90 s — releasing, back to polling"; release; sleep 5
done
while ! gate_ok; do logline "gate closed after acquiring the lock ($(gate_state)) — releasing, back to waiting"; release; sleep 60
  gw=0; while ! gate_ok; do (( gw % 15 == 0 )) && logline "waiting for the gate ($(gate_state))"; sleep 60; gw=$((gw+1)); done
  while ! mkdir $W/CHROME.lock 2>/dev/null; do sleep 5; done; echo "$OWNER" > $W/CHROME.lock/owner
done
trap 'logline "signal: cleaning up"; [[ -n $npid ]] && { pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; }; pkill -f "$CHROME" 2>/dev/null; release; exit 130' INT TERM
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
logline "START (waited ${waited}s) power='$(pmset -g batt | sed -n 2p | tr -s "\t" " " | cut -c1-70)' load=$(sysctl -n vm.loadavg) $(gate_state) swap='$(sysctl -n vm.swapusage)' free_pages=$(vm_stat | awk '/Pages free/{print $3}'): $*"
"$@" & npid=$!
t0=$(date +%s); seen=0; gone=0; why=""; lastpow=$t0
while kill -0 $npid 2>/dev/null; do
  sleep 5; now=$(date +%s)
  if pgrep -f "$CHROME" >/dev/null; then seen=1; gone=0
  elif (( seen )); then (( gone == 0 )) && gone=$now; (( now - gone >= 60 )) && { why="Chrome gone 60 s, node alive (hung close)"; break; }
  fi
  (( now - t0 >= cap )) && { why="wall cap ${cap}s"; break; }
  if (( now - lastpow >= 30 )); then lastpow=$now; on_ac || { why="POWER FLIPPED TO BATTERY — run INVALID"; break; }; fi
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
pgrep -f "$CHROME" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "$CHROME"; sleep 2; }
release; trap - INT TERM
logline "END rc=$rc power='$(pmset -g batt | sed -n 2p | tr -s "\t" " " | cut -c1-70)' load=$(sysctl -n vm.loadavg) $(gate_state) swap='$(sysctl -n vm.swapusage)'"
exit $rc
