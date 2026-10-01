#!/bin/zsh
# R6X merge: <out-tools-dir> = R5X/tools (combined8's emitter) + R6P/tools-vs-R5X.diff + R6V/tools-vs-R5X.diff (BSD patch, basenames, -F3),
# then R6X/apply_conflicts.py (exact-string edits). R6L's diff is NOT applied (merge takes R6V's early paint; R6L flags would be 0).
# usage: merge.sh <out-tools-dir>
set -e
setopt nullglob
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
out=${1:?tools dir}
rm -rf $out; cp -R $W/R5X/tools $out; find $out -name __pycache__ -type d -prune -exec rm -rf {} +
cd $out
echo "## R6P ($W/R6P/tools-vs-R5X.diff)"; patch -F3 -N < $W/R6P/tools-vs-R5X.diff || true
echo "## R6V ($W/R6V/tools-vs-R5X.diff)"; patch -F3 -N < $W/R6V/tools-vs-R5X.diff || true
echo "## rejects:"; r=(*.rej); (( ${#r} )) && { ls -la *.rej; for f in *.rej; do cp $f $W/R6X/rejects/$f; done; } || echo none
echo "## after both diffs, before conflict edits: merged minus R6P/tools (must be exactly R6V's two files):"; diff -rq -x __pycache__ $W/R6P/tools $out | sort || true
echo "## merged minus R6V/tools (must be exactly R6P's two files):"; diff -rq -x __pycache__ $W/R6V/tools $out | sort || true
echo "## r6p_prompt.py / r6v_progress_ui.py identical to owners' before the conflict edits:"; cmp $out/r6p_prompt.py $W/R6P/tools/r6p_prompt.py && cmp $out/r6v_progress_ui.py $W/R6V/tools/r6v_progress_ui.py && echo yes
echo "## runtime = R6P's + R6V's hunks? (diff vs R6P's runtime should show only r6v lines)"; diff $W/R6P/tools/browser_gpt2_runtime.py $out/browser_gpt2_runtime.py || true
echo "## r6v_progress_ui.py: R6V's diff predates R6V's 15:44 fix (literal · instead of the \\00b7 escape); take the owner's current module verbatim"
diff $out/r6v_progress_ui.py $W/R6V/tools/r6v_progress_ui.py || true; cp $W/R6V/tools/r6v_progress_ui.py $out/r6v_progress_ui.py
python3 $W/R6X/apply_conflicts.py $out
r=(*.rej); (( ${#r} )) && { echo "rejects remain"; ls *.rej; exit 3; }
rm -f *.orig
python3 -m py_compile *.py && echo "syntax ok"
find $out -name __pycache__ -type d -prune -exec rm -rf {} +
(cd $W && diff -ruN -x __pycache__ R5X/tools ${out#$W/} > $W/R6X/tools-vs-R5X.diff || true); wc -l $W/R6X/tools-vs-R5X.diff
echo "## files differing from R5X/tools:"; diff -rq -x __pycache__ $W/R5X/tools $out | sort
