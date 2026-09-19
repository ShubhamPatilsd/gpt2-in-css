#!/bin/zsh
# Waits for the correctness run; creates bundles/F5/READY only if the 8 ids match; then summarizes the latch test when it lands.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
for i in {1..240}; do [[ -f $W/F5/verify/F5.json ]] && break; sleep 15; done
python3 - <<'PY'
import json,os
W='/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'
r=json.load(open(f'{W}/F5/verify/F5.json'))
ok = r['ids']==[11,314,1101,7926,11,475,314,1101]
line=f"- {'PASS' if ok else 'FAIL'} browser correctness: ids={r['ids']} stop={r['stop']} wall={r['wallSeconds']:.0f}s per-token(5 s poll, not a timing run)={[round(t['tokenSeconds'],1) for t in r['tokens']]} metrics={r['metricsDelta']}"
open(f'{W}/F5.log.md','a').write(line+'\n')
md=open(f'{W}/F5.md').read().replace('## 5. Verification\n\nPENDING.', '## 5. Verification\n\n'+line+('\n\nREADY created for B0.' if ok else '\n\nREADY NOT created.'))
open(f'{W}/F5.md','w').write(md)
if ok: open(f'{W}/bundles/F5/READY','w').write('F5 correct 8/8 ids\n')
PY
for i in {1..240}; do [[ -f $W/F5/latch/results/summary.md ]] && break; ls $W/F5/latch/results/*.md >/dev/null 2>&1 && break; sleep 15; done
echo "- latch micro-test finished; results in F5/latch/results (summary md + jsonl); pages deleted to free disk" >> $W/F5.log.md
python3 - <<'PY'
import glob
W='/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19'
mds=sorted(glob.glob(f'{W}/F5/latch/results/*.md'))
body=open(mds[-1]).read() if mds else 'no summary written'
md=open(f'{W}/F5.md').read().replace('## 4. Latch micro-test (Fix 4) — `work/2026-09-19/F5/latch/`\n\nPENDING (filled in below when the run completes).', '## 4. Latch micro-test (Fix 4) — `work/2026-09-19/F5/latch/`\n\nHarness: copy of M1 run.mjs (+3 s idle-window TaskDuration column), 3 trials, 1 warm-up (arms the 18,432 transitions). Raw table:\n\n'+body)
open(f'{W}/F5.md','w').write(md)
PY
rm -rf $W/F5/latch/pages/*.html
