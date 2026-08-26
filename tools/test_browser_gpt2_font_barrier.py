"""A missing font must keep the native readiness barrier closed."""

import json
import os
import time
from pathlib import Path

from browser_gpt2_runtime import font_barrier
from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, query
from test_browser_gpt2_runtime import static_url

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/font-barrier-probe"


def main():
    manifest = json.loads(
        (ROOT / "experiments/browser-gpt2/demo/font-witnesses.json").read_text()
    )
    font = Path(next(iter(manifest)))
    OUT.mkdir(parents=True, exist_ok=True)
    face = (
        '@font-face{font-family:Witness;src:url("'
        + font.as_uri()
        + '") format("woff2")}'
    )
    html, css, _ = font_barrier(face, OUT)
    face = face.replace(font.as_uri(), os.path.relpath(font, OUT))
    css = (
        face
        + css
        + "@keyframes native-handshake{from{opacity:.99}to{opacity:1}}.native-signals{position:fixed;top:0;left:0;width:1px;height:1px}"
    )
    (OUT / "index.html").write_text(
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + css
        + "</style><body>"
        + html
        + "</body>"
    )
    report = []
    for blocked in (False, True):
        with static_url(OUT, True) as url, browser() as cdp:
            if blocked:
                cdp.command("Network.enable")
                cdp.command("Network.setBlockedURLs", {"urls": ["*" + font.name + "*"]})
            navigate(cdp, OUT / "index.html", ".font-status", url=url)
            time.sleep(1)
            ready = query(cdp, "#fonts-loaded.done") != 0
            width = props(cdp, query(cdp, ".font-status"))["width"]
            assert ready != blocked, (blocked, ready, width)
            report.append(
                {
                    "blocked": blocked,
                    "nativeReady": ready,
                    "width": width,
                    "passed": True,
                }
            )
    (OUT / "results.json").write_text(json.dumps(report, indent=2))
    print(report, flush=True)


if __name__ == "__main__":
    main()
