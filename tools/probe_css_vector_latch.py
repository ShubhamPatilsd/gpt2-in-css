"""Test lossless aggregate CSS storage and native argument extraction.

Python/CDP writes only source inputs and the hold control. Chromium owns every
capture, extraction, and downstream computation; script execution is disabled.
"""

import json
import time
from pathlib import Path

from probe_native_value_latch import attribute, navigate, props
from profile_hybrid_twelve_block import browser, query

OUT = Path(__file__).resolve().parents[1] / "experiments/css-vector-latch"


def fixture():
    return """<!doctype html><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="script-src 'none'">
<style>
@property --a {syntax:"<number>";inherits:true;initial-value:0}
@property --b {syntax:"<number>";inherits:true;initial-value:0}
@property --c {syntax:"<number>";inherits:true;initial-value:0}
@property --q {syntax:"<number>";inherits:true;initial-value:0}
@property --saved {syntax:"*";inherits:true;initial-value:0,0,0}
@property --deferred {syntax:"*";inherits:true;initial-value:0}
@property --out0 {syntax:"<number>";inherits:true;initial-value:-999}
@property --out1 {syntax:"<number>";inherits:true;initial-value:-999}
@property --out2 {syntax:"<number>";inherits:true;initial-value:-999}
@property --out3 {syntax:"<number>";inherits:true;initial-value:-999}
@property --direct {syntax:"<number>";inherits:true;initial-value:-999}
@function --get0(--x <number>, --y <number>, --z <number>) returns <number> {result:var(--x)}
@function --get1(--x <number>, --y <number>, --z <number>) returns <number> {result:var(--y)}
@function --get2(--x <number>, --y <number>, --z <number>) returns <number> {result:var(--z)}
@function --query() returns <number> {result:var(--q)}
.source {--a:17.125;--b:-89.0625;--c:.123456789;--q:2}
.bank {--saved:var(--a),var(--b),var(--c);--deferred:calc(var(--a) * --query());transition:none}
.hold .bank {--saved:0,0,0;--deferred:0;transition-property:--saved,--deferred;transition-duration:1ms;transition-delay:86400s;transition-behavior:allow-discrete}
.consumer {--q:3;--out0:--get0(var(--saved));--out1:--get1(var(--saved));--out2:--get2(var(--saved));--out3:var(--deferred);--direct:--get1(1,2,3);width:calc(var(--out0) * 1px);height:1px}
</style><body><div class="source"><div class="bank" id="bank"><div class="consumer" id="consumer"></div></div></div></body>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "probe.html"
    path.write_text(fixture())
    result = {"runtimeJavaScript": False, "harnessJavaScript": False, "phases": []}
    with browser() as cdp:
        result["browser"] = cdp.command("Browser.getVersion")
        bank = navigate(cdp, path, "#bank")
        consumer = query(cdp, "#consumer")
        body, source = query(cdp, "body"), query(cdp, ".source")
        for phase in ("initial", "hold", "changed", "resumed"):
            if phase == "hold":
                attribute(cdp, body, "class", "hold")
            elif phase == "changed":
                attribute(
                    cdp, source, "style", "--a:57.5;--b:101.25;--c:-.987654321;--q:7"
                )
            elif phase == "resumed":
                attribute(cdp, body, "class", "")
            time.sleep(0.1)
            row = {
                "phase": phase,
                "stored": {
                    k: v
                    for k, v in props(cdp, bank).items()
                    if k in ("--saved", "--deferred")
                },
                "outputs": {
                    k: v
                    for k, v in props(cdp, consumer).items()
                    if k.startswith("--out") or k == "--direct"
                },
            }
            result["phases"].append(row)
            print(row, flush=True)
    (OUT / "results.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
