#!/usr/bin/env python3
"""Regression checks on the generated, script-disabled latch experiments.

Run probe_native_value_latch.py first to refresh the browser evidence. These
checks validate that evidence and fixture structure; they do not launch Chrome.
"""

import json
from pathlib import Path
import unittest

from test_hybrid_profile import Depth

OUT = (
    Path(__file__).resolve().parents[1]
    / "experiments/hybrid-12block-profile/value-latch"
)


class NativeLatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUT / "results.json").exists():
            raise unittest.SkipTest("Run probe_native_value_latch.py first")
        cls.report = json.loads((OUT / "results.json").read_text())

    def test_delayed_transition_retention_and_restart(self):
        candidate = next(
            r for r in self.report["vector"] if r["mode"] == "delayed-transition"
        )
        phases = {r["phase"]: r for r in candidate["phases"]}
        for phase in (
            "hold",
            "detach",
            "change-input-while-detached",
            "reattach-still-held",
        ):
            self.assertEqual(phases[phase]["error"]["maximum"], 0)
            self.assertEqual(phases[phase]["downstreamRetentionError"]["maximum"], 0)
        self.assertLess(phases["resume"]["error"]["maximum"], 0.002)
        self.assertLess(phases["resume"]["downstreamReferenceError"]["maximum"], 0.005)
        self.assertGreater(phases["resume"]["downstreamChanged"]["maximum"], 0.1)

    def test_four_autonomous_retirements(self):
        self.assertFalse(self.report["runtimeJavaScript"])
        self.assertFalse(self.report["harnessJavaScript"])
        self.assertEqual(len(self.report["automatic"]), 4)
        for row in self.report["automatic"]:
            self.assertTrue(row["pass"], row)
            self.assertEqual(row["externalControlMutationsAfterNavigation"], 0)
            self.assertEqual(row["sourceTimeline"], "none")
            self.assertEqual(row["receiverAnimation"], "none")

    def test_fixtures_are_script_free_and_detach_only_the_producer(self):
        for state in range(4):
            html = (OUT / f"automatic-retirement-state{state}.html").read_text()
            parser = Depth()
            parser.feed(html)
            self.assertEqual(parser.scripts, 0)
            self.assertLess(parser.maximum, 500)
            self.assertIn("script-src 'none'", html)
            self.assertIn(".b0-qkv>.scroller .metric{view-timeline-name:none", html)
            self.assertNotIn(".b0-qkv .metric{view-timeline-name:none", html)
            self.assertIn('begin="capture-ready.animationend+0.001s"', html)
            self.assertIn('class="b0-attn"', html)

    def test_native_run_does_not_need_continuous_observation(self):
        report = self.report
        if "unobservedAutomatic" not in report:
            report = json.loads((OUT / "automatic-results.json").read_text())
        row = report["unobservedAutomatic"]
        self.assertTrue(row["pass"], row)
        self.assertEqual(row["unobservedSecondsAfterNavigation"], 5)
        self.assertTrue(row["retiredAtFirstObservation"])
        self.assertTrue(row["downstreamStartsAfterRetirement"])


if __name__ == "__main__":
    unittest.main()
