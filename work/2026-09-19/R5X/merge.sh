#!/bin/zsh
# R5X merge: <out-tools-dir> = R4M/tools7 (combined7's emitter) + R5E diff (-p2) + R5H diff (-p2); rejects resolved by R5X/apply_conflicts.py as exact-string edits.
# usage: merge.sh <out-tools-dir>
set -e
setopt nullglob
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
out=${1:?tools dir}
rm -rf $out; cp -R $W/R4M/tools7 $out; find $out -name __pycache__ -type d -prune -exec rm -rf {} +
cd $out
echo "## R5E ($W/R5E/tools-vs-tools7.diff, -p2)"; patch -p2 -F3 -N < $W/R5E/tools-vs-tools7.diff || true
echo "## R5H ($W/R5H/tools-vs-tools7.diff, -p2)"; patch -p2 -F3 -N < $W/R5H/tools-vs-tools7.diff || true
echo "## rejects:"; r=(*.rej); (( ${#r} )) && ls -la *.rej || echo none
mkdir -p $W/R5X/rejects; for f in *.rej; do cp $f $W/R5X/rejects/$f; done
python3 $W/R5X/apply_conflicts.py $out
mv browser_gpt2_reused_adapter.py.rej $W/R5X/rejects/r5h-adapter-readers.rej   # the known R5H-on-R5E reject, fixed above
echo "## rejects after fixes:"; r=(*.rej); (( ${#r} )) && { ls *.rej; exit 3; }; echo none
rm -f *.orig
python3 -m py_compile *.py && echo "syntax ok"
find $out -name __pycache__ -type d -prune -exec rm -rf {} +
cmp $out/r5e_dead_weight.py $W/R5E/tools/r5e_dead_weight.py && cmp $out/r5h_ch_scores.py $W/R5H/tools/r5h_ch_scores.py && echo "new modules identical to owners"
(cd $W && diff -ruN -x __pycache__ R4M/tools7 ${out#$W/} > $W/R5X/tools-vs-tools7.diff || true); wc -l $W/R5X/tools-vs-tools7.diff
echo "## files differing from tools7:"; diff -rq -x __pycache__ $W/R4M/tools7 $out | sort
echo "## merged minus R5E (should be exactly R5H's changes):"; diff -rq -x __pycache__ $W/R5E/tools $out | sort
echo "## merged minus R5H (should be exactly R5E's changes):"; diff -rq -x __pycache__ $W/R5H/tools $out | sort
