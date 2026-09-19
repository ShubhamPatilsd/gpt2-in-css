#!/bin/zsh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
while ! mkdir CHROME.lock 2>/dev/null; do sleep 15; done
echo "F2 holds CHROME.lock at $(date +%H:%M:%S)" > F2/LOCK_HELD
