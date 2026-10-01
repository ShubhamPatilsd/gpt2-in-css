#!/bin/zsh
# R6X: rebuild the two R6P-only twins (one at a time) for the R6X copy of R6V's offline checker, delete after.
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W
for pair in "p32-r6ponly 32 combined8-c32-prompt demo-c32" "p8-r6ponly 8 combined8-prompt demo-8"; do
  set -- ${=pair}; name=$1; cap=$2; ref=$3; demo=$4
  echo "### $(date '+%T') rebuild twin-$name"; R6X/twin.sh $name $cap bundles/$ref R6V_PROGRESS_UI=0 | grep -E 'index.html|runtime.css|font-witnesses' | cut -c1-200
  echo "### $(date '+%T') R6X/offline_check_r6v.py bundles/$demo vs R6X/twin-$name"; python3 R6X/offline_check_r6v.py bundles/$demo R6X/twin-$name | tee R6X/logs/offline_check-r6x-$demo.log | cut -c1-500
  rm -rf R6X/twin-$name
done
touch R6X/TWINS2-DONE; echo "### $(date '+%T') done"
