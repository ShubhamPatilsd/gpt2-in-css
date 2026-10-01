#!/bin/zsh
# R6X: build ONE flag twin into R6X/twin-<name> (same path depth as bundles/<x>) and compare it with a reference bundle.
# usage: twin.sh <name> <capacity> <ref-bundle-dir> [ENV=VAL ...]   (refuses while CHROME.lock exists)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
name=$1; cap=$2; ref=$3; shift 3
[[ -e $W/CHROME.lock ]] && { echo "CHROME.lock held ($(cat $W/CHROME.lock/owner 2>/dev/null)) — not building"; exit 8; }
out=$W/R6X/twin-$name; rm -rf $out
extra=(); if (( cap > 8 )); then extra=(VALUE_LAYOUT=widths R4S_SMALL_HOPS=0); fi
echo "== build twin-$name (cap $cap) flags: $* ${extra[*]}"
env "$@" ${extra[@]} $W/R6X/compile.sh $out $cap 12 > $W/R6X/logs/compile-twin-$name.log 2>&1 || { echo "BUILD FAILED rc=$?"; tail -5 $W/R6X/logs/compile-twin-$name.log; exit 1; }
echo "== compare twin-$name vs $ref"
python3 $W/R6X/compare_bundles.py $out $ref | tee $W/R6X/logs/compare-$name.log | cut -c1-700
