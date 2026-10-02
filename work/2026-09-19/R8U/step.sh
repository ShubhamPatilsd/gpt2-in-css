#!/bin/zsh
# R8U: ONE Chrome step: R8U/with_lock.sh <label> <wall-cap> <command…>, retrying every 60 s on rc 8 (gate) / 9 (power); DONE-<label> on rc 0.
# usage: step.sh <label> <wall-cap-s> <command…>
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R8U
label=$1; cap=$2; shift 2
logline() { echo "- $(date '+%F %T') [R8U step/$label] $*" >> $W/R8U.log.md; echo "$(date '+%T') $*"; }
n=0; while true; do $R/with_lock.sh $label $cap "$@"; rc=$?; (( rc == 8 || rc == 9 )) || break; (( n % 10 == 0 )) && logline "refused rc=$rc — retrying every 60 s"; sleep 60; n=$((n+1)); done
(( rc == 0 )) && touch $R/DONE-$label
logline "step finished rc=$rc"; exit $rc
