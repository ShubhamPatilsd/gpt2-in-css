#!/bin/zsh
# R5A: parse the two traced runs of run_trace8.sh <suffix>: summaries (ids, per-token), B0/parse_trace.py, anatomy.py (+frame_regress), parse_memdumps.py.
# usage: postprocess.sh <suffix>   (outputs under R5A/run-combined7/parsed-<suffix>/)
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; out=$W/R5A/run-combined7; sfx=${1:-1}; P=$out/parsed-$sfx; mkdir -p $P
logline() { echo "- $(date '+%F %T') [R5A postprocess/$sfx] $*" >> $W/R5A.log.md; echo "$(date '+%F %T') $*"; }
for lab in mem8-$sfx time8-$sfx; do
  [[ -f $out/$lab.json ]] || { logline "$lab.json missing — skipped"; continue; }
  python3 $W/R4M/summarize32.py $out/$lab.json $W/R5A/reference_ids_8.json > $P/$lab.summary.md 2>&1; logline "$lab summary -> $P/$lab.summary.md ($(sed -n 3p $P/$lab.summary.md | cut -c1-120))"
  tr=$out/$lab-trace.json.gz; [[ -f $tr ]] || { logline "$lab trace missing"; continue; }
  nice -n 5 python3 $W/R5A/parse_memdumps.py $tr $out/$lab.json $P/$lab > $P/$lab.memdumps.out 2>&1; rc=$?; logline "$lab memdumps rc=$rc -> $P/$lab-memdumps.md"; (( rc == 0 )) && [[ $lab == mem8-* ]] && touch $P/PARSED-OK-$lab-trace
  if [[ $lab == time8-* ]]; then
    nice -n 5 python3 $W/B0/parse_trace.py $tr $out/$lab.json $P/$lab > $P/$lab.parse_trace.out 2>&1; logline "$lab parse_trace rc=$? -> $P/$lab-analysis.txt"
    nice -n 5 python3 $W/R5A/anatomy.py $tr $out/$lab.json $P/$lab all > $P/$lab.anatomy.out 2>&1; logline "$lab anatomy rc=$? -> $P/$lab-anatomy.md"
    nice -n 5 python3 $W/R5A/frame_regress.py $tr $P/$lab-anatomy.json $P/$lab-frames > $P/$lab.frames.out 2>&1; rc=$?; logline "$lab frame_regress rc=$? -> $P/$lab-frames.md"; [[ -f $P/$lab-anatomy.json && -f $P/$lab-summary.json ]] && touch $P/PARSED-OK-$lab-trace
  fi
done
# coordinator retention rule: raw JSON is never written (Chrome streams gzip); keep the .gz only if < 150 MB, else delete after parsing
for tr in $out/mem8-$sfx-trace.json.gz $out/time8-$sfx-trace.json.gz; do
  [[ -f $tr ]] || continue; sz=$(stat -f %z $tr)
  if (( sz >= 157286400 )) && [[ -f $P/PARSED-OK-$(basename $tr .json.gz) ]]; then rm -f $tr; logline "deleted $tr ($((sz/1048576)) MB >= 150 MB, parsed)"; else logline "kept $tr ($((sz/1048576)) MB)"; fi
done
touch $P/PARSED; logline "postprocess done -> $P; disk free $(df -h / | awk 'NR==2{print $4}')"
