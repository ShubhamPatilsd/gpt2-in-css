"""Can an unevaluated numeric expression be retained as one native transition?"""

import json
import time
from pathlib import Path

from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, query

OUT = Path(__file__).resolve().parents[1] / "experiments/browser-gpt2/expression-latch"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    css, body, cases = [], [], []
    for bits in (9, 12, 16, 18, 20, 24):
        for syntax in ("*", "<number>"):
            name = f"p{bits}-{'expression' if syntax == '*' else 'number'}"
            packet = f"--{name}"
            radix = 2**bits
            a, b = radix - 2, radix // 2 + 17
            css += [
                f'@property {packet}{{syntax:"{syntax}";inherits:true;initial-value:0}}',
                f"#{name}{{{packet}:calc(var(--a) + {radix} * var(--b));transition-property:none}}",
                f".hold #{name}{{transition:{packet} 1ms steps(1,end) 86400s allow-discrete}}",
            ]
            body.append(
                f'<div class="source" id="s-{name}" style="--a:{a};--b:{b}"><div id="{name}"><i id="r-{name}" style="display:block;width:calc(mod(var({packet}),{radix}) * 1px);height:calc(round(down,calc(var({packet}) / {radix}),1) * 1px)"></i></div></div>'
            )
            cases.append((name, packet, [a, b]))
    page = OUT / "index.html"
    page.write_text(
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + "".join(css)
        + "</style><body>"
        + "".join(body)
    )
    rows = []
    with browser() as cdp:
        navigate(cdp, page, "#p9-expression")
        body_node = query(cdp, "body")
        for name, packet, expected in cases:
            reader = query(cdp, f"#r-{name}")

            def read(reader=reader, packet=packet):
                p = props(cdp, reader)
                box = cdp.command("DOM.getBoxModel", {"nodeId": reader})["model"]
                return {
                    "values": [box["width"], box["height"]],
                    "serialized": p[packet],
                }

            initial = read()
            attribute(cdp, body_node, "class", "hold")
            props(cdp, reader)
            attribute(cdp, query(cdp, f"#s-{name}"), "style", "--a:37;--b:241")
            time.sleep(0.06)
            held = read()
            attribute(cdp, body_node, "class", "")
            time.sleep(0.03)
            resumed = read()
            rows.append(
                {
                    "case": name,
                    "expected": expected,
                    "initial": initial,
                    "held": held,
                    "resumed": resumed,
                    "passed": initial["values"] == held["values"] == expected
                    and resumed["values"] == [37, 241],
                }
            )
    (OUT / "results.json").write_text(json.dumps(rows, indent=2))
    print(rows, flush=True)


if __name__ == "__main__":
    main()
