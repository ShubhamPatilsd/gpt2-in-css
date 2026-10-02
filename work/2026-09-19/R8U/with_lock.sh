#!/bin/zsh
# R7X Chrome session (= R7B/with_lock.sh with the R7X owner marker and log) under the Chromium mutex (= R5H/with_lock.sh with the R7B owner marker and the round-5 machine gate):
# gate (before ANY Chrome): AC AND ((disk >= 4 GB AND swap used < 4,000 MB) OR (disk >= 3 GB AND swap used < 3,000 MB));
# lock: mkdir CHROME.lock (poll 5 s), owner marker "R7B <label> <pid> <time>", touch -c every 30 s, rmdir ONLY if the marker is mine
# (toucher killed first), an existing lock FILE counts as held and is never removed; refuse while a foreign headless Chrome runs;
# power re-checked every 30 s (battery -> abort = INVALID); watchdog (wall cap + Chrome-gone-60-s); kill own children on exit.
# usage: with_lock.sh <label> <wall-cap-s> <command...>   (rc 8 = gate closed, rc 9 = battery; the command writes its own outputs)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
label=$1; cap=$2; shift 2
CHROME='^/Applications/.*Google Chrome .*--headless'
logline() { echo "- $(date '+%F %T') [R8U chrome/$label] $*" >> $W/R8U.log.md; echo "$(date '+%T') $*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
charge() { pmset -g batt | sed -n 2p | grep -oE "[0-9]+%" | tr -d % ; }
power_ok() { on_ac || (( $(charge) >= 40 )); }  # R7X (coordinator 19:1x): correctness runs may run on battery while charge >= 40 %
free_gb() { df -g $W | tail -1 | awk '{print $4}'; }
swap_used_mb() { sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1; }
load1() { sysctl -n vm.loadavg | awk '{print int($2)}'; }
gate_ok() { power_ok && (( $(load1) < 8 )) && { { (( $(free_gb) >= 6 )) && (( $(swap_used_mb) < 6000 )); } || { (( $(free_gb) >= 4 )) && (( $(swap_used_mb) < 5500 )); }; }; }  # R7X gate (coordinator 19:1x): (AC OR charge >= 40 %) AND load1 < 8 AND ((disk >= 6 GB AND swap < 6,000 MB) OR (disk >= 4 GB AND swap < 5,500 MB))
gate_state() { echo "AC=$(on_ac && echo 1 || echo 0) charge=$(charge)% disk=$(free_gb)GB swap_used=$(swap_used_mb)MB load1=$(load1)"; }
power_ok || { logline "battery below 40 % ($(pmset -g batt | sed -n 2p | tr -s '\t' ' ')) — refusing"; exit 9; }
gate_ok || { logline "machine gate closed ($(gate_state)) — refusing"; exit 8; }
OWNER="R8U $label $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "^R8U $label $$ " $W/CHROME.lock/owner; }
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
if ! gate_ok; then logline "gate closed after acquiring the lock ($(gate_state)) — releasing, rc 8"; release; exit 8; fi
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
  if (( now - lastpow >= 30 )); then lastpow=$now; power_ok || { why="battery below 40 % — aborting cleanly (run INVALID)"; break; }; (( $(free_gb) >= 2 )) || { why="disk below 2 GB ($(free_gb) GB) — aborting cleanly"; break; }; fi
done
if [[ -n $why ]]; then logline "WATCHDOG: $why — killing $npid"; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 2; kill -9 $npid 2>/dev/null; rc=124; else wait $npid; rc=$?; fi
pgrep -f "$CHROME" >/dev/null && { logline "Chrome still alive, killing"; pkill -f "$CHROME"; sleep 2; }
release; trap - INT TERM
logline "END rc=$rc power='$(pmset -g batt | sed -n 2p | tr -s "\t" " " | cut -c1-70)' load=$(sysctl -n vm.loadavg) $(gate_state) swap='$(sysctl -n vm.swapusage)'"
exit $rc
