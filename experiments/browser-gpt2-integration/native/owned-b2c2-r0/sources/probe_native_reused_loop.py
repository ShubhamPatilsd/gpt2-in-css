"""Native ping-pong vector feedback; no scripts or external iteration ticks."""

import argparse
import json
import time
from pathlib import Path

from build_hybrid_twelve_block import regs
from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, query

ROOT = Path(__file__).resolve().parents[1]


def loop_parts(width, steps, centered=False, selective=False):
    """Reusable vector banks with finite event-driven control, not timed ticks."""
    css = regs(
        [
            "--pass",
            "--loop-ready",
            "--loop-ack",
            "--loop-phase",
            "--loop-captured-pass",
            "--loop-held",
        ]
        + [f"--loop-in-{i}" for i in range(width)]
        + [f"--loop-out-{i}" for i in range(width)]
        + [f"--lp-{b}-{i}" for b in range(2) for i in range(width + 1)]
        + [f"--saved-{b}-{i}" for b in range(2) for i in range(width + 1)]
    )
    css += "body{--pass:1;container-name:loopcontrol;--loop-phase:mod(calc(var(--pass) - 1),2);--loop-held:calc(1 - min(1,abs(var(--pass) - var(--loop-captured-pass))))}@keyframes loop-pulse{from{opacity:.99}to{opacity:1}}.loop-signals{position:fixed;width:1px;height:1px;top:0;left:0}"
    css += ".loop-scroll{position:fixed;top:-100000px;left:0;width:524288px;height:1px;overflow:scroll;visibility:hidden}.loop-track{width:1572864px;height:1px;position:relative}.loop-metric{position:absolute;top:0;left:0;height:1px}"
    timelines, anims = [], []
    output = "{child}"
    bank_css = []
    for bank in range(2):
        names = [f"--saved-{bank}-{i}" for i in range(width + 1)]
        bank_css.append(
            f".loop-bank-{bank}{{transition-property:{','.join(names)};transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end)}}"
        )
        metrics = []
        for i in range(width + 1):
            tl, key = f"--loop-t-{bank}-{i}", f"loop-k-{bank}-{i}"
            timelines.append(tl)
            anims.append(key)
            css += f"@keyframes {key}{{from{{--lp-{bank}-{i}:{-2 if centered else 0}}}to{{--lp-{bank}-{i}:1}}}}"
            metrics.append(
                f'<i class="loop-metric" style="width:calc(262144px + var(--saved-{bank}-{i}) * 128px);view-timeline:{tl} inline"></i>'
            )
        output = (
            f'<div class="loop-bank-{bank}"><div class="loop-scroll"><div class="loop-track">'
            + "".join(metrics)
            + "</div></div>"
            + output
            + "</div>"
        )
        css += f"@container loopcontrol style(--loop-phase:{bank}){{.loop-bank-{bank}{{transition-property:none;"
        css += ";".join(f"--saved-{bank}-{i}:var(--loop-out-{i})" for i in range(width))
        css += f";--saved-{bank}-{width}:var(--pass)}}}}"
        css += f"@container loopcontrol style(--loop-held:1){{.loop-bank-{bank}{{transition-property:{','.join(names)}}}}}"
        read_bank = 1 - bank
        css += f"@container loopcontrol style(--loop-phase:{bank}){{.loop-input{{"
        css += ";".join(
            f"--loop-in-{i}:calc((524288 / var(--lp-{read_bank}-{i}) - 524288 - 262144) / 128)"
            for i in range(width)
        )
        css += f";--loop-ready:calc(1 - min(1,abs(round(nearest,(524288 / var(--lp-{read_bank}-{width}) - 524288 - 262144) / 128,1) - var(--pass) + 1)))"
        css += f";--loop-ack:calc(1 - min(1,abs(round(nearest,(524288 / var(--lp-{bank}-{width}) - 524288 - 262144) / 128,1) - var(--pass))))}}}}"
    # Base transition lists precede the active and captured-state overrides.
    css = "".join(bank_css) + css
    css += "html{timeline-scope:" + ",".join(timelines) + "}"
    css += (
        ".loop-reader{animation-name:"
        + ",".join(anims)
        + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
        + ",".join(timelines)
        + ";}"
    )
    if selective:
        for phase in range(2):
            indices = [(1 - phase, i) for i in range(width + 1)] + [(phase, width)]
            css += f"@container loopcontrol style(--loop-phase:{phase}){{.loop-reader{{animation-name:"
            css += ",".join(f"loop-k-{bank}-{i}" for bank, i in indices)
            css += (
                ";animation-timeline:"
                + ",".join(f"--loop-t-{bank}-{i}" for bank, i in indices)
                + "}}"
            )
    css += (
        "@container loopcontrol style(--pass:1){.loop-input{--loop-ready:1;"
        + ";".join(f"--loop-in-{i}:var(--initial-{i},0)" for i in range(width))
        + "}}"
    )
    signals = []
    for step in range(1, steps + 1):
        css += f"@container loopreceipt style(--loop-ack:1){{@container loopcontrol style(--pass:{step}){{#loop-ready-{step}{{animation:loop-pulse 1ms both}}}}}}"
        css += f"body:has(#loop-captured-{step}.done){{--loop-captured-pass:{step}}}"
        if step < steps:
            css += f"body:has(#loop-captured-{step}.done) #loop-ack-{step}{{animation:loop-pulse 1ms both}}body:has(#loop-advanced-{step}.done){{--pass:{step + 1}}}"
        signals.append(
            f'<g id="loop-ready-{step}"></g><g id="loop-ack-{step}"></g><g id="loop-captured-{step}"><set attributeName="class" to="done" begin="loop-ready-{step}.animationend+0.001s" fill="freeze"/></g><g id="loop-advanced-{step}"><set attributeName="class" to="done" begin="loop-ack-{step}.animationend+0.001s" fill="freeze"/></g>'
        )
    import re

    if centered:
        # A centered progress carrier avoids serializing a tiny delta from 2/3
        # as a full-sized decimal. The inverse mapping is algebraically exact.
        css = re.sub(r"524288 / var\((--lp-\d+-\d+)\)", r"1572864 / (var(\1) + 2)", css)
    css += ".loop-input{container-name:loopreceipt}.loop-compute{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container loopreceipt style(--loop-ready:1){.loop-compute{content-visibility:visible}}"
    source = (
        '<div class="loop-reader"><div class="loop-input"><svg class="loop-signals">'
        + "".join(signals)
        + '</svg><div class="loop-compute">{child}</div></div></div>'
    )
    return source, output, css


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--centered", action="store_true")
    parser.add_argument("--selective", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/native-reused-loop"
    )
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    source, output, css = loop_parts(2, args.steps, args.centered, args.selective)
    css += "body{--initial-0:1;--initial-1:2}.compute{--loop-out-0:calc(var(--loop-in-0) + .25);--loop-out-1:calc(var(--loop-in-1) + var(--loop-in-0) / 16);width:1px;height:1px}"
    path = args.output / "index.html"
    path.write_text(
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + css
        + "</style><body>"
        + source.replace(
            "{child}",
            '<div class="compute">'
            + output.replace("{child}", '<i id="result"></i>')
            + "</div>",
        )
        + "</body>"
    )
    result = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "externalWritesAfterNavigation": 0,
        "samples": [],
    }
    with browser() as cdp:
        started = time.perf_counter()
        node = navigate(cdp, path, "#result")
        deadline = time.monotonic() + 30
        seen = None
        while time.monotonic() < deadline:
            values = props(cdp, node)
            state = {
                k: v
                for k, v in values.items()
                if k.startswith(("--pass", "--loop-", "--saved-"))
            }
            if state != seen:
                result["samples"].append(
                    {"milliseconds": (time.perf_counter() - started) * 1000, **state}
                )
                print(state, flush=True)
                seen = state
            if query(cdp, f"#loop-captured-{args.steps}.done"):
                break
            time.sleep(0.05)
        result["completed"] = bool(query(cdp, f"#loop-captured-{args.steps}.done"))
        expected = [
            1 + args.steps * 0.25,
            2 + (args.steps + 0.25 * args.steps * (args.steps - 1) / 2) / 16,
        ]
        actual = [float(seen[f"--loop-out-{i}"]) for i in range(2)]
        result.update(
            expected=expected,
            actual=actual,
            passed=result["completed"]
            and max(abs(a - b) for a, b in zip(actual, expected)) < 0.005,
        )
    (args.output / "results.json").write_text(json.dumps(result, indent=2))
    print({k: v for k, v in result.items() if k != "samples"}, flush=True)


if __name__ == "__main__":
    main()
