#!/bin/zsh
ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; W=$ROOT/work/2026-09-19; NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node
port=$((45000 + RANDOM % 2000))
python3 $ROOT/tools/launch_browser_gpt2.py --no-open --port $port --directory $W/bundles/smoke-R3L-2L-font > $W/R3L/fontprobe/server.log 2>&1 & spid=$!
url="http://127.0.0.1:$port/work/2026-09-19/R3L/fontprobe/index.html"
for _ in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200 && break; sleep 1; done
URL=$url $NODE $W/R3L/fontprobe/probe.mjs
kill $spid 2>/dev/null
