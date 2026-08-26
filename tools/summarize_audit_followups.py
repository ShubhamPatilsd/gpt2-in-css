#!/usr/bin/env python3
"""Summarize preserved follow-up evidence without changing raw measurements."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/optimization-followups-2026-09-17'
VARIANTS = ('baseline', 'small-chunks', 'static-readers', 'combined')


def read(relative):
    path = OUT / relative
    return json.loads(path.read_text()) if path.exists() else None


def change(candidate, baseline):
    return 100 * (candidate / baseline - 1)


def maximum_difference(left, right):
    if len(left) != len(right):
        raise ValueError('Mismatched retained-vector lengths')
    return max(abs(a - b) for a, b in zip(left, right, strict=True))


def native_summary():
    rows, retained = [], {}
    for pair in range(3):
        for variant in VARIANTS:
            directory = f'native/runs/pair{pair}/{variant}'
            report = read(f'{directory}/prefix-results.json')
            numerical = read(f'{directory}/numerical-results.json')
            if report is None:
                continue
            samples = report.get('samples', [])
            row = {
                'pair': pair, 'variant': variant, 'directory': directory,
                'complete': report.get('completedObservedPrefix', False),
                'passed': bool(numerical and numerical['passed']),
                'firstObservedMs': samples[0]['milliseconds'] if samples else None,
                'totalObservedMs': samples[1]['milliseconds'] if len(samples) == 2 else None,
                'continuingObservedMs': samples[1]['milliseconds'] - samples[0]['milliseconds'] if len(samples) == 2 else None,
                'peakRendererRssMiB': max((s['rendererRssMiB'] for s in report.get('sampledMemory', [])), default=None),
                'sourceUnchanged': report.get('sourceUnchangedAfterRun'),
                'tokens': report.get('retainedTokens'),
                'startupVerification': report.get('startupVerification'),
                'startupAmbiguous': pair == 0 and variant == 'static-readers',
                'numerical': numerical,
            }
            rows.append(row)
            if 'numericalReadback' in report:
                retained[pair, variant] = report['numericalReadback']
    for pair in range(3):
        baseline = next((r for r in rows if r['pair'] == pair and r['variant'] == 'baseline'), None)
        if baseline is None or not baseline['passed']:
            continue
        for row in rows:
            if row['pair'] != pair or not row['passed']:
                continue
            row['percentChange'] = {
                key: change(row[key], baseline[key])
                for key in ('firstObservedMs', 'totalObservedMs', 'continuingObservedMs', 'peakRendererRssMiB')
            }
            left, right = retained[pair, 'baseline'], retained[pair, row['variant']]
            baseline_caches = {(c['layer'], c['position']): c['values'] for c in left['caches']}
            row['baselineDifference'] = {
                'hiddenMaximum': maximum_difference(left['hidden'], right['hidden']),
                'cacheMaximum': max(maximum_difference(baseline_caches[c['layer'], c['position']], c['values']) for c in right['caches']),
            }
    skipped = read('native/skipped-runs.json') or []
    return {
        'expectedRuns': 10, 'finishedRuns': sum(r['numerical'] is not None for r in rows),
        'skippedRuns': skipped,
        'completeRuns': sum(r['complete'] for r in rows),
        'passingRuns': sum(r['passed'] for r in rows), 'rows': rows,
        'scope': '12 layers, 32 allocated slots, 2 observed outputs; total includes navigation/setup; continuing time is the observed first-to-second interval.',
        'limitation': 'Two opposite orders, not enough to estimate a narrow confidence interval or full32 occupancy behavior.',
    }


def loop_summary():
    rows = [{'source': 'original', **r} for r in (read('loop/summary.json') or []) if r['pair'] in (2, 3)]
    rows += [{'source': 'awake-retry', **r} for r in (read('awake-retries/loop/summary.json') or [])]
    result = []
    for row in rows:
        baseline = next(r for r in rows if (r['source'], r['pair'], r['variant']) == (row['source'], row['pair'], 'baseline'))
        result.append({
            'source': row['source'], 'pair': row['pair'], 'variant': row['variant'],
            'passed': row['passed'], 'continuationMs': row.get('observedContinuationMilliseconds'),
            'percentChange': change(row['observedContinuationMilliseconds'], baseline['observedContinuationMilliseconds']) if row['passed'] and baseline['passed'] else None,
        })
    return result


def head_summary():
    rows = [{'source': 'full38-forward', **r} for r in (read('head/summary.json') or []) if r['repeat'] == 0]
    rows += [{'source': 'fixed8-reverse-awake', **r} for r in (read('awake-retries/head/summary.json') or [])]
    result = []
    for row in rows:
        baseline = next((r for r in rows if r['source'] == row['source'] and r['mode'] == 'baseline'), None)
        result.append({
            'source': row['source'], 'mode': row['mode'], 'passed': row['passed'],
            'checkedUpdates': len(row['samples']), 'medianMs': row.get('medianMilliseconds'),
            'percentChange': change(row['medianMilliseconds'], baseline['medianMilliseconds']) if row['passed'] and baseline and baseline['passed'] else None,
            'peakRendererRssMiB': row.get('peakRendererRssMiB'),
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    native = native_summary()
    required = ('normalization/browser-summary.json', 'fusion/results.json', 'persistent-v-track/summary.json',
                'awake-retries/head/summary.json', 'awake-retries/loop/summary.json', 'boundaries-r1/summary.json',
                'quality-clamped/results.json')
    missing = [name for name in required if read(name) is None]
    result = {
        'scope': 'Derived summary; raw interrupted runs remain unchanged and are excluded from eligible timing comparisons.',
        'complete': native['finishedRuns'] + len(native['skippedRuns']) == native['expectedRuns'] and not missing,
        'missingArtifacts': missing,
        'dense': read('dense/paired-summary.json'),
        'consumerSelection': read('dense-refinement/selection.json'),
        'loopEligibleTimings': loop_summary(), 'headEligibleTimings': head_summary(),
        'native': native,
        'normalizationBrowser': read('normalization/browser-summary.json'),
        'boundaryDiagnostic': read('boundaries-r1/summary.json'),
        'quality': read('quality-clamped/results.json'),
    }
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'complete': result['complete'], 'nativeComplete': native['completeRuns'], 'nativePassing': native['passingRuns'], 'missing': missing}))
    if args.require_complete and not result['complete']:
        raise SystemExit('Follow-up evidence is incomplete')


if __name__ == '__main__':
    main()
