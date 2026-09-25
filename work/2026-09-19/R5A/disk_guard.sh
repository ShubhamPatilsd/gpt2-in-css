#!/bin/bash
# R5A: while my time8 run is alive, abort my own Chrome if free disk < 150 MB (swap growth). Logs to R5A.log.md.
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
while pgrep -f "run_trace8.sh 3" >/dev/null; do
  free_kb=$(df -k / | awk 'NR==2{print $4}')
  if [ "$free_kb" -lt 153600 ]; then
    echo "- $(date '+%F %T') [R5A disk_guard] free=${free_kb}KB < 150 MB: killing my headless Chrome to protect the disk" >> R5A.log.md
    pkill -f '^/Applications/.*Google Chrome .*--headless'; sleep 30
  fi
  sleep 10
done
echo "- $(date '+%F %T') [R5A disk_guard] exit (run script gone); free=$(df -h / | awk 'NR==2{print $4}')" >> R5A.log.md
