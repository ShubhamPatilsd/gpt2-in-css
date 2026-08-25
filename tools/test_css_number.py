#!/usr/bin/env python3
"""Regression tests for lossless CSS numeric source compression."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_pretrained_gpt2.py"
SPEC = importlib.util.spec_from_file_location("css_number_builder", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
BUILDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUILDER
SPEC.loader.exec_module(BUILDER)


def previous_css_number(value: float) -> str:
    text = f"{float(value):.9f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


class CssNumberTest(unittest.TestCase):
    def test_expected_short_forms(self) -> None:
        cases = {
            0: "0",
            -0.0: "0",
            0.5: ".5",
            -0.5: "-.5",
            0.000001: "1e-6",
            0.000012345: "12345e-9",
            12.5: "12.5",
            1200: "1200",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(BUILDER.css_number(value), expected)

    def test_preserves_previous_decimal_value(self) -> None:
        values = [
            -12345.678901234,
            -1.000000001,
            -0.100000001,
            -0.000000009,
            0.000000001,
            0.000012345,
            0.125,
            1.234567891,
            100000000,
        ]
        for value in values:
            with self.subTest(value=value):
                before = previous_css_number(value)
                after = BUILDER.css_number(value)
                self.assertEqual(Decimal(before), Decimal(after))
                self.assertLessEqual(len(after), len(before))


if __name__ == "__main__":
    unittest.main()
