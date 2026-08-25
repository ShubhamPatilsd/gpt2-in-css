#!/usr/bin/env python3
"""Tests for static HTTP content-encoding negotiation."""

from __future__ import annotations

import unittest

from serve_precompressed import accepts_encoding


class AcceptEncodingTest(unittest.TestCase):
    def test_explicit_encoding(self) -> None:
        self.assertTrue(accepts_encoding("gzip, deflate, br", "br"))
        self.assertTrue(accepts_encoding("gzip, deflate, br", "gzip"))

    def test_zero_quality_is_rejected(self) -> None:
        self.assertFalse(accepts_encoding("br;q=0, gzip", "br"))
        self.assertTrue(accepts_encoding("br;q=0, gzip", "gzip"))

    def test_wildcard(self) -> None:
        self.assertTrue(accepts_encoding("*;q=.5", "br"))
        self.assertFalse(accepts_encoding("*;q=0", "br"))


if __name__ == "__main__":
    unittest.main()
