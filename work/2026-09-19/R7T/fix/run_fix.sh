#!/bin/zsh
# R7T fixture under the Chromium mutex. Gate: AC AND disk >= 4 GB AND swap used < 4000 MB AND load1 < 6; lock protocol: mkdir CHROME.lock,
# owner "R7T <what> <pid> <time>", touch -c every 30 s, rmdir only mine, poll 5 s. usage: run_fix.sh <tag> [run_fix.mjs args...]
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
tag=${1:-fix}; shift || true
logline() { echo "- $(date '+%F %T') [R7T fixture/$tag] $*" >> $W/R7T.log.md; echo "$(date '+%T') $*"; }
OWNER="R7T fixture-$tag $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R7T fixture-$tag $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner is $(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner')"; fi; }
gate() { local ac disk swap load
  ac=$(pmset -g batt | grep -c "AC Power"); disk=$(df -g / | awk 'NR==2{print $4}'); swap=$(sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1); load=$(sysctl -n vm.loadavg | awk '{print $2}' | cut -d. -f1)
  GATE="AC=$ac disk=${disk}GB swap_used=${swap}MB load1=$load"; (( ac >= 1 && disk >= 4 && swap < 4000 && load < 6 )); }
waited=0
while true; do
  until gate; do (( waited % 60 == 0 )) && logline "gate closed ($GATE), polling"; sleep 5; waited=$((waited+5)); done
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited % 60 == 0 )) && logline "CHROME.lock held ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'no owner')), polling every 5 s"; sleep 5; waited=$((waited+5)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 20); do pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null || break; sleep 3; waited=$((waited+3)); done
  if pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null; then logline "lock acquired but a foreign headless Chrome still runs after 60 s — releasing"; release; sleep 5; continue; fi
  gate && break; logline "lock acquired but gate closed ($GATE) — releasing"; release; sleep 5
done
trap 'release' EXIT INT TERM
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
logline "START (waited ${waited}s) $GATE args='$*'"
mkdir -p $W/R7T/fix/results
caffeinate -dims $NODE $W/R7T/fix/run_fix.mjs --out $W/R7T/fix/results/$tag.jsonl "$@" > $W/R7T/fix/results/$tag.stdout.log 2>&1; rc=$?
pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null && { logline "headless Chrome still alive, killing"; pkill -f '^/Applications/.*Google Chrome .*--headless'; sleep 2; }
release; trap - EXIT INT TERM
logline "END rc=$rc load='$(sysctl -n vm.loadavg)' -> R7T/fix/results/$tag.{jsonl,stdout.log}"
touch $W/R7T/fix/results/$tag.DONE; exit $rc
