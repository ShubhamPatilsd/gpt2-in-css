"""Chromium typed-property packet precision and retention; no JavaScript."""

import json
import time
from pathlib import Path

from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, query

OUT = Path(__file__).resolve().parents[1] / "experiments/css-numeric-packets"


def fixture():
    css = '@property --source{syntax:"<number>";inherits:true;initial-value:0}'
    cases = []
    for kind, syntax, unit, initial in (
        ("number", "<number>", "", "0"),
        ("integer", "<integer>", "", "0"),
        ("length", "<length>", "px", "0px"),
        ("angle", "<angle>", "deg", "0deg"),
        ("expression", "*", "", "0"),
    ):
        for bits, lanes in ((6, 3), (6, 5), (8, 2), (8, 3), (9, 2), (9, 3), (10, 2), (10, 3), (12, 2), (15, 2), (16, 3)):
            name = f"--{kind}-{bits}x{lanes}"
            radix = 2**bits
            codes = [radix - 3 - i * 17 for i in range(lanes)]
            packet = sum(c * radix**i for i, c in enumerate(codes))
            css += f'@property {name}{{syntax:"{syntax}";inherits:true;initial-value:{initial}}}'
            expression = (
                f"calc(({packet} + var(--source))"
                + (f" * 1{unit}" if unit else "")
                + ")"
            )
            css += f".bank{{{name}:{expression}}}.hold .bank{{{name}:{initial}}}"
            normalized = f"(var({name}) / 1{unit})" if unit else f"var({name})"
            outputs = []
            for lane in range(lanes):
                out = f"--out-{kind}-{bits}x{lanes}-{lane}"
                outputs.append(out)
                css += f'@property {out}{{syntax:"<number>";inherits:true;initial-value:-999}}'
                css += f".consumer{{{out}:mod(round(down,calc({normalized} / {radix**lane}),1),{radix})}}"
            cases.append({"name": name, "packet": packet, "codes": codes, "outputs": outputs})
    css += (
        ".hold .bank{transition-property:"
        + ",".join(c["name"] for c in cases)
        + ";transition-duration:1ms;transition-delay:86400s;transition-behavior:allow-discrete}"
    )
    page = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + css
        + '</style><body><div class="bank" id="bank"><div class="consumer" id="consumer"></div></div></body>'
    )
    return page, cases


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    page, cases = fixture()
    path = OUT / "index.html"
    path.write_text(page)
    result = {"runtimeJavaScript": False, "harnessJavaScript": False, "phases": []}
    with browser() as cdp:
        bank = navigate(cdp, path, "#bank")
        body, consumer = query(cdp, "body"), query(cdp, "#consumer")
        result["browser"] = cdp.command("Browser.getVersion")
        for phase in ("initial", "held", "source-changed"):
            if phase == "held":
                attribute(cdp, body, "class", "hold")
            elif phase == "source-changed":
                attribute(cdp, body, "style", "--source:99999")
            time.sleep(0.1)
            stored, outputs = props(cdp, bank), props(cdp, consumer)
            rows = []
            for case in cases:
                actual = [float(outputs[n]) for n in case["outputs"]]
                rows.append(
                    case
                    | {
                        "stored": stored[case["name"]],
                        "actual": actual,
                        "passed": actual == case["codes"],
                    }
                )
            result["phases"].append({"phase": phase, "cases": rows})
            print(
                phase,
                [(r["name"], r["stored"], r["actual"], r["passed"]) for r in rows],
                flush=True,
            )
    (OUT / "results.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
