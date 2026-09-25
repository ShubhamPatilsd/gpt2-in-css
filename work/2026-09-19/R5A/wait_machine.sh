#!/bin/bash
# R5A: poll AC power + >=3 GB free every 60 s; write R5A/MACHINE-OK when both hold. Appends a line to R5A/machine_poll.log each poll.
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
while true; do
  b=$(pmset -g batt | head -1)
  avail_kb=$(df -k / | awk 'NR==2{print $4}')
  ok=0
  if echo "$b" | grep -q "AC Power" && [ "$avail_kb" -ge 3145728 ]; then ok=1; fi
  echo "$(date '+%F %T') power='$b' avail_kb=$avail_kb ok=$ok" >> R5A/machine_poll.log
  if [ $ok = 1 ]; then touch R5A/MACHINE-OK; exit 0; fi
  sleep 60
done
