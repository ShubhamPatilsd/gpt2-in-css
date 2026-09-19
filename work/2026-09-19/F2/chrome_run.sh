#!/bin/zsh
# Runs once F2 holds CHROME.lock: static server (repo root) on :4199, headless Chrome correctness run, verify, unlock.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
R=/Users/shubhampatil/Documents/programming/gpt2-css
while [[ ! -f $W/F2/LOCK_HELD ]]; do sleep 5; done
echo "- $(date '+%F %T') lock acquired; pgrep chrome=$(pgrep -f 'Google Chrome --' | wc -l | tr -d ' ')" >> $W/F2.log.md
if pgrep -f "Google Chrome --" > /dev/null; then echo "- $(date '+%F %T') ABORT: a Chrome is still running" >> $W/F2.log.md; rmdir $W/CHROME.lock; rm -f $W/F2/LOCK_HELD; exit 1; fi
mkdir -p $W/F2/run; cp $W/bundles/F2/manifest.json $W/F2/run/manifest.json
cd $R && python3 tools/serve_precompressed.py --port 4199 > $W/F2/run/server.log 2>&1 &
SRV=$!
sleep 2
export F2_URL=http://127.0.0.1:4199/work/2026-09-19/bundles/F2/index.html F2_OUT=$W/F2/run F2_CAP_MS=900000
cd $W/F2 && node correctness_run.mjs > $W/F2/run/harness.log 2>&1
RC=$?
kill $SRV 2>/dev/null
sleep 1; pkill -f "playwright_chromiumdev_profile" 2>/dev/null
rmdir $W/CHROME.lock; rm -f $W/F2/LOCK_HELD
echo "- $(date '+%F %T') chrome run rc=$RC; lock released" >> $W/F2.log.md
cd $W/F2 && OPENBLAS_NUM_THREADS=1 uv run --with numpy --with fonttools --with pillow --with brotli python tools/verify_browser_gpt2_runtime.py $W/F2/run > $W/F2/run/verify.log 2>&1
echo "- $(date '+%F %T') verify rc=$?" >> $W/F2.log.md
touch $W/F2/run/DONE
