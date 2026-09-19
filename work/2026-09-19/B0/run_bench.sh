#!/bin/zsh
# B0 bench driver. usage: run_bench.sh <bundle-name> <label> <heap 0|1> <trace 0|1> [cap_ms]
# bundle-name "pinned" -> experiments/browser-gpt2/demo-font-vector-twelve; otherwise work/2026-09-19/bundles/<name>
set -u
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css
W=$ROOT/work/2026-09-19
NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
bundle=$1; label=$2; heap=$3; trace=$4; cap=${5:-600000}
if [[ $bundle == pinned ]]; then dir=$ROOT/experiments/browser-gpt2/demo-font-vector-twelve; rel=experiments/browser-gpt2/demo-font-vector-twelve
else dir=$W/bundles/$bundle; rel=work/2026-09-19/bundles/$bundle; fi
out=$W/bench/runs/$bundle; mkdir -p $out
if [[ ${B0_FORCE:-0} != 1 && -f $out/$label.json ]] && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('stopReason') in ('token-limit','eos') else 1)" $out/$label.json 2>/dev/null; then echo "skip $label (complete)"; exit 0; fi
logline() { echo "- $(date '+%Y-%m-%d %H:%M:%S') [$bundle/$label] $*" >> $W/B0.log.md; echo "$*"; }
on_ac() { pmset -g batt | head -1 | grep -q "AC Power"; }
wait_ac() { local n=0; while ! on_ac; do (( n % 5 == 0 )) && logline "ON BATTERY ($(pmset -g batt | sed -n 2p | tr -s '\t' ' ')) — timing refused, waiting for AC (poll 60 s)"; sleep 60; n=$((n+1)); done; }
cleanup() { rmdir $W/CHROME.lock 2>/dev/null; [[ -n ${spid:-} ]] && kill $spid 2>/dev/null; [[ -n ${wpid:-} ]] && kill $wpid 2>/dev/null; }
trap 'cleanup' EXIT
trap 'cleanup; trap - EXIT; exit 130' INT TERM
while true; do
  # 1. power (no lock held while waiting)
  wait_ac
  # 2. Chromium mutex
  waited=0
  while ! mkdir $W/CHROME.lock 2>/dev/null; do
    (( waited == 0 )) && logline "CHROME.lock held, polling"
    # stale-lock guard (coordinator 06:10, after a hung R2D harness held the lock 3 h with no Chrome): lock dir mtime older
    # than 20 min AND no Chrome process → log and remove. Live holders keep the mtime fresh (this script touches it in its gates).
    if [[ -d $W/CHROME.lock ]] && ! pgrep -f "Google Chrome --" >/dev/null; then
      age=$(( $(date +%s) - $(stat -f %m $W/CHROME.lock 2>/dev/null || date +%s) ))
      if (( age > 1200 )); then
        logline "STALE CHROME.lock (mtime $((age/60)) min old, no Chrome process alive) — removing it"
        rmdir $W/CHROME.lock 2>/dev/null || logline "stale lock rmdir failed (non-empty?): $(ls -la $W/CHROME.lock 2>&1 | tr '\n' ' ')"
        continue
      fi
    fi
    sleep 15; waited=$((waited+15))
  done
  # 3. never two Chromes: wait (up to 30 min) for any foreign Chrome to exit
  for try in {1..120}; do pgrep -f "Google Chrome --" >/dev/null || break; (( try == 1 || try % 20 == 0 )) && logline "foreign Chrome alive (pid $(pgrep -f 'Google Chrome --' | head -1)) — waiting 15 s ($try/120)"; touch $W/CHROME.lock; sleep 15; done
  if pgrep -f "Google Chrome --" >/dev/null; then logline "foreign Chrome still alive after 30 min — abort run"; exit 3; fi
  # 4a. disk (after the lock: a running Chrome's swap inflates disk use)
  for try in {1..60}; do avail_kb=$(df -k / | tail -1 | awk '{print $4}'); (( avail_kb >= 1572864 )) && break; logline "disk $((avail_kb/1024)) MB free < 1.5 GB (swap: $(sysctl -n vm.swapusage | tr -s ' ')) — waiting 30 s ($try/60)"; touch $W/CHROME.lock; sleep 30; done
  if (( avail_kb < 1572864 )); then logline "DISK < 1.5 GB free ($((avail_kb/1024)) MB) after 30 min — STOP"; exit 2; fi
  # 4b. quiet gate DISABLED 2026-09-20 20:30 (orchestrator): paired interleaving absorbs drift; the load is still measured once and recorded as "contended" when load1 >= 6 or a hog > 90 % CPU, no waiting
  contended=""
  for try in {1..1}; do
    load1=$(sysctl -n vm.loadavg | awk '{print $2}')
    hog=$(ps -Ao %cpu,pid,comm -r | sed -n 2p | awk '{printf "%s:%s", $1, substr($3, length($3)-24)}')
    hogcpu=${hog%%:*}
    if (( $(echo "$load1 < 6.0" | bc -l) )) && (( $(echo "${hogcpu:-0} < 90" | bc -l) )); then contended=""; break; fi
    contended="load1=$load1 top=$hog"
    (( try == 1 || try % 6 == 0 )) && logline "quiet gate: load1=$load1 top=$hog — waiting 30 s ($try/6)"
    touch $W/CHROME.lock; sleep 30
  done
  if [[ -n $contended ]]; then logline "quiet gate timed out; proceeding CONTENDED ($contended)"; echo "$contended" > $out/$label.contended; else rm -f $out/$label.contended; fi
  # 4c. FINAL power check immediately before launch; if battery, release the lock and start over
  if on_ac; then break; fi
  logline "power flipped to battery during the gates — releasing lock, waiting for AC"; rmdir $W/CHROME.lock 2>/dev/null
