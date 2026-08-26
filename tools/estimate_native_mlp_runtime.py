#!/usr/bin/env python3
"""Backtest short-prefix runtime estimates without executing the long model.

This deliberately does NOT turn an isolated or connected MLP time into a new
full-model prediction. Only completed native-loop calibration may do that.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / 'experiments/browser-gpt2/demo-font-vector-context32/scaling-summary.json'
DEFAULT_SHORT = ROOT / 'experiments/browser-gpt2/demo-font-vector-twelve/scaling-summary.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fit(rows, model):
    xs = [r['epoch'] for r in rows]
    ys = [r['seconds'] for r in rows]
    if model == 'constant':
        return {'interceptSeconds': statistics.mean(ys), 'secondsPerContextPosition': 0.0}
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / den
    return {'interceptSeconds': mean_y - slope * mean_x, 'secondsPerContextPosition': slope}


def predict(coeff, epoch):
    return max(0.0, coeff['interceptSeconds'] + coeff['secondsPerContextPosition'] * epoch)


def backtests(history):
    terminal_epoch = history['manifest']['generatedTokenLimit']
    rows = history['warmIntervals']
    continuing = [r for r in rows if r['epoch'] < terminal_epoch]
    results = []
    # Fixed before observing results. Model selection is not performed here.
    for cutoff in (4, 8, 12, 16):
        training = [r for r in continuing if r['epoch'] <= cutoff]
        held_out = [r for r in continuing if r['epoch'] > cutoff]
        for model in ('constant', 'linear-context'):
            coeff = fit(training, model)
            prediction = [{'epoch': r['epoch'], 'actualSeconds': r['seconds'],
                           'predictedSeconds': predict(coeff, r['epoch'])} for r in held_out]
            actual_future = sum(r['actualSeconds'] for r in prediction)
            predicted_future = sum(r['predictedSeconds'] for r in prediction)
            observed_prefix = history['firstObservedSeconds'] + sum(r['seconds'] for r in training)
            terminal = next(r['seconds'] for r in rows if r['epoch'] == terminal_epoch)
            terminal_proxy = predict(coeff, terminal_epoch)
            total_proxy = observed_prefix + predicted_future + terminal_proxy
            results.append({
                'prefixThroughEpoch': cutoff, 'model': model, 'fit': coeff,
                'trainingEpochs': [r['epoch'] for r in training],
                'heldOutContinuingEpochs': [r['epoch'] for r in held_out],
                'heldOutActualSeconds': actual_future,
                'heldOutPredictedSeconds': predicted_future,
                'heldOutAggregateErrorPercent': 100 * (predicted_future / actual_future - 1),
                'heldOutMeanAbsoluteErrorSeconds': statistics.mean(abs(r['predictedSeconds'] - r['actualSeconds']) for r in prediction),
                'heldOutMeanAbsolutePercentageError': statistics.mean(100 * abs(r['predictedSeconds'] / r['actualSeconds'] - 1) for r in prediction),
                'heldOutMaximumAbsoluteErrorSeconds': max(abs(r['predictedSeconds'] - r['actualSeconds']) for r in prediction),
                'observedPrefixSeconds': observed_prefix,
                'actualTerminalSeconds': terminal,
                'terminalContinuingProxySeconds': terminal_proxy,
                'terminalWasNotUsedForTrainingOrContinuingValidation': True,
                'estimatedTotalIncludingUncalibratedTerminalProxySeconds': total_proxy,
                'actualTotalSeconds': history['totalSeconds'],
                'totalProxyErrorPercent': 100 * (total_proxy / history['totalSeconds'] - 1),
                'heldOutPredictions': prediction,
            })
    return results


def forecast_native_prefix(calibration):
    """Consume the bounded native-prefix runner, never a segment timing report."""
    required = {
        'scope': 'full-native-token-pipeline', 'blocks': 12,
        'allocatedCapacity': 32, 'compiledGenerationLimit': 32,
        'compiledGraphModified': False, 'completedObservedPrefix': True,
        'sourceUnchangedAfterRun': True, 'wallBudgetExpired': False,
        'stopReason': 'observed-prefix', 'workerExitStatus': 0,
    }
    for key, expected in required.items():
        if calibration.get(key) != expected:
            raise ValueError(f'Calibration {key} must equal {expected!r}; segment, incomplete, changed, or wrong-scope runs cannot forecast this model.')
    samples = calibration['samples']
    count = calibration['observedTokenTarget']
    if not 4 <= count < 32 or [s['capturedTokenCount'] for s in samples] != list(range(1, count + 1)):
        raise ValueError('Need contiguous observed epochs1..K, with4<=K<32 and every last epoch continuing.')
    if any(s.get('skippedObservationCount', 0) != 0 for s in samples):
        raise ValueError('Skipped observations do not supply per-context calibration intervals.')
    times = [s['milliseconds'] / 1000 for s in samples]
    if not all(math.isfinite(value) for value in times) or times[0] <= 0 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Observed prefix times must be finite, positive, and strictly increasing.')
    rows = [{'epoch': i + 2, 'seconds': b - a} for i, (a, b) in enumerate(zip(times, times[1:]))]
    models = []
    for model in ('constant', 'linear-context'):
        coeff = fit(rows, model)
        remaining = [{'epoch': epoch, 'predictedSeconds': predict(coeff, epoch)} for epoch in range(count + 1, 32)]
        terminal = predict(coeff, 32)
        models.append({
            'model': model, 'fit': coeff, 'observedPrefixSeconds': times[-1],
            'predictedRemainingContinuingSeconds': sum(r['predictedSeconds'] for r in remaining),
            'terminalContinuingProxySeconds': terminal,
            'predictedTotalWithUncalibratedTerminalProxySeconds': times[-1] + sum(r['predictedSeconds'] for r in remaining) + terminal,
            'remainingContinuingPredictions': remaining,
        })
    return {
        'status': 'diagnostic-only; observed token timing is not numerical validation or calibrated forecast accuracy',
        'observedTokens': count, 'allocatedCapacity': 32, 'blocks': 12,
        'firstObservedSeconds': times[0], 'continuingIntervals': rows,
        'models': models,
        'numericalVerificationPerformed': calibration.get('numericalVerificationPerformed', False),
        'runnerBrowserValidated': calibration.get('runnerBrowserValidated', False),
        'requirementsBeforeCallingEstimateAccurate': [
            'Verify prefix token outputs, current residual, and every retained cache against an independent reference.',
            'Measure fresh AB/BA baseline and candidate native prefixes at the same allocated capacity and graph residency.',
            'Reserve later continuing contexts for validation; early-prefix fit alone cannot establish later-context or memory-pressure accuracy.',
            'Calibrate terminal behavior separately; the final token need not cost the same as a continuing token.',
        ],
        'limitation': 'No checkpoint restoration or candidate-model integration is implemented here. The historical withheld-suffix backtest is not a confidence interval for this prefix.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history', type=Path, default=DEFAULT_HISTORY)
    p.add_argument('--short-history', type=Path, default=DEFAULT_SHORT)
    p.add_argument('--benchmark', type=Path, action='append')
    p.add_argument('--calibration', type=Path, help='A completed unchanged cap32/12-layer report from benchmark_native_token_prefix.py; diagnostic forecast only until independent numerical and later-context validation.')
    p.add_argument('--output', type=Path, default=ROOT / 'experiments/native-mlp-integration/runtime-estimation.json')
    args = p.parse_args()
    history = json.loads(args.history.read_text())
    short = json.loads(args.short_history.read_text())
    assert history['complete'] and all(history['tokenAgreement'])
    assert history['manifest']['capacity'] == 32 and history['manifest']['blocks'] == 12
    observed_completion = history['firstObservedSeconds'] + sum(r['seconds'] for r in history['warmIntervals'])
    assert 0 <= history['totalSeconds'] - observed_completion < 1.0
    shared_epochs = range(2, 8)  # Epoch8 terminates capacity8 run; exclude it.
    short_rows = {r['epoch']: r['seconds'] for r in short['warmIntervals']}
    long_rows = {r['epoch']: r['seconds'] for r in history['warmIntervals']}
    cross = [{'epoch': e, 'capacity8Seconds': short_rows[e], 'capacity32Seconds': long_rows[e],
              'capacity32Over8Ratio': long_rows[e] / short_rows[e]} for e in shared_epochs]
    report = {
        'schemaVersion': 1,
        'purpose': 'Historical withheld-suffix backtest and requirements for a future calibrated prediction. No new 32-token run.',
        'sources': [{'path': str(x.relative_to(ROOT) if x.is_relative_to(ROOT) else x), 'sha256': digest(x)} for x in (args.history, args.short_history, Path(__file__).resolve())],
        'historicalBaseline': {'totalSeconds': history['totalSeconds'], 'blocks': 12, 'allocatedCapacity': 32,
                               'generatedTokens': 32, 'observedLastTokenSeconds': observed_completion, 'postObservationBookkeepingSeconds': history['totalSeconds'] - observed_completion, 'peakRendererRssMiB': history['sampledPeak']['rendererRssMiB']},
        'backtestProtocol': {
            'modelsDeclared': ['constant arithmetic-mean continuing latency', 'ordinary least squares affine latency versus token epoch'],
            'prefixCutoffsDeclared': [4, 8, 12, 16],
            'startup': 'Use observed first-token elapsed time; do not extrapolate it.',
            'continuing': 'Fit epochs2..cutoff only; validate unseen cutoff+1..31. Epoch32 is terminal and excluded.',
            'terminal': 'Show extrapolated continuing value separately; it is not a calibrated terminal model.',
            'limitations': ['Single historical trajectory and machine/browser state; not independent replicated validation.',
                           'Context count is a proxy for both growing cache/history and elapsed runtime; their effects cannot be identified separately.',
                           'No confidence interval is justified by one saved run.',
                           'Post-hoc backtesting shows feasibility/risk; these model classes were not prospectively declared before the historical run.'],
        },
        'backtests': backtests(history),
        'crossCapacityDiagnostic': {
            'matchedEpochs': cross,
            'ratioOfMeanContinuingLatencies': statistics.mean(x['capacity32Seconds'] for x in cross) / statistics.mean(x['capacity8Seconds'] for x in cross),
            'causalClaim': False,
            'warning': 'These are non-contemporaneous runs with different allocation and head-epoch transport. A capacity8 prefix is not a calibrated capacity32 prefix.'
        },
        'newCandidateTotalPrediction': None,
        'newCandidateTotalPredictionReason': 'A segment replay does not measure twelve-layer scheduling, layer switching, attention history, vocabulary, memory pressure, or token feedback. Multiplying its saving by384 is an unvalidated scenario, not a runtime forecast.',
        'futureCalibrationPlan': {
            'scope': 'Keep allocated capacity32 and all12layer assets resident in both variants.',
            'checkpoints': [2, 8, 16, 24, 30],
            'workAtCheckpoint': 'Restore independently verified residual/KV/native generation state, then measure a continuing token with actual current pipeline. Do not count restoration as inference; report it separately.',
            'checkpointSupport': 'Not implemented by this script. Never inject precomputed outputs within a timed token.',
            'pairing': 'At least two fresh-process AB/BA pairs per sampled context, one page resident. Compare per-context baseline/candidate changes and initialization independently.',
            'validation': 'Reserve at least one interior context and one late context from model fitting; compare prediction with their measured latencies. Save correctness of all caches and full token outputs.',
            'forecast': 'Sum context-specific calibrated predictions across32positions plus separately measured initialization and terminal behavior. Report pair spread and held-out prediction error.',
            'stop': 'Do not publish an accurate full-run estimate if correctness fails, pair directions reverse, or held-out error exceeds a predeclared useful bound.'
        }
    }
    if args.benchmark:
        report['segmentBenchmarks'] = []
        for benchmark_path in args.benchmark:
            bench = json.loads(benchmark_path.read_text())
            report['segmentBenchmarks'].append({'path': str(benchmark_path), 'sha256': digest(benchmark_path), 'passed': bench.get('passed'), 'schedule': bench.get('protocol', {}).get('schedule'), 'summary': bench.get('summary'), 'scope': bench.get('scope')})
    if args.calibration:
        calibration = json.loads(args.calibration.read_text())
        report['conditionalNativePrefixForecast'] = forecast_native_prefix(calibration)
        report['calibrationSource'] = {'path': str(args.calibration), 'sha256': digest(args.calibration)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    for row in report['backtests']:
        print(f"prefix{row['prefixThroughEpoch']:2d} {row['model']:14s} total proxy {row['estimatedTotalIncludingUncalibratedTerminalProxySeconds']/60:.2f}min error {row['totalProxyErrorPercent']:+.1f}% withheld {row['heldOutAggregateErrorPercent']:+.1f}%")
    print(f"same early epochs: capacity32/capacity8 latency ratio {report['crossCapacityDiagnostic']['ratioOfMeanContinuingLatencies']:.3f}")
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
