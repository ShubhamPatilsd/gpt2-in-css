#!/usr/bin/env python3
"""Small regression checks for the measurement/fixture infrastructure."""

from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

from analyze_hybrid_profile import trace_categories


class Depth(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.maximum = 0
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        self.scripts += tag == "script"
        if tag in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            return
        self.stack.append(tag)
        self.maximum = max(self.maximum, len(self.stack))

    def handle_endtag(self, tag):
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[index:]


class ProfileTests(unittest.TestCase):
    def test_nested_events_are_not_double_counted(self):
        events = [
            {
                "pid": 1,
                "tid": 2,
                "name": "thread_name",
                "args": {"name": "CrRendererMain"},
            }
        ]
        for name, start, end in [
            ("RunTask", 0, 1000),
            ("UpdateLayoutTree", 100, 500),
            ("Layout", 500, 800),
            ("InlineNode::ShapeTextIncludingFirstLine", 600, 700),
        ]:
            events.append(
                dict(pid=1, tid=2, name=name, ts=start, dur=end - start, ph="X")
            )
        events.append(dict(pid=1, tid=99, name="RunTask", ts=0, dur=999999, ph="X"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps({"traceEvents": events}))
            result = trace_categories(path)
        self.assertAlmostEqual(result["tracedMainThreadMilliseconds"], 1)
        shares = {r["category"]: r["percentage"] for r in result["categories"]}
        self.assertAlmostEqual(shares["Style recalculation"], 40)
        self.assertAlmostEqual(shares["Layout excluding font shaping"], 20)
        self.assertAlmostEqual(shares["Font shaping"], 10)
        self.assertAlmostEqual(shares["Other main-thread work"], 30)

    def test_connected_fixture_is_shallow_and_script_free(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "experiments/hybrid-12block-profile/gated/connected-12.html"
        )
        if not path.exists():
            self.skipTest("build fixtures first")
        html = path.read_text()
        parser = Depth()
        parser.feed(html)
        self.assertEqual(parser.scripts, 0)
        self.assertLess(parser.maximum, 500)
        self.assertIn("script-src 'none'", html)
        self.assertEqual(html.count('class="block"'), 12)
        self.assertEqual(html.count('class="b11-proj-gate"'), 1)


if __name__ == "__main__":
    unittest.main()
