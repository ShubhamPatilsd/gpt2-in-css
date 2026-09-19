#!/bin/zsh
# Re-run of the latch micro-test (first run aborted: finish.sh deleted the pages mid-run, zsh glob error). Appends the summary to F5.md, then frees the 77 MB of pages.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
$W/F5/run_latch.sh
python3 - <<'PY'
import glob
W='/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'
mds=sorted(glob.glob(f'{W}/F5/latch/results/summary*.md'))
body=open(mds[-1]).read() if mds else 'no summary written (see F5/latch/run.stdout.log)'
md=open(f'{W}/F5.md').read().replace('## 4. Latch micro-test (Fix 4) — `work/2026-09-19/F5/latch/`\n\nPENDING (filled in below when the run completes).', '## 4. Latch micro-test (Fix 4) — `work/2026-09-19/F5/latch/`\n\nHarness: copy of M1 run.mjs (+3 s idle-window TaskDuration column), 3 trials, 1 warm-up (arms the 18,432 transitions). First attempt (17:49) aborted by an F5 script bug (pages deleted mid-run; partial results in latch/results-aborted-17h49: transition-sib ULT 107 ms for 13 elements vs 0.1 ms with no banks). Raw table of the re-run:\n\n'+body)
open(f'{W}/F5.md','w').write(md)
open(f'{W}/F5.log.md','a').write('- latch micro-test re-run finished; summary appended to F5.md §4; pages deleted\n')
PY
rm -f $W/F5/latch/pages/*.html
