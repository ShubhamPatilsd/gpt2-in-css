"""Source/numeric contracts for experimental native cache encodings."""

import re
import unittest

from browser_gpt2_cache import config, declarations, read, registrations, storage_names
from browser_gpt2_core import cache_names, shared_css


class CacheCodecTests(unittest.TestCase):
    def test_object_counts(self):
        self.assertEqual(len(cache_names(0)), 1536)
        self.assertEqual(len(cache_names(0, "discrete")), 1536)
        self.assertEqual(len(storage_names(0, "numeric12")), 792)
        self.assertEqual(len(storage_names(0, "expression16")), 552)
        self.assertEqual(len(storage_names(0, "expression12")), 408)
        self.assertEqual(len(storage_names(0, "expression10")), 336)
        self.assertEqual(len(storage_names(0, "expression8")), 288)
        self.assertEqual(len(storage_names(0, "integer10")), 552)
        self.assertEqual(len(storage_names(0, "integer6")), 336)
        self.assertEqual(len(storage_names(0, "numeric9")), 792)

    def test_integer_packets_fit_signed_int_and_use_integer_registration(self):
        for mode in ("integer6", "integer10"):
            bits, lanes, expression = config(mode)
            self.assertFalse(expression)
            self.assertLessEqual(bits * lanes, 30)
            self.assertIn('syntax:"<integer>"', registrations(0, mode))
            self.assertIn("--qkv-2303", declarations(0, mode))
            self.assertNotIn("--qkv-2304", declarations(0, mode))

    def test_all_expression_codecs_fit_double_and_cover_tail(self):
        for mode in ("expression8", "expression10", "expression12", "expression16"):
            bits, lanes, expression = config(mode)
            self.assertTrue(expression)
            self.assertLessEqual(bits * lanes, 52)
            codes = [2**bits - 2 - i for i in range(lanes)]
            packet = float(sum(code * 2 ** (bits * i) for i, code in enumerate(codes)))
            self.assertEqual(
                [int(packet // 2 ** (bits * i)) % 2**bits for i in range(lanes)], codes
            )
            emitted = declarations(0, mode)
            self.assertIn("--qkv-2303", emitted)
            self.assertNotIn("--qkv-2304", emitted)

    def test_expression_packets_do_not_materialize_as_numbers(self):
        css = registrations(0, "expression16")
        self.assertEqual(css.count('syntax:"*"'), 528)
        self.assertEqual(css.count('syntax:"<number>"'), 24)
        self.assertIn(
            "transition-behavior:allow-discrete", shared_css(2, "flat", "expression16")
        )

    def test_every_coordinate_read_has_a_stored_packet_and_scale(self):
        names = set(storage_names(2, "expression16"))
        for kind in ("k", "v"):
            for coordinate in range(768):
                dependencies = set(
                    re.findall(
                        r"var\((--[^)]+)\)", read(2, kind, coordinate, "expression16")
                    )
                )
                self.assertTrue(dependencies <= names)
                self.assertEqual(len(dependencies), 2)
        source = declarations(2, "expression16")
        self.assertIn("--qkv-768", source)
        self.assertIn("--qkv-2303", source)
        self.assertNotIn("--qkv-2304", source)

    def test_three_codes_fit_exact_double_integer_range(self):
        bits, lanes, expression = config("expression16")
        self.assertTrue(expression)
        radix = 1 << bits
        maximum = radix - 2
        for values in ((0, 0, 0), (maximum, maximum, maximum), (123, 32767, 65534)):
            packet = sum(value * radix**i for i, value in enumerate(values))
            self.assertLess(packet, 2**53)
            self.assertEqual(float(packet), packet)
            self.assertEqual(
                tuple((int(float(packet)) // radix**i) % radix for i in range(lanes)),
                values,
            )

    def test_scalar_default_remains_numeric(self):
        css = shared_css(2, "flat")
        self.assertNotIn("allow-discrete", css)
        self.assertNotIn("--kp-", css)
        with self.assertRaises(ValueError):
            shared_css(2, "nested", "expression16")


if __name__ == "__main__":
    unittest.main()
