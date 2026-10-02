#!/bin/zsh
set -u; ROOT=/Users/shubhampatil/Documents/programming/gpt2-css; NODE=/Users/shubhampatil/.nvm/versions/node/v22.23.1/bin/node; R=$ROOT/work/2026-09-19/R8U
mkdir -p $R/tinystories-study; port=$((49000 + RANDOM % 500))
(cd $ROOT && python3 tools/serve_precompressed.py --port $port > $R/tinystories-study/server.log 2>&1) & spid=$!
sleep 3
T_URL=http://127.0.0.1:$port/tinystories/dynamic.html T_OUT=$R/tinystories-study/dynamic T_CLICK=".run-control" T_WAIT_S=15,30 $NODE $R/tiny_shot.mjs
T_URL=http://127.0.0.1:$port/tinystories/streaming-packed8.html T_OUT=$R/tinystories-study/streaming-packed8 T_CLICK=".pause-control" T_WAIT_S=15 $NODE $R/tiny_shot.mjs
pkill -P $spid 2>/dev/null; kill $spid 2>/dev/null
