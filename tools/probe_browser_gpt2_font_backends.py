"""Chromium-only platform vs identity-avar2 font acceptance/arithmetic probe.

Eight glyph outputs are sampled, not a complete transformer timing. Supplied
matrix inputs are external component fixtures; no author/harness JavaScript.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from browser_gpt2_font_backend import identity_avar2
from build_matrix_backend_prototypes import axis_tag
from build_variable_font_scaling import inputs_for_size
from probe_native_value_latch import attribute, navigate
from profile_hybrid_twelve_block import browser, query

ROOT = Path(__file__).resolve().parents[1]


def run(directory, sizes, states, render_all=False):
    directory.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "Font-backend component with eight checked outputs; not pipeline timing",
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "cases": [],
    }
    for size in sizes:
        source = ROOT / f"experiments/matrix-scaling/{size}/variable-matvec.woff2"
        metadata = json.loads(source.with_name("reference.json").read_text())
        weights, initial = inputs_for_size(size)
        selected = np.linspace(0, size - 1, min(size, 8), dtype=int)
        inputs = [initial] + [
            np.random.default_rng(4821 + i).integers(0, 17, size=size) / 16
            for i in range(states - 1)
        ]
        for backend in ("original", "fontations"):
            font = source if backend == "original" else identity_avar2(source)
            settings = lambda vector: ",".join(
                f'"{axis_tag(i)}" {float(value):.12g}' for i, value in enumerate(vector)
            )
            page = directory / f"axes-{size}-{backend}.html"
            page.write_text(
                '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
                f'<style>@font-face{{font-family:Probe;src:url("{font.as_uri()}")}}body{{font:512px Probe; font-variation-settings:{settings(initial)}}}i{{display:block;position:absolute;top:0;left:0;width:max-content;height:1px;font-style:normal;font-kerning:none}}</style><body>'
                + "".join(
                    f'<i id="row-{i}">&#x{0xE000 + int(i):X};</i>'
                    for i in (range(size) if render_all else selected)
                )
            )
            result = {
                "axes": size,
                "backend": backend,
                "renderedOutputs": size if render_all else len(selected),
                "samples": [],
            }
            with browser(["--js-flags=--heap-growing-percent=10"]) as cdp:
                first = navigate(cdp, page, f"#row-{selected[0]}", limit=60)
                body = query(cdp, "body")
                nodes = [query(cdp, f"#row-{i}") for i in selected]
                # Platform font reporting forces font resolution without executing scripts.
                fonts = cdp.command("CSS.getPlatformFontsForNode", {"nodeId": first})[
                    "fonts"
                ]
                deadline = time.monotonic() + 5
                while (
                    not any(f["isCustomFont"] for f in fonts)
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.05)
                    fonts = cdp.command(
                        "CSS.getPlatformFontsForNode", {"nodeId": first}
                    )["fonts"]
                result["fonts"] = fonts
                result["accepted"] = any(f["isCustomFont"] for f in fonts)
                if result["accepted"]:
                    for state, vector in enumerate(inputs):
                        started = time.perf_counter()
                        attribute(
                            cdp,
                            body,
                            "style",
                            "font-variation-settings:" + settings(vector),
                        )
                        values = []
                        for node in nodes:
                            box = cdp.command("DOM.getBoxModel", {"nodeId": node})[
                                "model"
                            ]["content"]
                            values.append(
                                (box[2] - box[0]) * metadata["units_per_em"] / 512
                                - metadata["base_advance"]
                            )
                        expected = weights[selected].astype(np.float64) @ vector
                        result["samples"].append(
                            {
                                "state": state,
                                "milliseconds": (time.perf_counter() - started) * 1000,
                                "maximumDesignUnitError": float(
                                    np.max(np.abs(np.asarray(values) - expected))
                                ),
                            }
                        )
                result["arithmeticPassed"] = result["accepted"] and all(
                    sample["maximumDesignUnitError"] < 2 for sample in result["samples"]
                )
                try:
                    result["histogram"] = cdp.command(
                        "Browser.getHistogram",
                        {"name": "Blink.Fonts.VariableFontsRatio"},
                    )
                except RuntimeError as exc:
                    result["histogramUnavailable"] = str(exc)
                result["browser"] = cdp.command("Browser.getVersion")
            report["cases"].append(result)
            (directory / "results.json").write_text(json.dumps(report, indent=2))
            print(result, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[256, 257, 768])
    parser.add_argument("--states", type=int, default=4)
    parser.add_argument(
        "--render-all",
        action="store_true",
        help="Render every matrix row while checking eight sampled outputs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/browser-gpt2/font-backend-probe",
    )
    args = parser.parse_args()
    run(args.output.resolve(), args.sizes, args.states, args.render_all)
