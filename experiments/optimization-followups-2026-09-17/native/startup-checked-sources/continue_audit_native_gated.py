#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Continue reverse-order native comparisons only after a successful gate."""
import json
from pathlib import Path
import subprocess
import sys
from probe_audit_native_prefix import DEST, verify
from benchmark_audit_followups import save

def prepare_observer():
    source=(DEST/'prefix_observer.py').read_text()
    start=source.index('        if not report["manifest"].get("autostart", True):')
    end=source.index('        capture = query(cdp,',start)
    source=source[:start]+'        from probe_audit_native_prefix import ensure_started\n        ensure_started(cdp, report)\n        atomic_json(output, report)\n'+source[end:]
    (DEST/'prefix_observer_start_checked.py').write_text(source)

def run(variant,pair):
    directory=DEST/'runs'/f'pair{pair}'/variant
    result=subprocess.run([sys.executable,str(DEST/'prefix_observer_start_checked.py'),
        '--directory',str(DEST/'fixtures'/variant),'--output',str(directory),
        '--tokens','2','--wall-seconds','360','--heap-growth-percent','10'])
    verify(directory)
    print(json.dumps({'variant':variant,'pair':pair,'status':result.returncode,
        'passed':json.loads((directory/'numerical-results.json').read_text())['passed']}),flush=True)


def main():
    prepare_observer()
    verify(DEST/'runs/pair0/combined')
    skipped = []
    for variant in ('combined', 'static-readers', 'small-chunks', 'baseline'):
        first = json.loads((DEST/'runs/pair0'/variant/'numerical-results.json').read_text())
        if first['passed'] or variant=='static-readers':
            run(variant, 1)
        else:
            skipped.append({'pair': 1, 'variant': variant,
                            'reason': 'First-order native completion/numerical gate failed; no repeated speed trial is meaningful.',
                            'firstOrderEvidence': f'native/runs/pair0/{variant}/numerical-results.json'})
        save(DEST/'skipped-runs.json', skipped)
    # The original static-reader timeout had no Run latch. Recover a second
    # matched order with an independently repeated, startup-checked control.
    if json.loads((DEST/'runs/pair1/static-readers/numerical-results.json').read_text())['passed']:
        for variant in ('baseline','static-readers'):
            run(variant,2)
    else:
        skipped.extend({'pair':2,'variant':v,'reason':'Startup-checked static-reader gate failed; no second speed comparison.'}
                       for v in ('baseline','static-readers'))
        save(DEST/'skipped-runs.json',skipped)


if __name__ == '__main__':
    main()
