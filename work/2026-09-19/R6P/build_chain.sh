#!/bin/zsh
# R6P build chain (ONE build at a time; never while another agent's Chrome run holds CHROME.lock):
# 1 bundles/combined8-c32-prompt (12 layers, cap 32, widths, R6P flags on)  2 scratch/c32-off (both R6P flags off) -> compare vs bundles/combined8-c32, delete
# 3 scratch/c32-echo (ECHO_FIX only) -> compare vs combined8-c32 (the 2-rule part-A patch), delete  4 bundles/combined8-prompt (cap 8, on)  5 scratch/c8-off -> compare vs bundles/combined8, delete
set -u
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; R=$W/R6P; cd $R
logline() { echo "- $(date '+%F %T') [R6P build] $*" >> $W/R6P.log.md; echo "$(date '+%T') $*"; }
wait_no_foreign_chrome() { while [[ -d $W/CHROME.lock ]] && ! grep -q '^R6P' $W/CHROME.lock/owner 2>/dev/null; do logline "CHROME.lock held by $(cat $W/CHROME.lock/owner 2>/dev/null) — not building during a foreign Chrome run; waiting 60 s"; sleep 60; done; }
build() { local out=$1 cap=$2 blocks=$3; shift 3; wait_no_foreign_chrome; logline "build $out cap=$cap blocks=$blocks env: $*"; local t0=$(date +%s); env "$@" ./compile.sh $out $cap $blocks > logs/compile-$(basename $out).log 2>&1; local rc=$?; logline "built $out rc=$rc in $(( $(date +%s) - t0 )) s: $(ls -la $out 2>/dev/null | awk '{s+=$5} END{print s\" B\"}') free=$(df -g $W | tail -1 | awk '{print $4}')GB"; return $rc; }
cmp() { python3 $R/compare_bundles.py $1 $2 > logs/compare-$3.log 2>&1; logline "compare $3: $(grep -E 'index.html|runtime.css|manifest|font-witnesses' logs/compare-$3.log | tr '\n' ' ' | cut -c1-400)"; }
# cap 8 keeps combined8's recipe (runs layout); cap 32 uses widths (combined8-c32)
build $W/bundles/combined8-c32-prompt 32 12 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=1 || exit 1
build $R/scratch/c32-off 32 12 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0 && cmp $R/scratch/c32-off $W/bundles/combined8-c32 c32-off-vs-combined8-c32 && rm -rf $R/scratch/c32-off
build $R/scratch/c32-echo 32 12 VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=0 && cmp $R/scratch/c32-echo $W/bundles/combined8-c32 c32-echo-vs-combined8-c32 && cmp $R/scratch/c32-echo $W/bundles/combined8-c32-prompt c32-echo-vs-c32-prompt
python3 - <<'PY' >> logs/compare-c32-echo-vs-combined8-c32.log 2>&1
import difflib
a=open('/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined8-c32/runtime.css').read().replace('}','}\n').splitlines()
b=open('/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6P/scratch/c32-echo/runtime.css').read().replace('}','}\n').splitlines()
d=[l for l in difflib.unified_diff(a,b,'combined8-c32','c32-echo',n=0,lineterm='') if not l.startswith(('---','+++','@@'))]
print('rule-level diff combined8-c32 -> echo-only twin (%d lines):' % len(d)); print('\n'.join(x[:400] for x in d))
PY
rm -rf $R/scratch/c32-echo
build $W/bundles/combined8-prompt 8 12 VALUE_LAYOUT=runs R4S_SMALL_HOPS=1 R6P_ECHO_FIX=1 R6P_TYPED_PROMPT=1
build $R/scratch/c8-off 8 12 VALUE_LAYOUT=runs R4S_SMALL_HOPS=1 R6P_ECHO_FIX=0 R6P_TYPED_PROMPT=0 && cmp $R/scratch/c8-off $W/bundles/combined8 c8-off-vs-combined8 && rm -rf $R/scratch/c8-off
logline "build chain done; free=$(df -g $W | tail -1 | awk '{print $4}')GB"
touch $R/BUILD-CHAIN-DONE
