#!/bin/zsh
# R4M merge: <out-tools-dir> = R3M/tools + R4S diff (-p1) + R4D diff (-p2, 2 known rejects fixed by apply_conflicts.py) [+ R4T diff].
# usage: merge.sh <out-tools-dir> [R4T-diff-file] [R4T -p level]
set -e
setopt nullglob
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
out=${1:?tools dir}; r4t=${2:-}; r4tp=${3:-2}
rm -rf $out; cp -R $W/R3M/tools $out; find $out -name __pycache__ -type d -prune -exec rm -rf {} +
cd $out
echo "## R4S ($W/R4S/tools-vs-R3M.diff)"; patch -p1 -F3 -N < $W/R4S/tools-vs-R3M.diff
echo "## R4D ($W/R4D/tools-vs-R3M.diff)"; patch -p2 -F3 -N < $W/R4D/tools-vs-R3M.diff || true
cp $W/R4D/tools/r4d_flags.py $out/  # R4D's diff is `diff -ru` without -N: the new module is listed as "Only in", copy it from the owner
echo "## rejects:"; ls *.rej
python3 $W/R4M/apply_conflicts.py $out
mkdir -p $W/R4M/rejects; mv browser_gpt2_font_vector_cache.py.rej browser_gpt2_reused_adapter.py.rej $W/R4M/rejects/  # the two known R4D-on-R4S rejects, fixed above
if [[ -n $r4t ]]; then echo "## R4T ($r4t)"; patch -p$r4tp -F3 -N < $r4t || true; cp $W/R4T/tools/r4t_consumer_chunk.py $out/; python3 $W/R4M/apply_r4t_import.py $out; mv browser_gpt2_reused_adapter.py.rej $W/R4M/rejects/r4t-adapter-import.rej; fi  # known reject: the adjacent import line; R4T's READY diff is `diff -ru` without -N -> copy the new module
echo "## rejects after fixes:"; r=(*.rej); (( ${#r} )) && { ls *.rej; exit 3; }; echo none
rm -f *.orig
python3 -m py_compile *.py && echo "syntax ok"
find $out -name __pycache__ -type d -prune -exec rm -rf {} +
cmp $out/r4s_small_hops.py $W/R4S/tools/r4s_small_hops.py && cmp $out/r4d_flags.py $W/R4D/tools/r4d_flags.py && { [[ -z $r4t ]] || cmp $out/r4t_consumer_chunk.py $W/R4T/tools/r4t_consumer_chunk.py; } && echo "new modules identical to owners"
dn=${DIFF_NAME:-tools-vs-R3M.diff}; (cd $W && diff -ruN -x __pycache__ R3M/tools ${out#$W/} > $W/R4M/$dn || true); wc -l $W/R4M/$dn
diff -rq -x __pycache__ $W/R3M/tools $out | sort
