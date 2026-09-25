#!/bin/zsh
# R5M: run a list of fixtures (label=url pairs from a list file) under ONE CHROME.lock acquisition. Lock discipline = R4D/run_r4d.sh:
# mkdir CHROME.lock, owner marker "R5M fixtures <pid> <time>", touch -c every 30 s, rmdir ONLY if the marker is mine, existing FILE = held.
# usage: run_fixtures.sh <listfile> [gens-default]   listfile lines: label<TAB>path-relative-to-repo<TAB>gens<TAB>settleMs  (gens/settle optional)
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
list=$1; what=${2:-fixtures}
CHROME_RE='^/Applications/.*Google Chrome .*--headless'
logline() { echo "- $(date '+%F %T') [R5M $what] $*" >> $W/R5M.log.md; echo "$(date '+%F %T') $*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
until on_ac; do logline "on battery — waiting 60 s"; sleep 60; done
# Coordinator gate (2026-09-24 12:5x): before ANY Chrome launch wait for AC power AND free disk >= 3.0 GB AND swap used < 3,000 MB; poll 60 s.
machine_ok() { local av=$(df -k / | tail -1 | awk '{print $4}'); local sw=$(sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/' | cut -d. -f1)
  pmset -g batt | head -1 | grep -q "AC Power" && (( av >= 3145728 )) && (( sw < 3000 )); }
gate_wait() { local n=0; until machine_ok; do (( n % 10 == 0 )) && logline "machine gate: waiting (power='$(pmset -g batt | head -1)' disk_free_MB=$(( $(df -k / | tail -1 | awk '{print $4}') / 1024 )) swap='$(sysctl -n vm.swapusage | tr -s ' ')')"; n=$((n+1)); sleep 60; done; }
gate_wait
OWNER="R5M $what $$ $(date '+%F %T')"
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && grep -q "R5M $what $$ " $W/CHROME.lock/owner; }
release() { [[ -n ${tpid:-} ]] && { kill $tpid 2>/dev/null; wait $tpid 2>/dev/null; tpid=; }
  if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null; logline "lock released (owner marker was mine)";
  elif [[ -e $W/CHROME.lock ]]; then logline "NOT releasing CHROME.lock: owner marker is not mine ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'plain file / no owner'))"; fi; }
waited=0
while true; do
  while ! mkdir $W/CHROME.lock 2>/dev/null; do (( waited == 0 )) && logline "CHROME.lock held ($( [[ -f $W/CHROME.lock ]] && echo 'plain FILE' || cat $W/CHROME.lock/owner 2>/dev/null || echo 'dir, no owner')), polling every 5 s"; sleep 5; waited=$((waited+5)); done
  echo "$OWNER" > $W/CHROME.lock/owner
  for _ in $(seq 1 30); do pgrep -f "$CHROME_RE" >/dev/null || break; sleep 3; waited=$((waited+3)); done
  pgrep -f "$CHROME_RE" >/dev/null || break
  logline "lock acquired but a foreign Chrome is still running after 90 s — releasing, back to polling"; release; sleep 15
done
trap 'release; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null; pkill -P $$ 2>/dev/null' EXIT INT TERM
machine_ok || { logline "machine gate failed after lock acquisition — releasing and re-waiting"; release; gate_wait; exec zsh "$0" "$@"; }
( while mine; do touch -c $W/CHROME.lock $W/CHROME.lock/owner 2>/dev/null; sleep 30; done ) & tpid=$!
port=$((47000 + RANDOM % 2000))
# plain static server rooted at the repo (the repo launcher only serves one index.html + its assets; fixtures are many pages)
python3 -m http.server --bind 127.0.0.1 --directory $ROOT $port > $W/R5M/fx-server.log 2>&1 &
spid=$!
for _ in $(seq 1 45); do curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$port/work/2026-09-19/R5M/fx/empty.html" 2>/dev/null | grep -q 200 && break; sleep 2; done
logline "START list=$list waited=${waited}s port=$port load=$(sysctl -n vm.loadavg) swap=$(sysctl -n vm.swapusage | tr -s ' ') power='$(pmset -g batt | sed -n 2p | tr -s "\t" " ")'"
while IFS=$'\t' read -r label rel gens settle; do
  [[ -z $label || $label == \#* ]] && continue
  logline "fixture $label gens=${gens:-0} load1=$(sysctl -n vm.loadavg | cut -d' ' -f2)"
  caffeinate -dims $NODE $W/R5M/fixture.mjs "$label" "http://127.0.0.1:$port/$rel" "${gens:-0}" "${settle:-4000}" > $W/R5M/fx-results/$label.log 2>&1
  logline "  rc=$? $(tail -1 $W/R5M/fx-results/$label.log | cut -c1-300)"
  pgrep -f "$CHROME_RE" >/dev/null && { sleep 3; pgrep -f "$CHROME_RE" >/dev/null && pkill -f "$CHROME_RE"; }
done < $list
kill $spid 2>/dev/null; spid=
release; trap - EXIT INT TERM
logline "END list=$list"
