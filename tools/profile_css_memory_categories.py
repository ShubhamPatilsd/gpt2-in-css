"""Separate Chromium native-memory diagnostic, never an inference benchmark."""

import argparse
import json
import time
from pathlib import Path

from benchmark_browser_gpt2_memory import MemorySampler
from probe_native_value_latch import attribute
from profile_hybrid_twelve_block import browser, load, query, settle


def dump(cdp):
    cdp.trace_complete = False
    cdp.command(
        "Tracing.start",
        {
            "transferMode": "ReturnAsStream",
            "traceConfig": {
                "recordMode": "recordContinuously",
                "includedCategories": ["disabled-by-default-memory-infra"],
                "excludedCategories": ["*"],
                "memoryDumpConfig": {"triggers": []},
            },
        },
    )
    request = cdp.command(
        "Tracing.requestMemoryDump",
        {"levelOfDetail": "detailed", "deterministic": False},
    )
    cdp.command("Tracing.end")
    deadline = time.monotonic() + 30
    while not cdp.trace_complete:
        if time.monotonic() > deadline:
            raise TimeoutError("memory trace completion")
        cdp.command("Browser.getVersion")
        time.sleep(0.02)
    handle = cdp.trace_completion["stream"]
    chunks = []
    while True:
        chunk = cdp.command("IO.read", {"handle": handle, "size": 1048576})
        if chunk.get("base64Encoded"):
            raise ValueError("Unexpected encoded JSON trace")
        chunks.append(chunk["data"])
        if chunk.get("eof"):
            break
    cdp.command("IO.close", {"handle": handle})
    trace = json.loads("".join(chunks))
    return request, [
        event for event in trace["traceEvents"] if "dumps" in event.get("args", {})
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--states", type=int, default=8)
    args = parser.parse_args()
    directory = args.directory.resolve()
    reference = json.loads((directory / "reference.json").read_text())
    report = {
        "scope": "native memory diagnostic with external critical-pressure signal; NOT allowed inference timing",
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
    }
    with browser() as cdp, MemorySampler(cdp.browser_pid) as memory:
        node, _, _, _ = load(cdp, directory / "index.html", "#core-result", "x", 768)
        body = query(cdp, "body")
        for state, inputs in enumerate(reference["inputs"][1 : args.states], 2):
            attribute(
                cdp,
                body,
                "style",
                f"--epoch:{state};"
                + ";".join(f"--x-{i:03d}:{v:.12g}" for i, v in enumerate(inputs)),
            )
            settle(
                cdp, node, "x", 768, geometry_node=cdp.geometry_node, generation=state
            )
        report["before"] = memory.snapshot()
        report["dumpRequest"], report["dumps"] = dump(cdp)
        cdp.command("Memory.simulatePressureNotification", {"level": "critical"})
        time.sleep(1)
        report["afterPressure"] = memory.snapshot()
        report["afterDumpRequest"], report["afterDumps"] = dump(cdp)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(
        {k: v for k, v in report.items() if k not in ("dumps", "afterDumps")},
        flush=True,
    )
    for event in report["dumps"]:
        allocators = event["args"]["dumps"].get("allocators", {})
        rows = []
        for name, data in allocators.items():
            attrs = data.get("attrs", {})
            size = attrs.get("size", attrs.get("allocated_objects_size", {})).get(
                "value", "0"
            )
            try:
                size = int(size, 16)
            except ValueError:
                continue
            if size:
                rows.append((size / 1048576, name))
        print("pid", event.get("pid"), sorted(rows, reverse=True)[:30], flush=True)


if __name__ == "__main__":
    main()
