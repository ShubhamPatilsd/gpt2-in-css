#!/usr/bin/env python3
"""Falsify CSS value-storage mechanisms without any JavaScript.

These are controlled storage experiments, not an autonomous model scheduler.
Python/CDP changes the input and control attributes, never copies output values
back into the document. Generated pages also prohibit script execution by CSP.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_signed_hvar_chain import quantize_float_rows
from profile_hybrid_twelve_block import (
    browser,
    error as vector_error,
    query,
    read_vector,
    settle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/hybrid-12block-profile/value-latch"


def error(actual, expected):
    result = vector_error(actual, expected)
    for name in ("rmse", "maximum"):
        if result[name] is not None and not math.isfinite(result[name]):
            result[name] = None
            result["overflow"] = True
    return result


def downstream_oracle(qkv):
    tensors = SafeTensors(MODEL_PATH)
    weight = np.asarray(tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64).T
    quantized = quantize_float_rows(weight, bits=9).reconstructed
    bias = np.asarray(tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64)
    return (np.asarray(qkv[:768]) / 64 @ quantized.T + bias).tolist()


def props(cdp, node):
    return {
        p["name"]: p["value"]
        for p in cdp.command("CSS.getComputedStyleForNode", {"nodeId": node})[
            "computedStyle"
        ]
    }


def attribute(cdp, node, name, value):
    cdp.command("DOM.setAttributeValue", {"nodeId": node, "name": name, "value": value})


def navigate(cdp, path, selector, observe_after_seconds=0, url=None, limit=30):
    if "<script" in path.read_text().lower():
        raise ValueError("Script in generated fixture")
    target_url = url or path.as_uri()
    cdp.command("Page.navigate", {"url": target_url})
    if observe_after_seconds:
        # Check that native progress does not depend on repeated forced-style
        # observations. Chromium keeps running while Python is not querying it.
        time.sleep(observe_after_seconds)
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        cdp.root_node = None
        try:
            node = query(cdp, selector)
            root = cdp.command("DOM.describeNode", {"nodeId": cdp.root_node})["node"]
            if node and root.get("documentURL") == target_url:
                return node
        except RuntimeError:
            pass
        time.sleep(0.05)
    raise TimeoutError(f"{selector}: document did not become available within {limit}s")


def scalar_fixture(mode):
    typed = '@property --saved{syntax:"<number>";inherits:true;initial-value:0}'
    rules = ""
    if mode == "delayed-transition":
        rules = (
            ".bank{--saved:var(--source);transition-property:none}"
            ".hold .bank{transition:--saved 1ms steps(1,end) 86400s}"
        )
    else:
        if mode == "paused-untyped":
            typed = ""
        iteration = "1" if mode == "filled-animation" else "infinite"
        rules = (
            f".bank{{animation:capture 1ms {iteration} both}}"
            ".hold .bank{animation-play-state:paused}"
            "@keyframes capture{0%,100%{--saved:var(--source)}}"
        )
    return (
        '<!doctype html><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        f"<style>{typed}"
        '@property --source{syntax:"<number>";inherits:true;initial-value:0}'
        f"{rules}.source{{--source:17.125}}.bank{{width:calc(var(--saved) * 1px);height:1px}}"
        '</style><body><div class="source"><div class="bank" id="bank"></div></div></body>'
    )


def scalar_screen(cdp):
    result = []
    for mode in (
        "paused-untyped",
        "paused-typed",
        "filled-animation",
        "delayed-transition",
    ):
        path = OUT / f"{mode}.html"
        path.write_text(scalar_fixture(mode))
        bank = navigate(cdp, path, "#bank")
        body, source = query(cdp, "body"), query(cdp, ".source")
        time.sleep(0.1)
        initial = float(props(cdp, bank)["--saved"])
        attribute(cdp, body, "class", "hold")
        props(cdp, bank)  # Establish the hold rule before changing the producer.
        attribute(cdp, source, "style", "--source:89.0625")
        time.sleep(0.15)
        held = float(props(cdp, bank)["--saved"])
        attribute(cdp, body, "class", "")
        time.sleep(0.1)
        resumed = float(props(cdp, bank)["--saved"])
        row = dict(mode=mode, initial=initial, held=held, resumed=resumed)
        row["pass"] = initial == held == 17.125 and resumed == 89.0625
        print(row, flush=True)
        result.append(row)
    return result


def vector_fixture(mode):
    source = OUT.parent / "content-gated/b0-qkv.html"
    count = 2304
    source_names = [f"--qkv-{i:03d}" for i in range(count)]
    saved_names = [f"--saved-{i:03d}" for i in range(count)]
    declarations = ";".join(f"{b}:var({a})" for a, b in zip(source_names, saved_names))
    registrations = "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in saved_names
    )
    if mode == "delayed-transition":
        rules = (
            f".bank{{{declarations};transition-property:none}}"
            f".hold .bank{{transition-property:{','.join(saved_names)};"
            "transition-duration:1ms;transition-timing-function:steps(1,end);transition-delay:86400s}"
        )
    else:
        registrations = ""  # The old recurrent model uses unregistered banks.
        rules = (
            ".bank{animation:capture 1ms infinite both}"
            ".hold .bank{animation-play-state:paused}"
            f"@keyframes capture{{0%,100%{{{declarations}}}}}"
        )
    # Keep the test's storage/readback subtree visible after the generation
    # receipt closes. Detach *all* QKV producers and view-timeline consumers.
    rules += (
        ".b0-qkv-gate{content-visibility:visible!important}"
        ".detached .b0-qkv>.scroller .metric{view-timeline-name:none!important}"
        ".detached .b0-qkv>.scroller{display:none!important}"
        '.detached .b0-qkv [class*="b0-qkv-c"],'
        ".detached .b0-qkv-receipt{animation:none!important}"
    )
    # A second real GPT-2 HVAR matvec consumes 768 captured coordinates. This
    # is a storage/transport circuit, not a transformer attention calculation:
    # it feeds Q / 64 into the attention-output projection with zero residual.
    downstream = (source.parent / "b0-attn.html").read_text()
    downstream_css = downstream.split("<style>", 1)[1].split("</style>", 1)[0]
    downstream_css = downstream_css.replace("}body{", "}.downstream{")
    downstream_body = downstream.split("<body>", 1)[1].split(
        '<i class="readback" id="measurement"', 1
    )[0]
    downstream_rules = ";".join(
        f"--ctx-{i:03d}:calc(var(--saved-{i:03d}) / 64);--x-{i:03d}:0"
        for i in range(768)
    )
    rules += f".downstream{{--epoch:1;{downstream_rules}}}"
    html = source.read_text().replace(
        "</style>", downstream_css + registrations + rules + "</style>"
    )
    needle = '<div id="b0-qkv-result">'
    if html.count(needle) != 1:
        raise RuntimeError("QKV output boundary changed")
    # Existing output is only an observer. The source values remain inherited;
    # a new bank captures them in the browser, not through a Python round trip.
    html = html.replace(
        needle,
        '<div class="bank" id="b0-qkv-result"><div class="downstream">'
        + downstream_body
        + "</div>",
        1,
    )
    path = OUT / f"qkv-{mode}.html"
    path.write_text(html)
    return path


def vector_screen(cdp, mode):
    path = vector_fixture(mode)
    bank = navigate(cdp, path, ".bank")
    body, output = query(cdp, "body"), query(cdp, "#b0-qkv-result")
    reference = json.loads((OUT.parent / "content-gated/reference.json").read_text())[
        "layers"
    ][0]
    source_initial, _ = settle(cdp, output, "qkv", 2304, limit=30)
    saved, _ = settle(cdp, bank, "saved", 2304, limit=30)
    consumer = query(cdp, "#b0-attn-result")
    downstream_initial, _ = settle(cdp, consumer, "r", 768, limit=30)
    phases = [
        dict(
            phase="initial",
            error=error(saved, source_initial),
            sourceReferenceError=error(source_initial, reference["qkv"][0]),
            downstreamReferenceError=error(
                downstream_initial, downstream_oracle(source_initial)
            ),
        )
    ]
    for phase, classes, state, expected in (
        ("hold", "hold", None, source_initial),
        ("detach", "hold detached", None, source_initial),
        ("change-input-while-detached", "hold detached", 1, source_initial),
        ("reattach-still-held", "hold", None, source_initial),
        ("resume", "", 1, reference["qkv"][1]),
    ):
        if state is not None:
            attribute(cdp, body, "style", reference["stageInputStyles"]["qkv"][state])
        attribute(cdp, body, "class", classes)
        time.sleep(0.1)
        saved, _ = settle(cdp, bank, "saved", 2304, limit=30)
        row = dict(phase=phase, error=error(saved, expected))
        downstream_values, _ = settle(cdp, consumer, "r", 768, limit=30)
        if phase != "resume":
            row["downstreamRetentionError"] = error(
                downstream_values, downstream_initial
            )
        else:
            row["downstreamChanged"] = error(downstream_values, downstream_initial)
            row["liveSourceError"] = error(
                read_vector(cdp, output, "qkv", 2304), expected
            )
            row["downstreamReferenceError"] = error(
                downstream_values, downstream_oracle(saved)
            )
        print(mode, row, flush=True)
        phases.append(row)
    return {
        "mode": mode,
        "downstream": "real 768-to-768 HVAR projection of captured Q / 64",
        "phases": phases,
    }


def automatic_screen(cdp, state=0, observe_after_seconds=0):
    """One-shot ready -> hold -> retire, using CSS events and SVG SMIL only."""
    source = vector_fixture("delayed-transition")
    html = source.read_text()
    reference = json.loads((OUT.parent / "content-gated/reference.json").read_text())[
        "layers"
    ][0]
    html = html.replace(
        "</style>", "body{" + reference["stageInputStyles"]["qkv"][state] + "}</style>"
    )
    html = html.replace(".hold .bank", "body:has(#hold-signal.hold) .bank")
    html = html.replace(".detached .b0-qkv", "body:has(#retire-signal.retired) .b0-qkv")
    bridge = (
        '<svg xmlns="http://www.w3.org/2000/svg" class="signals" width="1" height="1">'
        '<g id="capture-ready"></g><g id="hold-ready"></g>'
        '<g id="hold-signal"><set attributeName="class" to="hold" '
        'begin="capture-ready.animationend+0.001s" fill="freeze"/></g>'
        '<g id="retire-signal"><set attributeName="class" to="retired" '
        'begin="hold-ready.animationend+0.001s" fill="freeze"/></g></svg>'
    )
    rules = (
        ".signals{position:fixed;left:0;top:0}"
        ".downstream{content-visibility:hidden}"
        "body:has(#retire-signal.retired) .downstream{content-visibility:visible}"
        ".bank{--native-retired:0}"
        "body:has(#retire-signal.retired) .bank{--native-retired:1}"
        "@keyframes handshake{from{opacity:.99}to{opacity:1}}"
        "@container b0-qkv-receipt style(--gate-qkv:1){"
        "#capture-ready{animation:handshake 1ms both}}"
        "body:has(#hold-signal.hold) #hold-ready{animation:handshake 1ms both}"
    )
    html = html.replace("</style>", rules + "</style>")
    html = html.replace(
        '<div class="bank" id="b0-qkv-result">',
        '<div class="bank" id="b0-qkv-result">' + bridge,
    )
    path = OUT / f"automatic-retirement-state{state}.html"
    path.write_text(html)
    started = time.perf_counter()
    bank = navigate(cdp, path, ".bank", observe_after_seconds)
    retired_at_first_observation = props(cdp, bank).get("--native-retired") == "1"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if props(cdp, bank).get("--native-retired") == "1":
            break
        time.sleep(0.05)
    else:
        row = {
            "pass": False,
            "state": state,
            "error": "Native retirement signal did not fire",
            "diagnostics": {},
        }
        for selector in (
            "#capture-ready",
            "#hold-ready",
            "#hold-signal",
            "#retire-signal",
            ".b0-qkv-receipt",
        ):
            values = props(cdp, query(cdp, selector))
            row["diagnostics"][selector] = {
                k: values.get(k)
                for k in ("animation-name", "animation-play-state", "--gate-qkv")
            }
        print("automatic", row, flush=True)
        return row
    saved, _ = settle(cdp, bank, "saved", 2304, limit=30)
    consumer = query(cdp, "#b0-attn-result")
    output, _ = settle(cdp, consumer, "r", 768, limit=30)
    source_error = error(saved, reference["qkv"][state])
    consumer_error = error(output, downstream_oracle(saved))
    metric = props(cdp, query(cdp, ".b0-qkv>.scroller .metric"))
    scroller = props(cdp, query(cdp, ".b0-qkv>.scroller"))
    receiver = props(cdp, query(cdp, ".b0-qkv-c0"))
    row = {
        "state": state,
        "unobservedSecondsAfterNavigation": observe_after_seconds,
        "retiredAtFirstObservation": retired_at_first_observation,
        "automaticScheduler": True,
        "externalControlMutationsAfterNavigation": 0,
        "scope": "one-shot QKV capture and retirement, with a live downstream HVAR matvec",
        "downstreamStartsAfterRetirement": True,
        "sourceError": source_error,
        "consumerError": consumer_error,
        "sourceTimeline": metric["view-timeline-name"],
        "sourceDisplay": scroller["display"],
        "receiverAnimation": receiver["animation-name"],
        "coldIncludingObservationMilliseconds": (time.perf_counter() - started) * 1000,
    }
    row["pass"] = (
        source_error["maximum"] is not None
        and source_error["maximum"] < 0.002
        and consumer_error["maximum"] is not None
        and consumer_error["maximum"] < 0.005
        and row["sourceTimeline"] == "none"
        and row["sourceDisplay"] == "none"
        and row["receiverAnimation"] == "none"
    )
    print("automatic", row, flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-automatic", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "automaticScheduler": False,
        "externalIntermediateTransfers": 0,
        "holdDurationSeconds": 86400,
    }
    with browser() as cdp:
        report["browser"] = cdp.command("Browser.getVersion")
        if not args.only_automatic:
            report["scalar"] = scalar_screen(cdp)
            report["vector"] = []
            for row in report["scalar"]:
                if row["pass"]:
                    report["vector"].append(vector_screen(cdp, row["mode"]))
        report["automatic"] = [automatic_screen(cdp, state) for state in range(4)]
        report["unobservedAutomatic"] = automatic_screen(
            cdp, 0, observe_after_seconds=5
        )
    destination = "automatic-results.json" if args.only_automatic else "results.json"
    (OUT / destination).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
