"""Compare real core sequences with OS RSS sampling; no page JavaScript.

Input writes are teacher-forced component diagnostics, not autonomous inference.
RSS is resident memory, not macOS physical footprint; process sums double-count
shared pages. Sampling is independent of CDP and does not flush browser layout.
"""

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from browser_gpt2_core import cache_names
from decode_css_cache_diagnostic import expected_integer_packets
from probe_native_value_latch import attribute, error, props
from profile_hybrid_twelve_block import (
    browser,
    load,
    metrics,
    query,
    read_vector,
    settle,
)


class MemorySampler:
    def __init__(self, pid):
        self.pid = pid
        self.samples = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def snapshot(self):
        raw = subprocess.check_output(
            ["ps", "-axo", "pid=,ppid=,rss=,command="], text=True
        )
        rows = {}
        for line in raw.splitlines():
            fields = line.strip().split(None, 3)
            if len(fields) == 4:
                pid, parent, rss, command = fields
                rows[int(pid)] = (int(parent), int(rss), command)
        descendants = {self.pid}
        while True:
            expanded = descendants | {
                pid for pid, (parent, _, _) in rows.items() if parent in descendants
            }
            if expanded == descendants:
                break
            descendants = expanded
        selected = [rows[pid] for pid in descendants if pid in rows]
        return {
            "seconds": time.monotonic(),
            "browserTreeRssMiB": sum(row[1] for row in selected) / 1024,
            "rendererRssMiB": sum(
                row[1] for row in selected if "--type=renderer" in row[2]
            )
            / 1024,
        }

    def run(self):
        while not self.stop_event.is_set():
            self.samples.append(self.snapshot())
            self.stop_event.wait(0.5)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_event.set()
        self.thread.join()


def benchmark(
    directory,
    output,
    static_cache_diagnostic=False,
    continue_on_error=False,
    heap_growth_percent=0,
):
    reference = json.loads((directory / "reference.json").read_text())
    packed = reference.get(
        "cacheCodec", "numeric12" if reference.get("packedCacheBits") else "scalar"
    )
    packed = False if packed == "scalar" else packed
    if packed and static_cache_diagnostic:
        raise ValueError("Literal cache ablation is only implemented for scalar caches")
    result = {
        "directory": str(directory),
        "samples": [],
        "runtimeJavaScript": False,
        "harnessJavaScript": False,
        "measurement": "OS sampled RSS, not physical footprint",
        "mode": "teacher-forced core diagnostic; not autonomous pipeline timing",
    }
    result["externalStaticCacheDiagnostic"] = static_cache_diagnostic
    flags = (
        [f"--js-flags=--heap-growing-percent={heap_growth_percent}"]
        if heap_growth_percent
        else []
    )
    result["browserArguments"] = flags
    with browser(flags) as cdp, MemorySampler(cdp.browser_pid) as memory:
        node, _, cold, _ = load(cdp, directory / "index.html", "#core-result", "x", 768)
        result["coldMilliseconds"] = cold
        body = query(cdp, "body")
        stored = {}
        for state, inputs in enumerate(reference["inputs"]):
            before = metrics(cdp)
            begin = time.perf_counter()
            if state:
                attribute(
                    cdp,
                    body,
                    "style",
                    f"--epoch:{state + 1};"
                    + ";".join(
                        f"--x-{i:03d}:{value:.12g}" for i, value in enumerate(inputs)
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
            elapsed = (time.perf_counter() - begin) * 1000
            after = metrics(cdp)
            values = read_vector(cdp, node, "x", 768)
            retention = []
            for layer in range(reference["blocks"]):
                bank = props(cdp, query(cdp, f'.kv-bank[data-layer="{layer}"]'))
                for slot in range(state + 1):
                    if isinstance(packed, str) and packed.startswith("integer"):
                        if slot == state:
                            stored[layer, slot] = expected_integer_packets(
                                bank, slot, packed
                            )
                        else:
                            retention.append(
                                int(
                                    any(
                                        float(bank[name]) != expected
                                        for name, expected in stored[
                                            layer, slot
                                        ].items()
                                    )
                                )
                            )
                        continue
                    actual = [bank[name] for name in cache_names(slot, packed)]
                    if slot == state:
                        stored[layer, slot] = actual
                    retention.append(0 if actual == stored[layer, slot] else 1)
            numerical = error(values, reference["outputs"][state])
            row = {
                "epoch": state + 1,
                "milliseconds": elapsed,
                "rendererCountersSeconds": {
                    key: after[key] - before[key]
                    for key in (
                        "TaskDuration",
                        "RecalcStyleDuration",
                        "LayoutDuration",
                        "TaskOtherDuration",
                        "ScriptDuration",
                        "V8CompileDuration",
                    )
                },
                "memory": memory.snapshot(),
                "error": numerical,
                "retentionMaximum": max(retention, default=0),
                "values": values,
                "passed": numerical["rmse"] is not None
                and numerical["rmse"] < 0.02
                and max(retention, default=0) == 0,
            }
            result["samples"].append(row)
            print(
                {key: value for key, value in row.items() if key != "values"},
                flush=True,
            )
            output.write_text(json.dumps(result, indent=2))
            if not row["passed"] and not continue_on_error:
                raise AssertionError("Core numerical or cache-retention check failed")
            if static_cache_diagnostic:
                # Causal diagnostic ONLY: replace captured browser values with
                # CSS literals, removing the need for native delayed transitions.
                # This is NOT an allowed inference implementation or a speed claim.
                for layer in range(reference["blocks"]):
                    declarations = ["transition-property:none"]
                    for slot in range(state + 1):
                        values = stored[layer, slot]
                        declarations.extend(
                            f"--kv-{kind}{slot}-{i:03d}:{values[offset + i]}"
                            for kind, offset in (("k", 0), ("v", 768))
                            for i in range(768)
                        )
                    attribute(
                        cdp,
                        query(cdp, f'.kv-bank[data-layer="{layer}"]'),
                        "style",
                        ";".join(declarations),
                    )
        result["sampledPeak"] = {
            key: max(
                row[key]
                for row in memory.samples + [r["memory"] for r in result["samples"]]
            )
            for key in ("browserTreeRssMiB", "rendererRssMiB")
        }
        result["memorySamples"] = memory.samples
        result["passed"] = all(row["passed"] for row in result["samples"])
        output.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--static-cache-diagnostic", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--heap-growth-percent", type=int, choices=(0, 10, 25, 50, 100), default=0
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    benchmark(
        args.directory.resolve(),
        args.output.resolve(),
        args.static_cache_diagnostic,
        args.continue_on_error,
        args.heap_growth_percent,
    )