done
# 4. static server (repo's strict allowlist server, same as P2)
port=$((43000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $dir > $out/$label.server.log 2>&1 &
spid=$!
sleep 2
url="http://127.0.0.1:$port/$rel/index.html"
if ! curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q 200; then logline "server did not serve $url"; cat $out/$label.server.log; exit 4; fi
sysinfo() { echo "load=$(sysctl -n vm.loadavg | tr -d '{}') swap=$(sysctl -n vm.swapusage | awk '{print $6}') top=$(ps -Ao %cpu,comm -r | sed -n 2,4p | awk '{printf "%s:%s ", $1, substr($2, length($2)-24)}')"; }
logline "START heap=$heap trace=$trace mouseoff=${B0_MOUSEOFF:-off} cap=$cap url=$url disk_free_MB=$((avail_kb/1024)) batt='$(pmset -g batt | sed -n 2p | tr -s '\t' ' ')' $(sysinfo)"
# 5. run (caffeinated, headless Chrome 153)
rm -f $out/$label.INVALID-battery
B0_URL=$url B0_LABEL=$label B0_OUT=$out B0_HEAP=$heap B0_TRACE=$trace B0_CAP_MS=$cap B0_INVALIDATION=${B0_INVALIDATION:-0} B0_MOUSEOFF=${B0_MOUSEOFF:-off} \
  caffeinate -dims $NODE $W/B0/bench_native.mjs > $out/$label.stdout.log 2>&1 &
npid=$!
# power watchdog: every 30 s; on battery → kill the harness + Chrome, mark invalid
( while kill -0 $npid 2>/dev/null; do touch $W/CHROME.lock; sleep 30; if ! pmset -g batt | head -1 | grep -q "AC Power"; then echo "$(date '+%F %T') $(pmset -g batt | sed -n 2p | tr -s '\t' ' ')" > $out/$label.INVALID-battery; pkill -P $npid 2>/dev/null; kill $npid 2>/dev/null; sleep 1; pkill -f "Google Chrome --" 2>/dev/null; break; fi; done ) &
wpid=$!
wait $npid; rc=$?
kill $wpid 2>/dev/null; wpid=
if [[ -f $out/$label.INVALID-battery ]]; then
  logline "POWER FLIPPED TO BATTERY MID-RUN ($(cat $out/$label.INVALID-battery)) — run INVALID, files renamed *.INVALID-battery.*"
  for f in $out/$label.json $out/$label-final.png $out/$label.stdout.log $out/$label.server.log $out/$label-trace.json.gz; do [[ -f $f ]] && mv $f ${f/$label/$label.INVALID-battery}; done
  rm -f $out/$label.INVALID-battery; kill $spid 2>/dev/null; spid=; rmdir $W/CHROME.lock 2>/dev/null; trap - EXIT INT TERM; exit 4
fi
kill $spid 2>/dev/null; spid=
sleep 1
pgrep -f "Google Chrome --" >/dev/null && { logline "WARNING: Chrome still alive after run, killing"; pkill -f "Google Chrome --"; sleep 2; }
rmdir $W/CHROME.lock 2>/dev/null
trap - EXIT INT TERM
logline "END rc=$rc $(python3 $W/B0/summarize_run.py $out/$label.json --oneline 2>&1 | tail -1) $(sysinfo)"
# 6. trace post-processing
if [[ $trace == 1 && -f $out/$label-trace.json.gz ]]; then
  sz=$(stat -f%z $out/$label-trace.json.gz)
  if (( sz < 10000 )); then logline "trace export EMPTY ($sz B) — light category set failed to export"; rm -f $out/$label-trace.json.gz; exit 5; fi
  logline "parsing trace ($((sz/1048576)) MB gz)"
  python3 $W/B0/parse_trace.py $out/$label-trace.json.gz $out/$label.json $out/$label > $out/$label.parse.log 2>&1 && \
  ( cd $out && python3 $W/B0/make_tables.py $label > $label-tables.md 2>>$label.parse.log ) && logline "trace parsed → $out/$label-tables.md" || logline "trace parse FAILED (see $out/$label.parse.log)"
fi
exit $rc
