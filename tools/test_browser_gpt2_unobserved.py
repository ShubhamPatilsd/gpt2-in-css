"""The real 12-block loop must advance without style/layout observation."""

import argparse
import json
import time
from pathlib import Path

from launch_browser_gpt2 import static_model_server
from probe_native_value_latch import navigate, props
from profile_hybrid_twelve_block import browser, query
from test_browser_gpt2_controls import click

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory", type=Path, default=ROOT / "experiments/browser-gpt2/demo"
    )
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument(
        "--heap-growth-percent", type=int, choices=(0, 10, 25, 50, 100), default=10
    )
    args = parser.parse_args()
    directory = args.directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("teacherForcedInputs"):
        raise ValueError("Use an autonomous fixture for the unobserved generation test")
    capacity = manifest["capacity"]
    expected = json.loads((directory / "numerical-results.json").read_text())["tokens"]
    flags = (
        [f"--js-flags=--heap-growing-percent={args.heap_growth_percent}"]
        if args.heap_growth_percent
        else []
    )
    with static_model_server(directory) as url, browser(flags) as cdp:
        # Wait for the complete model markup, not merely the early Run control.
        navigate(cdp, directory / "index.html", "#tokens", url=url, limit=180)
        click(cdp, "#run")
        started = time.perf_counter()
        remaining = args.seconds
        while remaining:
            interval = min(60, remaining)
            time.sleep(interval)
            remaining -= interval
            print(
                f"{args.seconds - remaining} seconds with no browser observations",
                flush=True,
            )
        quiet = time.perf_counter() - started
        # DOM.documentUpdated can invalidate frontend IDs while the page runs.
        # Reacquiring the root is read-only and is the first post-wait query.
        cdp.root_node = None
        frame_url = cdp.command("Page.getFrameTree")["frameTree"]["frame"]["url"]
        assert frame_url == url, frame_url
        p = props(cdp, query(cdp, "#tokens"))
        tokens = [int(float(p[f"--saved-token-{i}"])) for i in range(1, capacity + 1)]
        count = sum(
            bool(query(cdp, f"#token-{i}-captured.done"))
            for i in range(1, capacity + 1)
        )
        report = {
            "unobservedSeconds": quiet,
            "capturedTokens": count,
            "tokens": tokens,
            "passed": count >= 2 and tokens[:count] == expected[:count],
            "runtimeJavaScript": False,
            "harnessJavaScript": False,
            "externalActions": ["Initial Run click only"],
            "httpServer": "production allowlisted static launcher",
            "browserArguments": flags,
        }
        (directory / "unobserved-results.json").write_text(json.dumps(report, indent=2))
        print(report, flush=True)
        assert report["passed"], report


if __name__ == "__main__":
    main()
