"""Separate native allocation diagnostic; never mixed with latency benchmarks."""

import json
from pathlib import Path

from probe_native_value_latch import attribute
from profile_hybrid_twelve_block import browser, load, query, settle

OUT = Path(__file__).resolve().parents[1] / "experiments/browser-gpt2/memory-baseline"


def main():
    reference = json.loads((OUT / "reference.json").read_text())
    with browser() as cdp:
        node, _, _, _ = load(cdp, OUT / "index.html", "#core-result", "x", 768)
        body = query(cdp, "body")
        cdp.command("Memory.startSampling", {"samplingInterval": 32768})
        for state in range(1, 4):
            attribute(
                cdp,
                body,
                "style",
                f"--epoch:{state + 1};"
                + ";".join(
                    f"--x-{i:03d}:{v:.12g}"
                    for i, v in enumerate(reference["inputs"][state])
                ),
            )
            settle(
                cdp,
                node,
                "x",
                768,
                geometry_node=cdp.geometry_node,
                generation=state + 1,
            )
        profile = cdp.command("Memory.getSamplingProfile")["profile"]
        counters = cdp.command("Memory.getDOMCounters")
        cdp.command("Memory.stopSampling")
    report = {
        "profile": profile,
        "domCounters": counters,
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "scope": "native allocation samples during three teacher-forced updates; not RSS or timings",
    }
    (OUT / "native-allocations.json").write_text(json.dumps(report, indent=2))
    print(
        "DOM", counters, "allocation sample count", len(profile["samples"]), flush=True
    )
    for sample in sorted(
        profile["samples"], key=lambda item: item["total"], reverse=True
    )[:8]:
        print(sample, flush=True)


if __name__ == "__main__":
    main()
