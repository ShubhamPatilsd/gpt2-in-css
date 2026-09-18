#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""All-head, real retained-KV component checks for the detached owner compiler."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import traceback

import numpy as np
import build_hybrid_twelve_block as hybrid
from browser_gpt2_owned_attention import OwnedAttention, collect_cache_layer
from decode_css_cache_diagnostic import decode_cache
from investigate_browser_gpt2_scaling import oracle
from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, error, metrics, query, read_vector
from test_browser_gpt2_components import wait_fonts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/browser-gpt2-integration/attention'


def declarations(vector, generation, layer, position):
    return f'--epoch:{generation};--layer:{layer};--position:{position};' + ';'.join(f'--qkv-{i:03d}:{v:.12g}' for i, v in enumerate(vector))


def fixture(directory, layers, capacity, value_layout):
    if (directory / 'results.json').exists():
        raise FileExistsError(f'Preserving existing attempt: {directory}')
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(712369)
    vectors = rng.normal(size=(capacity, layers, 2304))
    vectors[:, :, 768:1536] *= 3
    vectors[:, :, 1536:] *= 5
    history = [[] for _ in range(layers)]
    steps = []
    for position in range(capacity):
        for layer in range(layers):
            vector = vectors[position, layer]
            history[layer].append(tuple(np.split(vector, 3)[1:]))
            steps.append({'position': position + 1, 'layer': layer, 'vector': vector.tolist(), 'expected': oracle(vector, history[layer]), 'kind': 'append'})
    if layers > 1:
        vector = vectors[-1, 0].copy()
        vector[:768] += np.linspace(-.4, .4, 768)
        steps.append({'position': capacity, 'layer': 0, 'vector': vector.tolist(), 'expected': oracle(vector, history[0]), 'kind': 'revisit-layer-0'})
    source, receiver, bridge_css, _ = hybrid.bridge(100, 768)
    compiler = OwnedAttention(expected_epoch='--expected', max_generations=len(steps), value_layout=value_layout)
    producer, css, metadata = compiler.attention(capacity, layers, source, write_epoch='--position')
    css += bridge_css
    css += hybrid.regs(hybrid.names('qkv', 2304) + hybrid.names('x', 768) + hybrid.names('bridge-p', 768) + ['--epoch', '--position', '--layer', '--expected', '--bridge-stamp', '--bridge-ready'])
    css += ''.join(f'@keyframes bridgek{i}{{from{{--bridge-p-{i:03d}:-2}}to{{--bridge-p-{i:03d}:1}}}}' for i in range(768))
    css += '@keyframes bridgestamp{from{--bridge-stamp:0}to{--bridge-stamp:1}}'
    css = re.sub(r'524288 / var\((--bridge-p-\d+)\)', r'1572864 / (var(\1) + 2)', css)
    css += 'body{--expected:1;--epoch:var(--expected)}#supplied-qkv{container-name:runtime}.scroller{position:fixed;top:-60000px;left:0;height:1px;overflow:scroll;contain:strict;visibility:hidden}.track{position:relative;height:1px}.metric{position:absolute;left:0;top:0;height:1px}'
    scopes = re.findall(r'html\{timeline-scope:([^}]+)\}', css)
    css += 'html{timeline-scope:' + ','.join(dict.fromkeys(x for group in scopes for x in group.split(','))) + '}'
    initial = steps[0]
    html = '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="attention.css"><body><div id="supplied-qkv" style="' + declarations(initial['vector'], 1, initial['layer'], initial['position']) + '">' + producer + '</div>' + compiler.artifact.detached_consumers_html + receiver.replace('{child}', '<div id="result"></div>') + '</body>'
    assert css.count('{') == css.count('}')
    assert '<script' not in html.lower()
    assert producer + '</div><div class="oa-consumers">' in html
    assert compiler.artifact.detached_consumers_html.count('var(--qkv-') == 0
    (directory / 'index.html').write_text(html)
    (directory / 'attention.css').write_text(css)
    (directory / 'fixture.json').write_text(json.dumps({'steps': steps, 'metadata': metadata}, indent=2))
    for name in ('browser_gpt2_owned_attention.py', 'probe_browser_gpt2_owned_attention.py'):
        (directory / name).write_text((ROOT / 'tools' / name).read_text())
    return steps, metadata


def settled(cdp, result_node, join_node, generation, limit=45):
    previous, stable = None, 0
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        joined = props(cdp, join_node)
        values = read_vector(cdp, result_node, 'x', 768)
        ready = joined.get('--oa-output-epoch') == str(generation) and joined.get('--oa-all-ready') == '1'
        if ready and previous == values and np.isfinite(values).all():
            stable += 1
        else:
            stable = 0
        if stable >= 3:
            return values, [float(joined[f'--oa-join-tag-{h}']) for h in range(12)]
        previous = values
        time.sleep(.025)
    raise TimeoutError(f'Generation {generation} did not join all heads: epoch={joined.get("--oa-output-epoch")}, ready={joined.get("--oa-all-ready")}, tags={[joined.get(f"--oa-join-tag-{h}") for h in range(12)]}')


