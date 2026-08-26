#!/usr/bin/env python3
"""Structural checks for the direct-CSS GPT-2 block control."""

from __future__ import annotations

import json
from pathlib import Path

from build_matrix_backend_prototypes import ROOT


OUT = ROOT / "experiments" / "direct-css-block"


def main() -> None:
    reference = json.loads((OUT / "reference.json").read_text())
    matrix_html = (OUT / "matrix.html").read_text()
    block_html = (OUT / "block.html").read_text()
    sharded_html = (OUT / "block-sharded.html").read_text()
    matrix_css = (OUT / "matrix.css").read_text()
    block_css = (OUT / "block.css").read_text()

    assert reference["width"] == 768
    assert len(reference["matrix_expected"]) == 768
    assert len(reference["block_expected"]) == 768
    assert reference["block_css_shards"] == 16
    assert matrix_html.count('class="sink"') == 768
    assert block_html.count('class="sink"') == 768
    assert sharded_html.count('class="sink"') == 768
    assert sharded_html.count('rel="stylesheet"') == 17
    assert "<script" not in (matrix_html + block_html + sharded_html).lower()
    assert "--hidden-" not in block_css
    assert "--e2db" in block_css  # compact base-36 name for hidden value 3071
    assert "sqrt(" in block_css
    assert "exp(" in block_css
    assert len(matrix_css.encode()) == reference["matrix_css_bytes"]
    assert len(block_css.encode()) == reference["block_css_bytes"]
    print(
        {
            "matrix_bytes": reference["matrix_css_bytes"],
            "block_bytes": reference["block_css_bytes"],
            "block_terms": reference["block_terms"],
            "css_shards": reference["block_css_shards"],
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
