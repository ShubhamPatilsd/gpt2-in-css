#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Native A/B/A input capture, poison, and reuse around two real attention heads.

Python generates fixtures, navigates, and reads only. CSS receipts and SVG SMIL
advance the finite sequence. K/V remain static; this is not production inference.
"""

import argparse
import hashlib
import json
import re
import time
import traceback
from pathlib import Path

import numpy as np
from browser_gpt2_runtime import font_barrier
from probe_browser_gpt2_state_locality import compile_page, expected, reg
from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, error, query
from test_browser_gpt2_components import wait_fonts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2-scaling/native-local-commits"
WIDTH = 64


def assignments(stem, values):
    return ";".join(f"--{stem}-{i}:{value:.12g}" for i, value in enumerate(values))


def pulse_signal(name, event):
    return f'<g id="{name}"><set attributeName="class" to="done" begin="{event}.animationend+0.001s" fill="freeze"/></g>'


def rule(selector, body):
    return selector + "{" + body + "}"


def compile_fixture(directory):
    if (directory / 'results.json').exists():
        raise FileExistsError(f'Preserving prior attempt at {directory}; use a new --label')
    q, k, v = compile_page(directory, 2, 8, 0, "local")
    css = (directory / "style.css").read_text()
    css, removed = re.subn(r'#head-0\{--query-0-0:[^{}]*\}', '', css)
    assert removed == 1, 'Expected one static active-head query declaration to replace'
    old_html = (directory / "index.html").read_text()
    a, b = q[0].copy(), q[0] * -0.7
    poison = np.linspace(-0.91, 0.93, WIDTH)
    vectors = [a, b, a]
    css += '@keyframes native-handshake{from{opacity:.99}to{opacity:1}}'
    css += '.native-signals{position:fixed;left:0;top:0;width:1px;height:1px}.record{position:absolute;width:1px;height:1px}'
    css += reg("--commit-step") + reg("--commit-held") + reg("--commit-poison")
    css += '#transfer{container-name:commitcontrol;--commit-step:1;--commit-held:0;--commit-poison:0}'
    for name in ("--source-tag", "--wanted", "--incoming-tag", "--poison-confirmed", "--input-ready"):
        css += reg(name)
    css += reg("--held-tag", True)
    for i in range(WIDTH):
        css += reg(f"--source-q-{i}", True) + reg(f"--incoming-q-{i}") + reg(f"--held-q-{i}", True)
    # Producer geometry and the input reader are siblings. Raw producer Q never
    # inherits into the receiving head. Timeline scratch stays on the reader.
    names, animations, glyphs, reads = [], [], [], []
    for i in range(WIDTH + 1):
        name = f"--commit-source-{i}"
        animation = f"commit-source-{i}"
        progress = f"--commit-progress-{i}"
        names.append(name)
        animations.append(animation)
        css += reg(progress)
        css += f'@keyframes {animation}{{from{{{progress}:-2}}to{{{progress}:1}}}}'
        source = f"var(--source-q-{i})" if i < WIDTH else "var(--source-tag)"
        glyphs.append(f'<i class="metric" style="width:calc(262144px + {source} * 1024px);view-timeline:{name} inline"></i>')
        target = f"--incoming-q-{i}" if i < WIDTH else "--incoming-tag"
        expr = f"(1572864 / (var({progress}) + 2) - 786432) / 1024"
        reads.append(f"{target}:calc({expr})" if i < WIDTH else f"{target}:round(nearest,calc({expr}),1)")
    # The source-tag is private to #producer, so forward it explicitly only to
    # its metric. Query coordinates are inherited only within that producer.
    css += '#producer>.source>.track{--source-tag:inherit}#producer>.source{--source-tag:inherit}#producer .metric{--source-tag:inherit}'
    css += f'#transfer{{timeline-scope:{",".join(names)}}}'
    css += '#input-reader{container-name:incomingreceipt;'
    css += f'animation-name:{",".join(animations)};animation-timeline:{",".join(names)};animation-duration:1s;animation-fill-mode:both;animation-timing-function:linear;'
    css += ";".join(reads) + ';--poison-confirmed:calc(1 - min(1,abs(var(--incoming-tag) + var(--wanted))))}'
    held_names = [f"--held-q-{i}" for i in range(WIDTH)] + ["--held-tag"]
    css += '#input-bank{container-name:bankreceipt;--wanted:inherit;--incoming-tag:inherit;'
    css += ";".join(f"--incoming-q-{i}:inherit;--held-q-{i}:var(--incoming-q-{i})" for i in range(WIDTH))
    css += ';--held-tag:var(--incoming-tag);--input-ready:calc(1 - min(1,abs(var(--held-tag) - var(--wanted))));transition-property:none;transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}'
    css += f'@container commitcontrol style(--commit-held:1){{#input-bank{{transition-property:{",".join(held_names)}}}}}'
    css += '#head-0{' + ";".join(f"--query-0-{i}:var(--held-q-{i})" for i in range(WIDTH)) + ';--tick-0:var(--held-tag)}'
    css += '#reader-0{container-name:headreceipt}'
    signals, records, source_records = [], [], []
    for step, vector in enumerate(vectors, 1):
        # Equal selector specificity and source order make later states win.
        if step > 1:
            css += f'#transfer:where(:has(#advanced-{step - 1}.done)){{--commit-step:{step};--commit-held:0;--commit-poison:0}}'
        css += f'#transfer:where(:has(#captured-{step}.done)){{--commit-held:1}}'
        css += f'#transfer:where(:has(#poisoned-{step}.done)){{--commit-poison:1}}'
        css += rule(f'@container commitcontrol style(--commit-step:{step})', rule('#producer', assignments('source-q', vector) + f';--source-tag:{step}') + rule('#input-reader', f'--wanted:{step}'))
        css += rule(f'@container commitcontrol style(--commit-step:{step})', rule('@container commitcontrol style(--commit-poison:1)', rule('#producer', assignments('source-q', poison) + f';--source-tag:{-step}')))
        # Do not capture before the same real-font barrier used by the runtime.
        css += f'@container commitcontrol style(--commit-step:{step}){{@container bankreceipt style(--input-ready:1){{@container headreceipt style(--h0-ready:1){{body:has(#fonts-loaded.done) #capture-ready-{step}{{animation:native-handshake 1ms both}}}}}}}}'
        css += f'#transfer:has(#captured-{step}.done) #held-ready-{step}{{animation:native-handshake 1ms both}}'
        css += f'@container commitcontrol style(--commit-step:{step}){{@container incomingreceipt style(--poison-confirmed:1){{@container bankreceipt style(--input-ready:1){{@container headreceipt style(--h0-ready:1){{#finish-ready-{step}{{animation:native-handshake 1ms both}}}}}}}}}}'
        css += f'#transfer:has(#finished-{step}.done) #advance-ready-{step}{{animation:native-handshake 1ms both}}'
        signals += [f'<g id="{kind}-ready-{step}"></g>' for kind in ("capture", "held", "finish", "advance")]
        signals += [pulse_signal(f"captured-{step}", f"capture-ready-{step}"), pulse_signal(f"poisoned-{step}", f"held-ready-{step}"), pulse_signal(f"finished-{step}", f"finish-ready-{step}")]
        if step < 3:
            signals.append(pulse_signal(f"advanced-{step}", f"advance-ready-{step}"))
        # Audit snapshots are native held registers of actual computed values.
        record_fields = [f"--audit-{step}-q-{i}" for i in range(WIDTH)] + [f"--audit-{step}-out-{i}" for i in range(WIDTH)] + [f"--audit-{step}-tag"]
        source_fields = [f"--audit-{step}-source-{i}" for i in range(WIDTH)] + [f"--audit-{step}-source-tag"]
        for name in record_fields + source_fields:
            css += reg(name)
        css += f'#record-{step}{{transition-property:{",".join(record_fields)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}'
        css += f'#source-record-{step}{{transition-property:{",".join(source_fields)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}'
        # Explicitly forward only into the source audit leaves; compute receives
        # none of these raw incoming fields by normal inheritance.
        css += f'#source-record-{step}{{--incoming-tag:inherit;' + ";".join(f"--incoming-q-{i}:inherit" for i in range(WIDTH)) + '}'
        target_assign = ";".join(f"--audit-{step}-q-{i}:var(--held-q-{i});--audit-{step}-out-{i}:var(--h0-out{i})" for i in range(WIDTH))
        source_assign = ";".join(f"--audit-{step}-source-{i}:var(--incoming-q-{i})" for i in range(WIDTH))
        css += f'@container commitcontrol style(--commit-step:{step}){{@container incomingreceipt style(--poison-confirmed:1){{#record-{step}{{transition-property:none;{target_assign};--audit-{step}-tag:var(--held-tag)}}#source-record-{step}{{transition-property:none;{source_assign};--audit-{step}-source-tag:var(--incoming-tag)}}}}}}'
        records.append(f'<i class="record" id="record-{step}"></i>')
        source_records.append(f'<i class="record" id="source-record-{step}"></i>')
    body = old_html.split('<body>', 1)[1].rsplit('</body>', 1)[0]
    head0, head1 = body.split('<div class="head" id="head-1">', 1)
    head1 = '<div class="head" id="head-1">' + head1
    head0 = head0.replace('<div id="reader-0">', '<div id="reader-0"><svg xmlns="http://www.w3.org/2000/svg" class="native-signals">' + "".join(signals) + '</svg>' + "".join(records))
    producer = '<div id="producer"><div class="source"><div class="track">' + "".join(glyphs) + '</div></div></div>'
    transfer = '<div id="transfer">' + producer + '<div id="input-reader">' + "".join(source_records) + '<div id="input-bank">' + head0 + '</div></div></div>'
    font_html, font_css, count = font_barrier(css, directory)
    css += font_css
    assert css.count('{') == css.count('}'), 'Unbalanced generated CSS'
    (directory / 'style.css').write_text(css)
    (directory / 'index.html').write_text('<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="style.css"><body>' + font_html + transfer + head1 + '</body>')
    fixture = {"sequence": [x.tolist() for x in vectors], "poison": poison.tolist(), "expectedContexts": [expected(x, k[0], v[0]) for x in vectors], "expectedUnrelatedContext": expected(q[1], k[1], v[1]), "fontFaces": count}
    (directory / 'fixture.json').write_text(json.dumps(fixture, indent=2))
    (directory / 'probe-source.py').write_text(Path(__file__).read_text())
    return fixture


def vector(state, stem):
    return [float(state.get(f"--{stem}-{i}", 'nan')) for i in range(WIDTH)]


def run(directory, observe_after=0):
    fixture = compile_fixture(directory)
    report = {"scope": "Two real bilinear-font QK + CSS softmax heads; static eight-slot KV; single reusable local input register; finite A/B/A native capture/poison sequence; not production cache or inference", "runtimeJavaScript": False, "harnessJavaScript": False, "externalWritesAfterNavigation": 0, "observeAfterSeconds": observe_after, "samples": [], "sourceHashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), ROOT / 'tools/probe_browser_gpt2_state_locality.py', ROOT / 'tools/browser_gpt2_runtime.py', directory / 'index.html', directory / 'style.css')}}
    try:
        with browser(["--js-flags=--heap-growing-percent=10"]) as cdp:
            report['browser'] = cdp.command('Browser.getVersion')
            started = time.perf_counter()
            node = navigate(cdp, directory / 'index.html', '#input-bank', observe_after_seconds=observe_after)
            # DOM selection does not force computed style; record the native
            # completion marker before any computed-style observation can help.
            report['completedBeforeFirstComputedStyleRead'] = bool(query(cdp, '#finished-3.done'))
            owner = query(cdp, '#transfer')
            unrelated = query(cdp, '#reader-1')
            deadline = time.monotonic() + 30
            previous = None
            while time.monotonic() < deadline:
                state = props(cdp, owner)
                bank = props(cdp, node)
                sample = {k: state.get(k) for k in ('--commit-step', '--commit-held', '--commit-poison')}
                sample.update({k: bank.get(k) for k in ('--held-tag', '--input-ready', '--incoming-tag')})
                unrelated_state = props(cdp, unrelated)
                sample['unrelatedOutput'] = [float(unrelated_state.get(f'--h1-out{i}', 'nan')) for i in range(WIDTH)]
                if sample != previous:
                    report['samples'].append({'milliseconds': (time.perf_counter() - started) * 1000, **sample})
                    previous = sample
                if query(cdp, '#finished-3.done'):
                    break
                time.sleep(.025)
            report['completed'] = bool(query(cdp, '#finished-3.done'))
            wait_fonts(cdp, '.h0-s0', 1, limit=10)
            report['commits'] = []
            for step in range(1, 4):
                target = props(cdp, query(cdp, f'#record-{step}'))
                source = props(cdp, query(cdp, f'#source-record-{step}'))
                row = {'step': step, 'inputError': error(vector(target, f'audit-{step}-q'), fixture['sequence'][step - 1]), 'outputError': error(vector(target, f'audit-{step}-out'), fixture['expectedContexts'][step - 1]), 'poisonError': error(vector(source, f'audit-{step}-source'), fixture['poison']), 'heldTag': float(target.get(f'--audit-{step}-tag', 'nan')), 'sourceTag': float(source.get(f'--audit-{step}-source-tag', 'nan'))}
                row['passed'] = all(row[name]['rmse'] is not None and row[name]['rmse'] < .005 for name in ('inputError', 'outputError', 'poisonError')) and row['heldTag'] == step and row['sourceTag'] == -step
                report['commits'].append(row)
            state = props(cdp, unrelated)
            report['unrelatedError'] = error([float(state.get(f'--h1-out{i}', 'nan')) for i in range(WIDTH)], fixture['expectedUnrelatedContext'])
            valid_unrelated = [s['unrelatedOutput'] for s in report['samples'] if (error(s['unrelatedOutput'], fixture['expectedUnrelatedContext'])['rmse'] or 0) < .005 and np.isfinite(s['unrelatedOutput']).all()]
            report['unrelatedObservedValidSamples'] = len(valid_unrelated)
            report['unrelatedMaximumObservedOutputChange'] = max((float(np.max(np.abs(np.asarray(values) - valid_unrelated[0]))) for values in valid_unrelated), default=None)
            report['passed'] = report['completed'] and all(r['passed'] for r in report['commits']) and report['unrelatedError']['rmse'] is not None and report['unrelatedError']['rmse'] < .005
            report['finalDiagnostics'] = {selector: {k: value for k, value in props(cdp, query(cdp, selector)).items() if k.startswith(('--commit-', '--incoming-tag', '--held-tag', '--wanted', '--poison-confirmed', '--input-ready', '--h0-ready')) or k == 'animation-name'} for selector in ('#transfer', '#producer', '#input-reader', '#input-bank', '#reader-0', '#capture-ready-1', '#held-ready-1', '#finish-ready-1')}
    except Exception as exc:  # noqa: BLE001 - Preserve diagnostics for any experiment failure.
        report['passed'] = False
        report['exception'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
    (directory / 'results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'case': directory.name, **{k: report.get(k) for k in ('passed', 'completed', 'commits', 'exception')}}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--observe-after', type=float, default=0)
    parser.add_argument('--label', default='attempt1')
    args = parser.parse_args()
    for repeat in range(args.repeats):
        directory = OUT / f'{args.label}-delay{args.observe_after:g}-r{repeat}'
        if args.build_only:
            compile_fixture(directory)
            print(directory)
        else:
            run(directory, args.observe_after)
