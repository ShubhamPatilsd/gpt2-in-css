import unittest

from decode_css_cache_diagnostic import css_number, decode_cache


class CssCacheDiagnosticTests(unittest.TestCase):
    def test_font_settings_are_decoded_only_after_measurement(self):
        properties = {}
        for kind in ("k", "v"):
            for head in range(12):
                properties[f"--fc-{kind}s-2-{head}"] = "4"
                properties[f"--fc-{kind}-2-{head}"] = ",".join(
                    f'"K{i:03d}" calc({i} / 4)' for i in range(64)
                )
        self.assertEqual(
            decode_cache(properties, 2, "font-vector"), list(range(64)) * 24
        )
        for head in range(12):
            properties[f"--fc-v-2-{head}"] = ",".join(
                f'"V{128 + i:03X}" calc({i} / 4)' for i in range(64)
            )
        self.assertEqual(
            decode_cache(properties, 2, "font-vector"), list(range(64)) * 24
        )
        properties["--fc-k-2-0"] = '"K000" 0'
        with self.assertRaises(ValueError):
            decode_cache(properties, 2, "font-vector")

    def test_css_rounding_and_exact_expression(self):
        self.assertEqual(css_number("round(nearest,-1.5,1)"), -1)
        self.assertEqual(
            css_number(
                "calc(4096 * (clamp(-2047,round(nearest,calc(2.5 / .25),1),2047) + 2047) + 1234)"
            ),
            4096 * 2057 + 1234,
        )
        self.assertEqual(
            css_number("calc(281474976710655 / 65536)"), 281474976710655 / 65536
        )

    def test_rejects_executable_or_non_finite_input(self):
        for text in ('__import__("os")', "a.b", "1e999", "[1,2][0]"):
            with self.assertRaises(ValueError):
                css_number(text)


if __name__ == "__main__":
    unittest.main()
