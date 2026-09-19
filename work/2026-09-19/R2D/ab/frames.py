#!/usr/bin/env python3
"""Per-frame phase costs from B0 parse_trace summaries. usage: frames.py label=path/to/-summary.json ..."""
import json, sys
cols = [("style", "style_ms"), ("layout", "layout_ms"), ("animate", "animate_ms"), ("prepaint", "prepaint_ms"), ("compInputs", "of_which_compositing_inputs_ms"), ("paintLC", "paint_lifecycle_ms"), ("hitTest", "hittest_ms"), ("other", "other_busy_ms")]
print("| run | token | wall s | frames | passes | whole-DOM | " + " | ".join(f"{c} ms/frame" for c, _ in cols) + " | hit tests | frame ms (busy/frames) |")
print("|---|---|---:|---:|---:|---:|" + "---:|" * len(cols) + "---:|---:|")
for arg in sys.argv[1:]:
    label, path = arg.split("=", 1)
    s = json.load(open(path))
    dom = s["dom_elements"]
    for w in s["tokens"]:
        f = max(1, w["frames"])
        whole = sum(1 for b in w.get("ult_biggest", []) if b[1] >= 0.5 * dom)
        print(f"| {label} | {w['token_index']} | {w['wall_ms']/1000:.1f} | {w['frames']} | {w['style_count']} | {whole} | " + " | ".join(f"{w[k]/f:.1f}" for _, k in cols) + f" | {w['hittest_count']} | {w['busy_ms']/f:.1f} |")
