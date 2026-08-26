"""Cheap regression guards; browser/e2e checks remain separate and mandatory."""

import json
import re
import unittest
from pathlib import Path

from browser_gpt2_core import cache_names, shared_css
from browser_gpt2_runtime import feedback

ROOT = Path(__file__).resolve().parents[1]


class NativeRuntimeSourceTests(unittest.TestCase):
    def test_flat_bank_releases_exactly_one_slot(self):
        css = shared_css(4, "flat")
        for epoch in range(1, 5):
            rule = re.search(
                r"@container runtime style\(--epoch:"
                + str(epoch)
                + r"\)\{\.kv-bank\{([^}]+)",
                css,
            )[1]
            transitions = re.search(r"transition-property:([^;]+)", rule)[1].split(",")
            active = cache_names(epoch - 1)
            retained = [
                p for slot in range(4) if slot != epoch - 1 for p in cache_names(slot)
            ]
            self.assertEqual(transitions, retained)
            self.assertTrue(all(f"{p}:var(--qkv-" in rule for p in active))
            self.assertEqual(rule.count(":var(--qkv-"), 1536)
        self.assertNotIn("if(style(--epoch:", css)

    def test_feedback_is_native_and_finite(self):
        front, output, css, timelines = feedback(8)
        self.assertEqual(len(timelines), 8)
        self.assertIn("--feedback-7", css)
        self.assertNotIn("body:has(#token-8-advanced.done)", css)
        self.assertIn("animationend+0.001s", output)
        self.assertIn("not style(--winner:50256)", css)
        self.assertEqual((front + output + css).lower().count("<script"), 0)
        self.assertEqual(css.count("{"), css.count("}"))

    def test_component_screens_are_not_shortlists(self):
        head = json.loads(
            (
                ROOT / "experiments/browser-gpt2/head-two-pass/browser-results.json"
            ).read_text()
        )
        lookup = json.loads(
            (
                ROOT / "experiments/browser-gpt2/embedding/browser-results.json"
            ).read_text()
        )
        self.assertEqual(len(head["samples"]), 38)
        self.assertTrue(all(x["passed"] for x in head["samples"]))
        self.assertEqual(len(lookup["samples"]), 16)
        self.assertTrue(all(x["passed"] for x in lookup["samples"]))


if __name__ == "__main__":
    unittest.main()
