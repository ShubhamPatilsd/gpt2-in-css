#!/bin/zsh
# B5 copy of B0/run_bench.sh (2026-09-21). usage: run_bench5.sh <bundle-name> <label> <heap 0|1> <trace 0|1> [cap_ms]
# Differences vs B0/run_bench.sh (everything else byte-for-byte the same protocol: heap flag, passive, AC, disk guard, quiet gate DISABLED,
# 30 s power watchdog, logging into B0.log.md so analyze5.py can read START/END loads):
#   * round-4 CHROME.lock protocol: mkdir, then stamp CHROME.lock/owner ("B5 paired5 <pid> <ts>"), touch -c every 30 s, release with
#     rm owner + rmdir ONLY if the owner marker is ours; a lock FILE counts as held; foreign locks are NEVER removed (stale ones are logged only)
#   * Chrome processes matched with '^/Applications/.*Google Chrome .*--headless' (never the user's own Chrome)
#   * B0_TRIGGER is passed through (paired5.sh exports B0_TRIGGER=keyboard for both arms)
#   * B5_LOCK_DEADLINE_S (optional): give up with rc 6 if CHROME.lock is not acquired within that many seconds (candidate arm only:
#     keeps the ref->cand start gap <= 10 min; the driver then starts a fresh ref+cand pair instead)
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
CHROME_RE='^/Applications/.*Google Chrome .*--headless'
OWNER="B5 paired5 $$ $(date '+%F %T')"
HELD=${B5_LOCK_HELD:-0}   # 1 = the driver already holds CHROME.lock for the whole pair (owner marker B5_LOCK_OWNER); never stamp/touch-create/release it here
bundle=$1; label=$2; heap=$3; trace=$4; cap=${5:-600000}
if [[ $bundle == pinned ]]; then dir=$ROOT/experiments/browser-gpt2/demo-font-vector-twelve; rel=experiments/browser-gpt2/demo-font-vector-twelve
else dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle; fi
out=$W/bench/runs/$bundle; mkdir -p $out
if [[ ${B0_FORCE:-0} != 1 && -f $out/$label.json ]] && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('stopReason') in ('token-limit','eos') else 1)" $out/$label.json 2>/dev/null; then echo "skip $label (complete)"; exit 0; fi
logline() { echo "- $(date '+%Y-%m-%d %H:%M:%S') [$bundle/$label] $*" >> $W/B0.log.md; echo "$*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
wait_ac() { local n=0; while ! on_ac; do (( n % 5 == 0 )) && logline "ON BATTERY ($(pmset -g batt | sed -n 2p | tr -s '\t' ' ')) — timing refused, waiting for AC (poll 60 s)"; sleep 60; n=$((n+1)); done; }
mine() { [[ -d $W/CHROME.lock && -f $W/CHROME.lock/owner ]] && [[ "$(cat $W/CHROME.lock/owner 2>/dev/null)" == "$OWNER" ]]; }
unlock() { (( HELD )) && return; if mine; then rm -f $W/CHROME.lock/owner; rmdir $W/CHROME.lock 2>/dev/null || logline "unlock: rmdir failed: $(ls -la $W/CHROME.lock 2>&1 | tr '\n' ' ')"; fi; }
chrome_alive() { pgrep -f "$CHROME_RE" >/dev/null; }
cleanup() { [[ -n ${npid:-} ]] && { kill $npid 2>/dev/null; sleep 1; pkill -f "$CHROME_RE" 2>/dev/null; }; unlock; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null; [[ -n ${wpid:-} ]] && kill $wpid 2>/dev/null; }
trap 'cleanup' EXIT
trap 'cleanup; trap - EXIT; exit 130' INT TERM
while true; do
  # 1. power (no lock held while waiting)
  wait_ac
  # 2. Chromium mutex (mkdir fails on an existing dir OR file → held); in HELD mode just verify the driver's pair lock
  waited=0
  if (( HELD )); then
    if [[ ! -d $W/CHROME.lock || "$(cat $W/CHROME.lock/owner 2>/dev/null)" != "${B5_LOCK_OWNER:-}" ]]; then logline "B5_LOCK_HELD=1 but CHROME.lock is not ours (expected '${B5_LOCK_OWNER:-}', found '$(cat $W/CHROME.lock/owner 2>/dev/null || echo none)') — abort rc 7"; exit 7; fi
    touch -c $W/CHROME.lock
  fi
  while (( ! HELD )) && ! mkdir $W/CHROME.lock 2>/dev/null; do
    (( waited == 0 )) && logline "CHROME.lock held ($(cat $W/CHROME.lock/owner 2>/dev/null || echo 'no owner marker / lock file')), polling every 5 s"
    if [[ -e $W/CHROME.lock ]] && ! chrome_alive; then
      age=$(( $(date +%s) - $(stat -f %m $W/CHROME.lock 2>/dev/null || date +%s) ))
      (( age > 1200 && waited % 600 == 0 )) && logline "foreign CHROME.lock looks stale (mtime $((age/60)) min old, no headless Chrome alive; owner: $(cat $W/CHROME.lock/owner 2>/dev/null || echo none)) — NOT removing (round-4 rule), still waiting"
    fi
    if (( ${B5_LOCK_DEADLINE_S:-0} > 0 && waited >= ${B5_LOCK_DEADLINE_S} )); then logline "lock deadline ${B5_LOCK_DEADLINE_S}s reached (held by: $(cat $W/CHROME.lock/owner 2>/dev/null || echo ?)) — giving up this run (rc 6) so the driver can start a fresh pair"; exit 6; fi
    sleep 5; waited=$((waited+5))
  done
  (( HELD )) || echo "$OWNER" > $W/CHROME.lock/owner
  (( waited > 0 )) && logline "CHROME.lock acquired after ${waited}s"
  # 3. never two Chromes: wait (up to 30 min) for any foreign headless Chrome to exit
  for try in {1..120}; do chrome_alive || break; (( try == 1 || try % 20 == 0 )) && logline "foreign headless Chrome alive (pid $(pgrep -f "$CHROME_RE" | head -1)) — waiting 15 s ($try/120)"; touch -c $W/CHROME.lock; sleep 15; done
  if chrome_alive; then logline "foreign headless Chrome still alive after 30 min — abort run"; exit 3; fi
  # 4a. disk (after the lock: a running Chrome's swap inflates disk use)
  for try in {1..60}; do avail_kb=$(df -k / | tail -1 | awk '{print $4}'); (( avail_kb >= 1572864 )) && break; logline "disk $((avail_kb/1024)) MB free < 1.5 GB (swap: $(sysctl -n vm.swapusage | tr -s ' ')) — waiting 30 s ($try/60)"; touch -c $W/CHROME.lock; sleep 30; done
  if (( avail_kb < 1572864 )); then logline "DISK < 1.5 GB free ($((avail_kb/1024)) MB) after 30 min — STOP"; exit 2; fi
  # 4b. quiet gate DISABLED (2026-09-20 20:30, orchestrator): load measured once, recorded as "contended" when load1 >= 6 or a hog > 90 % CPU, no waiting
  contended=""
  load1=$(sysctl -n vm.loadavg | awk '{print $2}')
  hog=$(ps -Ao %cpu,pid,comm -r | sed -n 2p | awk '{printf "%s:%s", $1, substr($3, length($3)-24)}')
  hogcpu=${hog%%:*}
  if ! { (( $(echo "$load1 < 6.0" | bc -l) )) && (( $(echo "${hogcpu:-0} < 90" | bc -l) )); }; then contended="load1=$load1 top=$hog"; fi
  if [[ -n $contended ]]; then logline "quiet gate disabled; proceeding CONTENDED ($contended)"; echo "$contended" > $out/$label.contended; else rm -f $out/$label.contended; fi
  # 4c. FINAL power check immediately before launch; if battery, release the lock and start over
  if on_ac; then break; fi
  (( HELD )) && { logline "power flipped to battery during the gates — rc 4 (driver holds the pair lock and will retry)"; exit 4; }
  logline "power flipped to battery during the gates — releasing lock, waiting for AC"; unlock
done
# 4. static server (repo's strict allowlist server, same as P2)
port=$((43000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 &
spid=$!
sleep 2
url="http://127.0.0.1:$port/$rel/index.html"
if ! curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q 200; then logline "server did not serve $url"; cat $out/$label.server.log; exit 4; fi
sysinfo() { echo "load=$(sysctl -n vm.loadavg | tr -d '{}') swap=$(sysctl -n vm.swapusage | awk '{print $6}') top=$(ps -Ao %cpu,comm -r | sed -n 2,4p | awk '{printf "%s:%s ", $1, substr($2, length($2)-24)}')"; }
logline "START heap=$heap trace=$trace trigger=${B0_TRIGGER:-click} mouseoff=${B0_MOUSEOFF:-off} cap=$cap url=$url disk_free_MB=$((avail_kb/1024)) batt='$(pmset -g batt | sed -n 2p | tr -s '\t' ' ')' $(sysinfo)"
# 5. run (caffeinated, headless Chrome 153)
rm -f $out/$label.INVALID-battery
B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=$heap B0_TRACE=$trace B0_CAP_MS=$cap B0_INVALIDATION=${B0_INVALIDATION:-0} B0_MOUSEOFF=${B0_MOUSEOFF:-off} B0_TRIGGER=${B0_TRIGGER:-click} \
  caffeinate -dims $NODE $W/B0/bench_native.mjs > $out/$label.stdout.log 2>&1 &
npid=$!
# power watchdog + lock heartbeat: every 30 s; on battery → kill the harness + Chrome, mark invalid
( while kill -0 $npid 2>/dev/null; do touch -c $W/CHROME.lock; sleep 30; if ! pmset -g batt | head -1 | grep -q "AC Power"; then echo "$(date '+%F %T') $(pmset -g batt | sed -n 2p | tr -s '\t' ' ')" > $out/$label.INVALID-battery; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 1; pkill -f "$CHROME_RE" 2>/dev/null; break; fi; done ) &
wpid=$!
wait $npid; rc=$?
kill $wpid 2>/dev/null; wpid=
if [[ -f $out/$label.INVALID-battery ]]; then
  logline "POWER FLIPPED TO BATTERY MID-RUN ($(cat $out/$label.INVALID-battery)) — run INVALID, files renamed *.INVALID-battery.*"
  for f in $out/$label.json $out/$label-final.png $out/$label.stdout.log $out/$label.server.log $out/$label-trace.json.gz; do [[ -f $f ]] && mv $f ${f/$label/$label.INVALID-battery}; done
  rm -f $out/$label.INVALID-battery; kill $spid 2>/dev/null; spid=; unlock; trap - EXIT INT TERM; exit 4
fi
kill $spid 2>/dev/null; spid=
sleep 1
chrome_alive && { logline "WARNING: headless Chrome still alive after run, killing"; pkill -f "$CHROME_RE"; sleep 2; }
unlock
trap - EXIT INT TERM
logline "END rc=$rc $(python3 $W/B0/summarize_run.py $out/$label.json --oneline 2>&1 | tail -1) $(sysinfo)"
exit $rc
