#!/bin/zsh
# R4T fixture under the Chromium mutex (R3M protocol: mkdir CHROME.lock; stamp CHROME.lock/owner; touch -c every 30 s; release = kill toucher first,
# rmdir only if the owner marker is mine; a plain CHROME.lock FILE counts as held; Chrome matched by ^/Applications/.*Google Chrome .*--headless).
# usage: run_r4t.sh <tag> [extra run_r4t.mjs args...]
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
tag=${1:-run}; shift || true
logline() { echo "- $(date '+%F %T') [R4T fixture/$tag] $*" >> $W/R4T.log.md; echo "$*"; }
OWNER="R4T fixture $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R4T fixture $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner'))"; fi; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($( [[ -f $W/CHROME.lock ]] && echo 'plain FILE' || cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner')), polling every 5 s"; sleep 5; waited=$((waited+5)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null || break
  logline "lock acquired but a foreign headless Chrome is still running after 90 s — releasing, back to polling"; release; sleep 5
done
trap 'release' EXIT INT TERM
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
logline "START (waited ${waited}s) load='$(sysctl -n vm.loadavg)' batt='$(pmset -g batt | sed -n 2p | tr -s '\t' ' ')' args='$*'"
cd $W/R4T/fixture
caffeinate -dims $NODE ${MJS:-run_r4t.mjs} --tag $tag "$@" > results/$tag.stdout.log 2>&1
rc=$?
pgrep -f '^/Applications/.*Google Chrome .*--headless' >/dev/null && { logline "headless Chrome still alive, killing"; pkill -f '^/Applications/.*Google Chrome .*--headless'; sleep 2; }
release; trap - EXIT INT TERM
logline "END rc=$rc load='$(sysctl -n vm.loadavg)'"
touch results/$tag.DONE
exit $rc
