"""Static contracts for the real Chromium causal quality fixture."""

import unittest
import xml.etree.ElementTree as ET

import numpy as np

from measure_svg_causal_chromium import bounded_primitives


class SvgCausalContracts(unittest.TestCase):
    def test_opaque_color_matrix_preserves_small_support(self):
        primitives = bounded_primitives([
            '<feImage result="input" x="0" y="0" width="1" height="64"/>',
            '<feColorMatrix in="input" result="opaque" values="0 0 0 0 1"/>',
            '<feComposite in="input" in2="opaque" result="product"/>',
        ])
        for primitive in primitives:
            element = ET.fromstring(primitive)
            self.assertEqual(element.attrib["width"], "1")
            self.assertEqual(element.attrib["height"], "64")

    def test_output_merge_uses_union_not_filter_canvas(self):
        primitives = bounded_primitives([
            '<feOffset in="SourceGraphic" x="0" y="0" width="768" height="1" result="a"/>',
            '<feOffset in="SourceGraphic" x="0" y="3" width="768" height="1" result="b"/>',
            '<feMerge result="out"><feMergeNode in="a"/><feMergeNode in="b"/></feMerge>',
        ])
        element = ET.fromstring(primitives[-1])
        self.assertEqual(element.attrib["width"], "768")
        self.assertEqual(element.attrib["height"], "4")

    def test_calibration_product_bound_refactor_is_algebraically_equal(self):
        rng = np.random.default_rng(3)
        x = rng.normal(size=(7, 16))
        w = rng.normal(size=(9, 16))
        products = x[:, None] * w[None]
        signed = x @ w.T
        absolute = np.abs(x) @ np.abs(w).T
        np.testing.assert_allclose(np.maximum(products, 0).sum(-1), (absolute + signed) / 2, atol=1e-12)
        np.testing.assert_allclose(np.maximum(-products, 0).sum(-1), (absolute - signed) / 2, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