def run(directory, layers, capacity, value_layout):
    steps, metadata = fixture(directory, layers, capacity, value_layout)
    report = {'scope': 'Externally supplied all-head QKV component, native owned input commits and per-layer/per-slot retained KV; not autonomous full-model timing', 'runtimeJavaScript': False, 'harnessJavaScript': False, 'externalWritesAfterNavigation': 0, 'metadata': metadata, 'samples': [], 'sourceHashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), ROOT / 'tools/browser_gpt2_owned_attention.py', directory / 'index.html', directory / 'attention.css')}}
    history = {}
    try:
        with browser(['--js-flags=--heap-growing-percent=10']) as cdp:
            report['browser'] = cdp.command('Browser.getVersion')
            node = navigate(cdp, directory / 'index.html', '#result')
            supplied = query(cdp, '#supplied-qkv')
            body = query(cdp, 'body')
            join = query(cdp, '.oa-all-heads-join')
            wait_fonts(cdp, '.oa-0-score-0', 1, limit=30)
            wait_fonts(cdp, '.oa-v-0-0', 1, limit=30)
            previous_vector = None
            for generation, step in enumerate(steps, 1):
                vector = np.asarray(step['vector'])
                start = time.perf_counter()
                before = metrics(cdp)
                if generation > 1:
                    attribute(cdp, supplied, 'style', declarations(vector, generation, step['layer'], step['position']))
                    attribute(cdp, body, 'style', f'--expected:{generation}')
                    report['externalWritesAfterNavigation'] += 2
                actual, tags = settled(cdp, node, join, generation)
                head_errors = [error(actual[h * 64:(h + 1) * 64], step['expected'][h * 64:(h + 1) * 64]) for h in range(12)]
                changed = None if previous_vector is None else [[float(np.max(np.abs(vector[k * 768 + h * 64:k * 768 + (h + 1) * 64] - previous_vector[k * 768 + h * 64:k * 768 + (h + 1) * 64]))) for h in range(12)] for k in range(3)]
                row = {'generation': generation, 'kind': step['kind'], 'layer': step['layer'], 'position': step['position'], 'milliseconds': (time.perf_counter() - start) * 1000, 'headErrors': head_errors, 'headJoinedTags': tags, 'perHeadQKVChangeMaximum': changed, 'rendererDelta': {k: v - before.get(k, 0) for k, v in metrics(cdp).items() if k.endswith(('Count', 'Duration'))}}
                if step['kind'] == 'append':
                    history[step['layer'], step['position'] - 1] = vector[768:].tolist()
                bank_values = {layer: collect_cache_layer(cdp, layer, capacity) for layer in sorted({layer for layer, _ in history})}
                row['cacheErrors'] = [{'layer': layer, 'slot': slot, 'error': error(decode_cache(bank_values[layer], slot, 'font-vector'), expected)} for (layer, slot), expected in history.items()]
                row['passed'] = all(e['rmse'] is not None and e['rmse'] < .005 for e in head_errors) and tags == [generation] * 12 and all(r['error']['rmse'] is not None and r['error']['rmse'] < .005 for r in row['cacheErrors'])
                report['samples'].append(row)
                (directory / 'results.json').write_text(json.dumps(report, indent=2))
                print(json.dumps({'case': directory.name, 'generation': generation, 'passed': row['passed'], 'maxHeadRMSE': max(e['rmse'] or 0 for e in head_errors), 'tags': tags}), flush=True)
                if not row['passed']:
                    break
                previous_vector = vector
            if len(report['samples']) == len(steps) and all(s['passed'] for s in report['samples']):
                poison = np.random.default_rng(884).normal(size=2304) * 2
                final = steps[-1]
                attribute(cdp, supplied, 'style', declarations(poison, len(steps), final['layer'], final['position']))
                report['externalWritesAfterNavigation'] += 1
                actual, tags = settled(cdp, node, join, len(steps))
                poison_heads = []
                for head in range(12):
                    incoming = props(cdp, query(cdp, f'.oa-input-reader-{head}'))
                    bank = props(cdp, query(cdp, f'.oa-input-bank-{head}'))
                    indices = [k * 768 + head * 64 + i for k in range(3) for i in range(64)]
                    received = [float(incoming[f'--oa-{head}-incoming-x-{i}']) for i in range(192)]
                    held = [float(bank[f'--oa-{head}-x-{i}']) for i in range(192)]
                    poison_heads.append({'head': head, 'receivedPoisonError': error(received, poison[indices]), 'heldOriginalError': error(held, np.asarray(final['vector'])[indices])})
                report['poisonCheck'] = {'heads': poison_heads, 'contextError': error(actual, final['expected']), 'tags': tags}
                report['poisonCheck']['passed'] = all(e[name]['rmse'] is not None and e[name]['rmse'] < .005 for e in poison_heads for name in ('receivedPoisonError', 'heldOriginalError')) and report['poisonCheck']['contextError']['rmse'] < .005
            report['finalJoin'] = {k: v for k, v in props(cdp, join).items() if k.startswith('--oa-join-tag') or k in ('--oa-output-epoch', '--oa-all-ready')}
            report['passed'] = len(report['samples']) == len(steps) and all(s['passed'] for s in report['samples']) and report.get('poisonCheck', {}).get('passed', False)
    except Exception as exc:  # noqa: BLE001 - Keep every failed experiment's diagnostics.
        report['passed'] = False
        report['exception'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
    (directory / 'results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'case': directory.name, 'passed': report['passed'], 'exception': report.get('exception')}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--layers', type=int, default=2)
    parser.add_argument('--capacity', type=int, default=2)
    parser.add_argument('--value-layout', choices=('runs', 'widths'), default='widths')
    parser.add_argument('--label', default='attempt1')
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    directory = OUT / f'{args.label}-l{args.layers}-c{args.capacity}-{args.value_layout}'
    if args.build_only:
        fixture(directory, args.layers, args.capacity, args.value_layout)
        print(directory)
    else:
        run(directory, args.layers, args.capacity, args.value_layout)
