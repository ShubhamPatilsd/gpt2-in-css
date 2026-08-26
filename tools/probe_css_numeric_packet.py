"""Test integer packets in CSS storage without any geometry transport or JS."""

import json
from pathlib import Path

from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, query

OUT = Path(__file__).resolve().parents[1] / "experiments/browser-gpt2/numeric-packet"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    css, body, cases = [], [], []
    for syntax in ("number", "integer"):
        for bits in range(8, 13):
            for sample, (a, b) in enumerate(
                (
                    (1, 1),
                    (37, 241),
                    (2**bits - 2, 2**bits - 2),
                    (123, 2 ** (bits - 1) + 17),
                )
            ):
                name = f"{syntax}-{bits}-{sample}"
                prop = f"--packet-{name}"
                radix = 2**bits
                css.append(
                    f'@property {prop}{{syntax:"<{syntax}>";inherits:true;initial-value:0}}'
                )
                css.append(f"#{name}{{{prop}:calc({a} + {radix} * {b})}}")
                body.append(
                    f'<div id="{name}"><i id="read-{name}" style="display:block;width:calc(mod(var({prop}),{radix}) * 1px);height:calc(round(down,calc(var({prop}) / {radix}),1) * 1px)"></i></div>'
                )
                cases.append((name, prop, bits, a, b))
    page = OUT / "index.html"
    page.write_text(
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + "".join(css)
        + "</style><body>"
        + "".join(body)
    )
    rows = []
    with browser() as cdp:
        navigate(cdp, page, "#number-8-0")
        for name, prop, bits, a, b in cases:
            values = props(cdp, query(cdp, f"#read-{name}"))
            actual = [
                float(values["width"].removesuffix("px")),
                float(values["height"].removesuffix("px")),
            ]
            rows.append(
                {
                    "case": name,
                    "bits": bits,
                    "serializedPacket": values[prop],
                    "expected": [a, b],
                    "actual": actual,
                    "passed": actual == [a, b],
                }
            )
    (OUT / "results.json").write_text(json.dumps(rows, indent=2))
    print(rows, flush=True)


if __name__ == "__main__":
    main()
