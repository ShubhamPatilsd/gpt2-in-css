"""Real 50,257-row head at long epochs, with Python/CDP observation only.

Externally supplied hidden vectors are explicitly component fixtures, not an
autonomous inference benchmark. The expected token never enters page markup.
"""

import json
import time
from pathlib import Path

from browser_gpt2_head_receipts import split_head_receipt
from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, query
from test_browser_gpt2_components import wait_fonts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/head-long-epochs"


def main():
    source = ROOT / "experiments/browser-gpt2/head-two-pass"
    reference = json.loads((source / "reference.json").read_text())
    html, css = split_head_receipt(
        (source / "head-body.html").read_text(),
        (source / "head.css").read_text(),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    initial = ";".join(f"--h{i}:{v:.12g}" for i, v in enumerate(reference["hidden"][0]))
    (OUT / "head.css").write_text(css)
    (OUT / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        '<link rel="stylesheet" href="head.css"><style>body{'
        + initial
        + "}</style><body>"
        + html.replace("{child}", "")
        + "</body>"
    )
    result = {
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "mode": "externally supplied head-input component diagnostic",
        "samples": [],
    }
    with browser(["--js-flags=--heap-growing-percent=10"]) as cdp:
        node = navigate(cdp, OUT / "index.html", "#head-result", limit=180)
        result["browser"] = cdp.command("Browser.getVersion")
        wait_fonts(cdp, '.head-row[data-token="0"]', 6)
        body = query(cdp, "body")
        epochs = list(range(14, 14 + len(reference["hidden"])))
        epochs[-1] = 1024
        for state, (epoch, hidden) in enumerate(zip(epochs, reference["hidden"])):
            attribute(
                cdp,
                body,
                "style",
                f"--head-input-epoch:{epoch};"
                + ";".join(f"--h{i}:{v:.12g}" for i, v in enumerate(hidden)),
            )
            begin = time.perf_counter()
            previous, stable = None, 0
            while time.perf_counter() - begin < 60:
                values = props(cdp, node)
                actual = tuple(
                    float(values[n]) for n in ("--head-output-epoch", "--winner")
                )
                stable = stable + 1 if actual == previous else 0
                if actual[0] == epoch and stable >= 4:
                    break
                previous = actual
                time.sleep(0.03)
            expected = reference["fixtures"][state]["q16BucketWinner"]
            row = {
                "state": reference["sourceStates"][state],
                "epoch": epoch,
                "actualEpoch": actual[0],
                "winner": actual[1],
                "expectedWinner": expected,
                "passed": actual == (epoch, expected),
            }
            result["samples"].append(row)
            result["passed"] = all(r["passed"] for r in result["samples"])
            (OUT / "results.json").write_text(json.dumps(result, indent=2))
            print(row, flush=True)
            if not row["passed"]:
                break


if __name__ == "__main__":
    main()
