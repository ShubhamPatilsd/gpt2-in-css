"""Isolate the native full-vocabulary text decoder's startup layout cost."""

import base64
import json
import time
from pathlib import Path

from probe_native_value_latch import navigate
from profile_hybrid_twelve_block import browser, metrics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/text-counter-probe"


def main():
    css = (ROOT / "experiments/browser-gpt2/app/runtime.css").read_text()
    start = css.index("@counter-style gpt2-vocabulary{")
    counter = css[start : css.index(".visible-output::after", start)]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "counter.css").write_text(
        counter
        + "p{font:32px sans-serif;counter-reset:token 15496}p::before{content:counter(token,gpt2-vocabulary)}"
    )
    (OUT / "index.html").write_text(
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><link rel="stylesheet" href="counter.css"><p id="result"></p>'
    )
    with browser() as cdp:
        started = time.perf_counter()
        node = navigate(cdp, OUT / "index.html", "#result")
        cdp.command("DOM.getBoxModel", {"nodeId": node})
        report = {
            "milliseconds": (time.perf_counter() - started) * 1000,
            "metrics": metrics(cdp),
        }
        (OUT / "results.json").write_text(json.dumps(report, indent=2))
        screenshot = cdp.command("Page.captureScreenshot", {"format": "png"})
        (OUT / "screenshot.png").write_bytes(base64.b64decode(screenshot["data"]))
        print(report, flush=True)


if __name__ == "__main__":
    main()
