"""Source contracts for independent score/epoch transport; not browser proof."""

import unittest
from pathlib import Path

from browser_gpt2_head_receipts import split_head_receipt


class HeadReceiptTests(unittest.TestCase):
    def test_preserves_rows_and_replaces_packed_decoder(self):
        directory = (
            Path(__file__).resolve().parents[1]
            / "experiments/browser-gpt2/head-two-pass"
        )
        original_html = (directory / "head-body.html").read_text()
        original_css = (directory / "head.css").read_text()
        html, css = split_head_receipt(original_html, original_css)
        self.assertEqual(html.count('class="head-row"'), 50257)
        self.assertEqual(html.count("<div"), html.count("</div>"))
        self.assertEqual(css.count("{"), css.count("}"))
        self.assertNotIn("--head-pipeline-epoch:mod", css)
        self.assertIn(".head-score-state{--head-group-index:", css)
        self.assertIn(
            ".head-group-state{--head-pipeline-epoch:round(nearest,100cqi/1px,1)}", css
        )
        self.assertNotIn("<script", html.lower())
        with self.assertRaises(ValueError):
            split_head_receipt(html, css)


if __name__ == "__main__":
    unittest.main()
