"""Test Chromium's native remembered-size state as a numeric latch.

No animations or transitions store the values. CSS retains intrinsic dimensions
when contents are skipped. Python supplies diagnostic inputs and reads boxes;
it does not compute, restore, or replay the saved state into the page.
"""

import argparse
import json
import time
from pathlib import Path

from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, query

OUT = Path(__file__).resolve().parents[1] / "experiments/css-remembered-size"


def fixture(variant="direct"):
    css = (
        "body{--x:123.125;--y:456.75}"
        ".latch{position:fixed;left:0;top:-100000px;width:max-content;height:max-content;"
        "contain-intrinsic-size:auto 0px;anchor-name:--saved}"
        ".value{display:block;width:calc(var(--x)*1px);height:calc(var(--y)*1px)}"
        ".hold .latch{content-visibility:hidden}"
        ".removed .wrapper{display:none}"
        ".reader{position:fixed;left:0;top:0;container-type:size;"
        "width:anchor-size(--saved width,0px);height:anchor-size(--saved height,0px)}"
        '@property --actual-x{syntax:"<number>";inherits:true;initial-value:-1}'
        '@property --actual-y{syntax:"<number>";inherits:true;initial-value:-1}'
        ".output{--actual-x:calc(100cqi/1px);--actual-y:calc(100cqb/1px)}"
    )
    if variant != "direct":
        css += (
            ".wrapper{position:fixed;left:0;top:-100000px;width:max-content;height:max-content;anchor-name:--saved}"
            ".latch{position:static;anchor-name:none}"
        )
    if variant == "auto":
        css += ".wrapper{top:0}.latch,.hold .latch{content-visibility:auto}.hold .wrapper{top:-100000px}"
    return (
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + css
        + '</style><body><div class="wrapper"><div class="latch"><i class="value"></i></div></div>'
        '<div class="reader"><i id="output" class="output"></i></div></body>'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--variant", choices=("direct", "wrapped", "auto"), default="direct"
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / (args.variant + ".html")
    path.write_text(fixture(args.variant))
    report = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "nativeStorage": "contain-intrinsic-size auto; no delayed transitions",
        "samples": [],
        "variant": args.variant,
    }
    with browser() as cdp:
        output = navigate(cdp, path, "#output")
        body = query(cdp, "body")
        report["browser"] = cdp.command("Browser.getVersion")
        for phase, classes, x, y, expected in (
            ("initial", "", 123.125, 456.75, [123.125, 456.75]),
            ("held", "hold", 123.125, 456.75, [123.125, 456.75]),
            ("changed-source", "hold", 789.5, 987.25, [123.125, 456.75]),
            ("removed", "hold removed", 333.5, 777.25, [0.0, 0.0]),
            ("restored", "hold", 333.5, 777.25, [123.125, 456.75]),
            ("rewritten", "", 333.5, 777.25, [333.5, 777.25]),
            ("reheld", "hold", 333.5, 777.25, [333.5, 777.25]),
            ("changed-again", "hold", 1.0, 2.0, [333.5, 777.25]),
        ):
            attribute(cdp, body, "class", classes)
            attribute(cdp, body, "style", f"--x:{x};--y:{y}")
            time.sleep(0.15)
            values = props(cdp, output)
            actual = [float(values[n]) for n in ("--actual-x", "--actual-y")]
            row = {
                "phase": phase,
                "actual": actual,
                "expected": expected,
                "passed": actual == expected,
            }
            if phase != "removed":
                latch = props(cdp, query(cdp, ".latch"))
                row["latchGeometry"] = {
                    key: latch[key]
                    for key in (
                        "width",
                        "height",
                        "contain-intrinsic-width",
                        "contain-intrinsic-height",
                        "content-visibility",
                    )
                }
            report["samples"].append(row)
            print(row, flush=True)
    report["passed"] = all(r["passed"] for r in report["samples"])
    (OUT / (args.variant + "-results.json")).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
