#!/usr/bin/env python3
"""Attribute trace time without double-counting nested Chromium events."""

import argparse
import collections
import heapq
import json
from pathlib import Path


def trace_categories(path):
    try:
        import ijson
    except ImportError:
        if path.stat().st_size > 64 * 1024 * 1024:
            raise RuntimeError(
                "Large trace: run with uv run --with ijson python tools/analyze_hybrid_profile.py ..."
            )
        events = json.loads(path.read_text())["traceEvents"]
    else:
        # Millions of per-timeline leaf events are already nested in the frame
        # and style phases. Do not materialize them or count their time twice.
        with path.open("rb") as stream:
            events = [
                e
                for e in ijson.items(stream, "traceEvents.item", use_float=True)
                if e.get("name") != "AnimationTimeline::serviceAnimations"
            ]
    threads = {
        (e["pid"], e["tid"])
        for e in events
        if e.get("name") == "thread_name"
        and e.get("args", {}).get("name") == "CrRendererMain"
    }
    font_events = any(
        e.get("name") == "InlineNode::ShapeTextIncludingFirstLine" for e in events
    )
    categories = {
        "RunTask": ("Other main-thread work", 0),
        "UpdateLayoutTree": ("Style recalculation", 2),
        "LocalFrameView::RunPaintLifecyclePhase": (
            "Paint/compositing lifecycle overhead",
            1,
        ),
        "LocalFrameView::RunStyleAndLayoutLifecyclePhases": (
            "Style/layout lifecycle overhead",
            1,
        ),
        "Layout": (
            "Layout excluding font shaping"
            if font_events
            else "Layout including font shaping",
            3,
        ),
        "InlineNode::ShapeTextIncludingFirstLine": ("Font shaping", 4),
        "PrePaint": ("Pre-paint", 2),
        "Blink.CompositingInputs.UpdateTime": ("Compositing inputs", 2),
        "Paint": ("Paint", 3),
        "PageAnimator::serviceScriptedAnimations": ("Animation frame servicing", 2),
    }
    intervals = collections.defaultdict(list)
    for e in events:
        thread = e.get("pid"), e.get("tid")
        if (
            thread in threads
            and e.get("ph") == "X"
            and e.get("name") in categories
            and e.get("dur", 0) > 0
        ):
            category, priority = categories[e["name"]]
            intervals[thread].append((e["ts"], e["ts"] + e["dur"], category, priority))
    totals = collections.Counter()
    for spans in intervals.values():
        points = []
        for i, (start, end, category, priority) in enumerate(spans):
            points.extend([(start, 1, i), (end, -1, i)])
        active = set()
        heap = []
        previous = None
        for timestamp, kind, i in sorted(points):
            while heap and heap[0][2] not in active:
                heapq.heappop(heap)
            if previous is not None and heap:
                category = spans[heap[0][2]][2]
                totals[category] += (timestamp - previous) / 1000
            if kind == 1:
                active.add(i)
                start, end, category, priority = spans[i]
                heapq.heappush(heap, (-priority, -start, i))
            else:
                active.discard(i)
            previous = timestamp
    total = sum(totals.values())
    return {
        "tracedMainThreadMilliseconds": total,
        "categories": [
            {"category": name, "milliseconds": ms, "percentage": 100 * ms / total}
            for name, ms in totals.most_common()
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        if "trace" in path.stem:
            report = trace_categories(path)
        else:
            data = json.loads(path.read_text())
            sums = collections.Counter()
            for stage in data["isolated"]:
                sums[stage["stage"]] += stage["medianBrowserTaskMilliseconds"]
            total = sum(sums.values())
            report = {
                "isolatedTaskTotalMilliseconds": total,
                "stageShares": [
                    {"stage": n, "milliseconds": v, "percentage": v / total * 100}
                    for n, v in sums.most_common()
                ],
            }
        print(path)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
