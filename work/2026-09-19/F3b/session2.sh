#!/bin/zsh
# F3b Chrome session 2 (under run_chrome.sh): ONE passive correctness run each of bundles/F3a and bundles/combined2 (12 layers, 8 tokens, no trace).
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
cd $W/F3b
echo "== F3a $(date)"
F3B_POLL_MS=5000 ./serve_and_run.sh F3a F3a 0 2>&1 | tee results/F3a.txt
echo "== combined2 $(date)"
F3B_POLL_MS=5000 ./serve_and_run.sh combined2 combined2 0 2>&1 | tee results/combined2.txt
echo "== done $(date)"
