"""Native controls regression: pause, prompt lock, resume, reset, EOS.

The scalar incrementer replaces expensive matmuls in this control-only fixture.
Its slower handshake is test-only; production never waits on a guessed runtime.
"""

import json
import time
from pathlib import Path

import build_hybrid_twelve_block as hybrid
from browser_gpt2_runtime import feedback
from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, query
from test_browser_gpt2_runtime import static_url

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/browser-gpt2/controls"


def fixture(directory, eos=False):
    front, output, css, timelines = feedback(4)
    css += hybrid.regs(["--epoch", "--token", "--winner", "--head-output-epoch"])
    css += (
        "html{timeline-scope:"
        + ",".join(timelines)
        + "}body{--prompt-token:10}.fake-metric{position:fixed;top:-100px;width:calc(var(--token)*1px);height:calc(var(--epoch)*1px);anchor-name:--fake}.fake-reader{position:fixed;top:-100px;width:anchor-size(--fake width,0px);height:anchor-size(--fake height,0px);container-type:size}.fake-result{--head-output-epoch:round(nearest,100cqb/1px,1);--winner:calc(round(nearest,100cqi/1px,1) + 1)}"
    )
    if eos:
        css += ".fake-result{--winner:if(style(--head-output-epoch:2):50256;else:calc(round(nearest,100cqi/1px,1) + 1))}"
    else:
        css += '[id^="token-"][id$="-ready"]{animation-duration:500ms!important}'
    signals = '<svg xmlns="http://www.w3.org/2000/svg" class="native-signals"><g id="run-start"></g><g id="run-latched"><set attributeName="class" to="done" begin="run-start.animationend+0.001s" fill="freeze"/></g></svg>'
    model = front.replace(
        "{child}",
        '<i class="fake-metric"></i><div class="fake-reader"><div class="fake-result">'
        + output
        + "</div></div>",
    )
    controls = (
        '<label><input id="run" type="checkbox" '
        + ("checked" if eos else "")
        + '>Run</label><form action="index.html"><button id="reset">Reset</button></form>'
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text(
        '<!doctype html><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>'
        + css
        + "</style><body>"
        + controls
        + signals
        + model
        + "</body>"
    )


def click(cdp, selector):
    box = cdp.command("DOM.getBoxModel", {"nodeId": query(cdp, selector)})["model"][
        "content"
    ]
    point = {
        "x": (box[0] + box[2]) / 2,
        "y": (box[1] + box[5]) / 2,
        "button": "left",
        "clickCount": 1,
    }
    cdp.command("Input.dispatchMouseEvent", dict(type="mousePressed", **point))
    cdp.command("Input.dispatchMouseEvent", dict(type="mouseReleased", **point))


def wait_for(cdp, selector, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if query(cdp, selector):
            return
        time.sleep(0.03)
    raise AssertionError(f"No native completion: {selector}")


def values(cdp):
    p = props(cdp, query(cdp, "#tokens"))
    return int(float(p["--epoch"])), [
        int(float(p[f"--saved-token-{i}"])) for i in range(1, 5)
    ]


def main():
    report = {}
    normal = OUT / "pause-reset"
    fixture(normal)
    with static_url(normal, True) as url, browser() as cdp:
        navigate(cdp, normal / "index.html", "#tokens", url=url)
        assert not query(cdp, "#run:checked")
        assert not query(cdp, "#token-1-captured.done")
        click(cdp, "#run")
        wait_for(cdp, "#run-latched.done")
        click(cdp, "#run")
        attribute(cdp, query(cdp, "body"), "style", "--prompt-token:90")
        time.sleep(0.7)
        assert values(cdp) == (1, [11, -1, -1, -1]), values(cdp)
        assert props(cdp, query(cdp, ".feedback-reader"))["--frozen-prompt"] == "10"
        assert not query(cdp, "#token-1-captured.done")
        report["pauseAndPromptLock"] = True
        click(cdp, "#run")
        wait_for(cdp, "#token-4-captured.done")
        assert values(cdp) == (4, [11, 12, 13, 14]), values(cdp)
        report["resume"] = True
        click(cdp, "#reset")
        time.sleep(0.2)
        cdp.root_node = None
        assert not query(cdp, "#run:checked")
        assert not query(cdp, "#run-latched.done")
        assert values(cdp) == (1, [11, -1, -1, -1]), values(cdp)
        report["nativeFormReset"] = True
    eos = OUT / "eos"
    fixture(eos, True)
    with static_url(eos, True) as url, browser() as cdp:
        navigate(cdp, eos / "index.html", "#tokens", url=url)
        wait_for(cdp, "#eos-done.done")
        time.sleep(0.3)
        assert values(cdp) == (2, [11, 50256, -1, -1]), values(cdp)
        assert not query(cdp, "#token-3-captured.done")
        report["eosStopsBeforeNextEpoch"] = True
    report.update(runtimeJavaScript=False, harnessJavaScript=False)
    (OUT / "results.json").write_text(json.dumps(report, indent=2))
    print(report, flush=True)


if __name__ == "__main__":
    main()
