"""Projection topology contract; complete Chromium tests remain mandatory."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import build_gpt2_block_css as block
import build_hybrid_twelve_block as hybrid
import numpy as np


class GlobalProjectionTests(unittest.TestCase):
    def test_all_glyphs_share_one_inherited_global_axis_list(self):
        group = block.FontGroup(
            ("a", "b"),
            ("a", "b"),
            (64, 64),
            (0xF0000, 0xF0100),
            2,
            (np.array([64, 64]), np.array([64, 64])),
        )
        with (
            patch(
                "build_hybrid_twelve_block.font_group",
                return_value=(Path("/fonts"), group),
            ),
            patch(
                "browser_gpt2_projection_layout.global_projection_fonts",
                return_value=(Path("/fonts"), group),
            ),
        ):
            html, css = hybrid.matvec(
                0,
                "proj",
                SimpleNamespace(scales=np.ones(2)),
                np.zeros(2),
                hybrid.names("hidden", 512),
                hybrid.names("out", 2),
                1,
                512,
                compact=True,
                gated=True,
                dynamic_range=True,
                global_axes=True,
            )
        self.assertNotIn("proj-pack", html + css)
        self.assertEqual(html.count("&#x"), 4)
        self.assertIn(f'"{block.global_axis_tag(511)}"', css)
        self.assertIn("font-family:b0projS0,b0projS1", css)
        self.assertEqual(css.count("{"), css.count("}"))


if __name__ == "__main__":
    unittest.main()
