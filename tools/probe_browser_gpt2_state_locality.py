#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Structural locality diagnostic with real bilinear-font QK and static KV.

This is deliberately not the production cache: immutable K/V are fixture inputs,
softmax and weighted V are CSS arithmetic, and every head owns one subtree.
Identical pages compare mutation at body versus the owning head. It measures
collateral work from unrelated state, not generated-token throughput.
"""

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import numpy as np
from benchmark_browser_gpt2_memory import MemorySampler
from browser_gpt2_font_vector_cache import FONT_DIR, QK_SIZE, UNITS_PER_EM, fonts
from investigate_browser_gpt2_scaling import delta
from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, error, metrics, query
from test_browser_gpt2_components import wait_fonts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2-scaling/locality"


def reg(name, inherits=False):
    return f'@property {name}{{syntax:"<number>";inherits:{str(inherits).lower()};initial-value:0}}'


def compile_page(directory, heads, slots, spectators, mode):
    info = fonts()["dot"]
    unit = QK_SIZE / UNITS_PER_EM
    # Each head has its own seed: changing the number of unrelated heads must
    # not change the active head's arithmetic workload or numerical inputs.
    queries, keys, values = [], [], []
    for head in range(heads):
        rng = np.random.default_rng(2417 + head)
        queries.append(rng.uniform(-0.8, 0.8, 64))
        keys.append(rng.uniform(-0.8, 0.8, (slots, 64)))
        values.append(rng.normal(size=(slots, 64)))
    queries, keys, values = map(np.array, (queries, keys, values))
    css = f'@font-face{{font-family:LocalDot;src:url("{(FONT_DIR / "dot.woff2").as_uri()}")}}'
    css += '.source{position:fixed;top:-60000px;left:0;width:524288px;height:1px;overflow:scroll;contain:strict;visibility:hidden}.track{position:relative;width:1572864px;height:1px}.metric{position:absolute;left:0;top:0;height:1px}.spectator{display:block;width:1px;height:1px}.head{position:absolute;top:0;left:0}.out{display:block;height:1px}'
    body = []
    for head in range(heads):
        scope = f"h{head}"
        query_names = [f"--query-{head}-{i}" for i in range(64)]
        for name in query_names + [f"--tick-{head}"]:
            css += reg(name, True)
        declarations = ";".join(f"{name}:{v:.12g}" for name, v in zip(query_names, queries[head])) + f";--tick-{head}:1"
        owner = "body" if mode == "broadcast" and head == 0 else f"#head-{head}"
        css += f"{owner}{{{declarations}}}"
        timelines, animations, reads, glyphs = [], [], [], []
        q_axes = ",".join(f'"Q{i:03d}" var({name})' for i, name in enumerate(query_names))
        for slot in range(slots):
            timeline, animation, progress = f"--{scope}-s{slot}", f"{scope}-s{slot}", f"--{scope}-p{slot}"
            timelines.append(timeline)
            animations.append(animation)
            css += reg(progress) + reg(f"--{scope}-score{slot}")
            css += f"@keyframes {animation}{{from{{{progress}:-2}}to{{{progress}:1}}}}"
            k_axes = ",".join(f'"K{i:03d}" {v:.12g}' for i, v in enumerate(keys[head, slot]))
            css += f".{animation}{{font:{QK_SIZE}px LocalDot;font-kerning:none;font-variation-settings:{k_axes},{q_axes};width:calc-size(max-content,calc(262144px + (size - {info['base'] * unit:.12g}px) * {128 / (8 * info['coefficient'] * unit):.12g}))}}"
            glyphs.append(f'<i class="metric {animation}" style="view-timeline:{timeline} inline">&#xF5800;</i>')
            reads.append(f"--{scope}-score{slot}:calc((1572864 / (var({progress}) + 2) - 786432) / 128)")
        timelines.append(f"--{scope}-stamp")
        animations.append(f"{scope}-stamp")
        css += reg(f"--{scope}-receipt") + reg(f"--{scope}-ready")
        css += f"@keyframes {scope}-stamp{{from{{--{scope}-receipt:-2}}to{{--{scope}-receipt:1}}}}"
        glyphs.append(f'<i class="metric" style="width:calc(262144px + var(--tick-{head}) * 1024px);view-timeline:--{scope}-stamp inline"></i>')
        reads.append(f"--{scope}-ready:calc(1 - min(1,abs(round(nearest,(1572864 / (var(--{scope}-receipt) + 2) - 786432) / 1024,1) - var(--tick-{head}))))")
        maximum = f"--{scope}-max"
        css += reg(maximum)
        reads.append(f"{maximum}:max(" + ",".join(f"var(--{scope}-score{s})" for s in range(slots)) + ")")
        for slot in range(slots):
            name = f"--{scope}-exp{slot}"
            css += reg(name)
            reads.append(f"{name}:exp(calc(var(--{scope}-score{slot}) - var({maximum})))")
        css += reg(f"--{scope}-den")
        reads.append(f"--{scope}-den:calc(" + " + ".join(f"var(--{scope}-exp{s})" for s in range(slots)) + ")")
        for i in range(64):
            name = f"--{scope}-out{i}"
            css += reg(name, True)
            terms = " + ".join(f"var(--{scope}-exp{s}) * ({values[head, s, i]:.12g})" for s in range(slots))
            reads.append(f"{name}:calc(({terms}) / var(--{scope}-den))")
        css += f"#head-{head}{{timeline-scope:{','.join(timelines)}}}#reader-{head}{{animation-name:{','.join(animations)};animation-timeline:{','.join(timelines)};animation-duration:1s;animation-fill-mode:both;animation-timing-function:linear;{';'.join(reads)}}}"
        outputs = "".join(f'<i class="out" style="width:calc(20px + var(--{scope}-out{i}) * 1px)"></i>' for i in range(64))
        # Extra immutable elements amplify the cost of unrelated descendants.
        # They carry no useful neural computation and are reported separately.
        noise = '<div class="unrelated-storage">' + '<i class="spectator"></i>' * spectators + '</div>'
        body.append(f'<div class="head" id="head-{head}"><div class="source"><div class="track">{"".join(glyphs)}</div></div><div id="reader-{head}">{outputs}</div>{noise}</div>')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "style.css").write_text(css)
    (directory / "index.html").write_text('<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="style.css"><body>' + "".join(body) + '</body>')
    return queries, keys, values


def expected(q, k, v):
    scores = k @ q / 8
    weights = np.exp(scores - scores.max())
    return (weights @ v / weights.sum()).tolist()


def read_head(cdp, node, head):
    state = props(cdp, node)
    return state, [float(state.get(f"--h{head}-out{i}", "nan")) for i in range(64)]


def settle_head(cdp, node, head, tick=1, limit=20):
    deadline = time.monotonic() + limit
    previous, stable, reads = None, 0, 0
    while time.monotonic() < deadline:
        state, actual = read_head(cdp, node, head)
        reads += 1
        if state.get(f"--h{head}-ready") == "1" and float(state.get(f"--tick-{head}", 0)) == tick and previous == actual and np.isfinite(actual).all():
            stable += 1
        else:
            stable = 0
        if stable >= 3:
            return actual, reads
        previous = actual
        time.sleep(0.025)
    raise TimeoutError("Head output did not become fresh and stable")


def run(heads, slots, spectators, mode, repeat):
    directory = OUT / f"{mode}-h{heads}-s{slots}-n{spectators}-r{repeat}"
    queries, keys, values = compile_page(directory, heads, slots, spectators, mode)
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__), ROOT / "tools/browser_gpt2_font_vector_cache.py", ROOT / "tools/profile_hybrid_twelve_block.py",
        directory / "style.css", directory / "index.html", FONT_DIR / "dot.woff2",
    )}
    if (directory / "results.json").exists():
        previous = json.loads((directory / "results.json").read_text())
        if previous.get("passed") and previous.get("sourceHashes") == source_hashes:
            print(json.dumps({"case": directory.name, "cached": True}), flush=True)
            return previous
    report = {"scope": "Structural locality diagnostic: static fixture KV, real font QK, CSS softmax/weighted V; not production cache or autonomous inference", "heads": heads, "slots": slots, "spectatorsPerHead": spectators, "mode": mode, "repeat": repeat, "samples": [], "runtimeJavaScript": False, "harnessJavaScript": False, "externalWritesAfterNavigation": 0,
        "sourceHashes": source_hashes, "activeInputHash": hashlib.sha256(b"".join(a[0].tobytes() for a in (queries, keys, values))).hexdigest(),
        "settleProtocol": "All heads initialized before timing; matching native receipt and explicit input tick plus three unchanged finite reads. 25ms polling imposes at least 75ms delay; mutation timing includes CDP overhead. Unrelated-head checks occur outside timed samples.",
        "browserArguments": ["--js-flags=--heap-growing-percent=10"],
    }
    try:
        with browser(report["browserArguments"]) as cdp, MemorySampler(cdp.browser_pid) as memory:
            cdp.connection.settimeout(60)
            report["browser"] = cdp.command("Browser.getVersion")
            active = navigate(cdp, directory / "index.html", "#reader-0")
            owner = query(cdp, "body" if mode == "broadcast" else "#head-0")
            wait_fonts(cdp, ".h0-s0", 1)
            nodes = [active] + [query(cdp, f"#reader-{h}") for h in range(1, heads)]
            baseline = [settle_head(cdp, node, h)[0] for h, node in enumerate(nodes)]
            report["initialHeadErrors"] = [error(v, expected(queries[h], keys[h], values[h])) for h, v in enumerate(baseline)]
            report["initialError"] = report["initialHeadErrors"][0]
            for update in range(4):
                q = queries[0] * (0.8 if update % 2 else -0.7)
                before = metrics(cdp)
                start = time.perf_counter()
                attribute(cdp, owner, "style", f"--tick-0:{update + 2};" + ";".join(f"--query-0-{i}:{v:.12g}" for i, v in enumerate(q)))
                report["externalWritesAfterNavigation"] += 1
                actual, reads = settle_head(cdp, active, 0, tick=update + 2)
                row = {"milliseconds": (time.perf_counter() - start) * 1000, "error": error(actual, expected(q, keys[0], values[0])), "reads": reads, "rendererDelta": delta(metrics(cdp), before)}
                unrelated = [read_head(cdp, nodes[h], h)[1] for h in range(1, heads)]
                row["unrelatedMaximumOutputChange"] = max((float(np.max(np.abs(np.asarray(v) - baseline[h]))) for h, v in enumerate(unrelated, 1)), default=0)
                row["unrelatedHeadErrors"] = [error(v, expected(queries[h], keys[h], values[h])) for h, v in enumerate(unrelated, 1)]
                report["samples"].append(row)
                (directory / "results.json").write_text(json.dumps(report, indent=2))
            report["unrelatedHeadErrors"] = report["samples"][-1]["unrelatedHeadErrors"]
            report["sampledPeakRendererMiB"] = max(s["rendererRssMiB"] for s in memory.samples)
            report["domCounters"] = cdp.command("Memory.getDOMCounters")
        errors = [*report["initialHeadErrors"], *[r["error"] for r in report["samples"]], *[e for r in report["samples"] for e in r["unrelatedHeadErrors"]]]
        report["passed"] = all(e["rmse"] is not None and e["rmse"] < 0.005 for e in errors) and all(r["unrelatedMaximumOutputChange"] < 1e-7 for r in report["samples"])
        report["medianMilliseconds"] = statistics.median(r["milliseconds"] for r in report["samples"])
        report["meanStyleMilliseconds"] = statistics.mean(r["rendererDelta"].get("RecalcStyleDuration", 0) * 1000 for r in report["samples"])
        report["meanLayoutMilliseconds"] = statistics.mean(r["rendererDelta"].get("LayoutDuration", 0) * 1000 for r in report["samples"])
    except Exception as exc:  # noqa: BLE001 - Preserve diagnostics for any experiment failure.
        report["passed"] = False
        report["exception"] = str(exc)
    (directory / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"case": directory.name, **{k: report.get(k) for k in ("passed", "medianMilliseconds", "meanStyleMilliseconds", "exception")}}), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--heads", nargs="+", type=int, default=[1, 4, 12])
    parser.add_argument("--slots", type=int, default=8)
    parser.add_argument("--spectators", type=int, default=1024)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if min(args.heads) < 1 or args.slots < 1 or args.spectators < 0 or args.repeats < 1:
        parser.error("heads, slots and repeats must be positive; spectators must be nonnegative")
    for repeat in range(args.repeats):
        for heads in args.heads:
            for mode in (["broadcast", "local"] if repeat % 2 == 0 else ["local", "broadcast"]):
                run(heads, args.slots, args.spectators, mode, repeat)
