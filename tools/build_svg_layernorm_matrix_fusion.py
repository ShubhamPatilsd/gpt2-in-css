#!/usr/bin/env python3
"""Build the real GPT-2 LayerNorm→matrix materialized/fused A/B fixture."""

from __future__ import annotations

import os
import runpy
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-layernorm-matrix-fusion-bucketed"


def main() -> None:
    # build_gpt2_block_css imports Brotli for unrelated bundle-size reports.
    # This focused SVG branch never calls it, so keep the probe buildable in a
    # minimal NumPy/Pillow environment without changing the main compiler.
    try:
        __import__("brotli")
    except ModuleNotFoundError:
        module = types.ModuleType("brotli")

        def unavailable(*_args: object, **_kwargs: object) -> bytes:
            raise RuntimeError("Brotli is not used by the LayerNorm fusion probe")

        module.compress = unavailable  # type: ignore[attr-defined]
        sys.modules["brotli"] = module

    # The shared numerical helpers live in modules that also import the font
    # compiler. This probe uses only model_data/layer_norm/quantize_float_rows,
    # so provide the unused font-facing names without requiring FontTools.
    try:
        __import__("fontTools")
    except ModuleNotFoundError:
        backend = types.ModuleType("build_matrix_backend_prototypes")
        backend.ROOT = ROOT  # type: ignore[attr-defined]
        backend.FONT_SIZE = 512  # type: ignore[attr-defined]
        backend.UNITS_PER_EM = 64  # type: ignore[attr-defined]
        backend.axis_tag = lambda *_args, **_kwargs: "TEST"  # type: ignore[attr-defined]
        backend.build_direct_font_backend = unavailable  # type: ignore[attr-defined]
        sys.modules["build_matrix_backend_prototypes"] = backend

        head = types.ModuleType("build_output_head_benchmark")
        head.css_number = lambda value: f"{float(value):.12g}"  # type: ignore[attr-defined]
        sys.modules["build_output_head_benchmark"] = head

    os.environ["SVG_FILTER_OUT"] = str(OUT)
    os.environ["SVG_FILTER_LN_FUSION_BUCKETED_ONLY"] = "1"
    runpy.run_path(str(ROOT / "tools" / "build_svg_filter_full_block.py"), run_name="__main__")


if __name__ == "__main__":
    main()
