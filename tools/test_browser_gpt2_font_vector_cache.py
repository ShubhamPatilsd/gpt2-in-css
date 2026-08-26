"""Source contracts for native whole-head registers; Chromium tests are separate."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_hybrid_twelve_block as hybrid
from browser_gpt2_core import attention_positions
from browser_gpt2_font_backend import identity_avar2
from browser_gpt2_font_vector_cache import (
    QK_SIZE,
    VALUE_SIZE,
    attention,
    cache_slot,
    fallback_value_fonts,
    fonts,
    storage_names,
    value_axis,
)
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer


class FontVectorCacheTests(unittest.TestCase):
    def test_shared_probability_axis_preserves_bilinear_products(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("browser_gpt2_font_vector_cache.FONT_DIR", Path(temp)),
        ):
            info = fonts()["value"]
            font = TTFont(Path(temp) / "value.woff2")
            self.assertEqual(len(font["fvar"].axes), 65)
            self.assertEqual(font["fvar"].axes[0].axisTag, "P000")
            location = {f"K{i:03d}": (i - 32) / 32 for i in range(64)}
            location["P000"] = 0.375
            store = VarStoreInstancer(
                font["HVAR"].table.VarStore, font["fvar"].axes, location
            )
            for i in range(64):
                delta = store[font.getGlyphID(f"g{i:03d}")]
                self.assertAlmostEqual(
                    delta, info["coefficient"] * 0.375 * location[f"K{i:03d}"]
                )
            source_bytes = (Path(temp) / "value.woff2").read_bytes()
            converted = identity_avar2(
                Path(temp) / "value.woff2", Path(temp) / "converted"
            )
            wrapped = TTFont(converted)
            self.assertEqual(wrapped["avar"].majorVersion, 2)
            self.assertEqual(
                wrapped["avar"].renormalizeLocation(
                    location, wrapped, dropZeroes=False
                ),
                location,
            )
            self.assertEqual((Path(temp) / "value.woff2").read_bytes(), source_bytes)
            paths = fallback_value_fonts(3)
            for slot, path in enumerate(paths):
                fallback = TTFont(path)
                self.assertEqual(len(fallback["fvar"].axes), 65)
                renamed = {
                    value_axis(slot, i): location[f"K{i:03d}"] for i in range(64)
                }
                renamed[f"P{slot:03X}"] = location["P000"]
                deltas = VarStoreInstancer(
                    fallback["HVAR"].table.VarStore, fallback["fvar"].axes, renamed
                )
                for i in range(64):
                    self.assertEqual(
                        deltas[fallback.getGlyphID(f"g{i:03d}")],
                        store[font.getGlyphID(f"g{i:03d}")],
                    )
                self.assertEqual(
                    set(fallback.getBestCmap()),
                    {0xF5800 + slot * 64 + i for i in range(64)},
                )

    def test_private_banks_share_one_attention_graph(self):
        carrier, _, _, _ = hybrid.bridge(100, 768)
        operators = {
            "dot": {"base": 29984, "coefficient": 468},
            "value": {"base": 12032, "coefficient": 12000},
        }
        with patch("browser_gpt2_font_vector_cache.fonts", return_value=operators):
            html, css, metadata = attention(3, 2, carrier, "--position")
        self.assertEqual(len(storage_names(3)), 3 * 48)
        self.assertEqual(metadata["cacheFieldsPerLayer"], 144)
        self.assertEqual(html.count('class="fvs-bank '), 2)
        self.assertEqual(html.count('class="scroller fvs-score-source"'), 1)
        self.assertEqual(html.count("fvs-value-row"), 768)
        self.assertIn('syntax:"*";inherits:false;', css)
        self.assertIn("transition-behavior:allow-discrete", css)
        self.assertIn("@container fvscache style(--fvs-write-slot:2)", css)
        self.assertIn("var(--fr-k-0-0)", css)
        self.assertIn("var(--fr-v-0-0)", css)
        self.assertNotIn("font-size:calc", css)
        self.assertEqual(css.count("{"), css.count("}"))
        self.assertNotIn("<script", html.lower())
        self.assertLess((29984 + 64 * 468) * QK_SIZE / 1000, 32767)
        self.assertLess((12032 + 12000) * VALUE_SIZE / 1000, 32767)
        with (
            patch("browser_gpt2_font_vector_cache.fonts", return_value=operators),
            patch(
                "browser_gpt2_font_vector_cache.fallback_value_fonts",
                return_value=[Path(f"/font-{i}.woff2") for i in range(3)],
            ),
        ):
            flat_html, flat_css, metadata = attention(
                3, 2, carrier, "--position", value_layout="fallback"
            )
        self.assertEqual(flat_html.count('class="fvs-value-head-'), 12)
        self.assertEqual(flat_html.count('class="metric fvs-value-row"'), 768)
        self.assertNotIn('class="fvs-v-', flat_html)
        self.assertIn('"V080"', flat_css)
        self.assertEqual(metadata["valueLayout"], "fallback")
        self.assertEqual(flat_css.count("{"), flat_css.count("}"))

    def test_ring_overwrites_only_old_recent_slots(self):
        for sinks in (0, 1, 4):
            retained = {}
            for position in range(64):
                retained[cache_slot(position, 8, sinks)] = position
                self.assertEqual(
                    sorted(retained.values()), attention_positions(position, 8, sinks)
                )

    def test_early_values_keep_output_generation_gated(self):
        carrier, _, _, _ = hybrid.bridge(100, 768)
        operators = {
            "dot": {"base": 29984, "coefficient": 468},
            "value": {"base": 12032, "coefficient": 12000},
        }
        with patch("browser_gpt2_font_vector_cache.fonts", return_value=operators):
            html, css, metadata = attention(
                3, 1, carrier, value_layout="widths", prewarm_values=True
            )
            with self.assertRaises(ValueError):
                attention(3, 1, carrier, prewarm_values=True)
        self.assertTrue(metadata["prewarmValues"])
        self.assertEqual(html.count("var(--fvs-value-epoch)"), 1)
        self.assertIn('"P000" 1', css)
        self.assertIn("content-visibility:visible;--fvs-value-epoch:0", css)
        self.assertIn(
            "@container fvsscore style(--fvs-score-ready:1){"
            ".fvs-score-gate{--fvs-value-epoch:var(--epoch)}}", css
        )


if __name__ == "__main__":
    unittest.main()
