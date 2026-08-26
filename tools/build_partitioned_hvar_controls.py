#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Same-coefficient HVAR controls for the digit-rule isolation experiment."""
import hashlib
import json
from pathlib import Path

import build_gsub_shared_matrix_probe as shared

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-partitioned-digits"

if __name__ == "__main__":
    shared.OUT = OUT
    rows = []
    for n in (4, 16, 64, 256):
        weights = [3, -2, 5, 1] * (n // 4)
        # Keep the complete signed range positive, including the 256-wide case.
        shared.BASE = 64 - 2 * sum(min(w * -8, w * 7) for w in weights)
        font = shared.build_hvar(n, [weights[:] for _ in range(16)])
        if n == 256:
            # This WOFF2 fixture fails Chrome's WOFF2-to-SFNT conversion; the
            # identical uncompressed TTF loads. Font loading is outside timing.
            font["rejectedWoff2File"] = font["fontFile"]
            font["rejectedWoff2Sha256"] = font["fontSha256"]
            font["fontFile"] = "hvar/n256.ttf"
            font["fontSha256"] = hashlib.sha256((OUT/font["fontFile"]).read_bytes()).hexdigest()
            font["format"] = "ttf"
        rows.append({"width": n, "outputRows": 16, "weights": [weights[:] for _ in range(16)], "hvar": font})
    report = {"description": "Sixteen repeated coefficient rows. This isolates shared input/font state; it is not evidence of distinct-row general matrix performance.",
              "builderSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "sharedBuilderSha256": hashlib.sha256(Path(shared.__file__).read_bytes()).hexdigest(), "matrices": rows}
    (OUT / "hvar-reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([{ "width": r["width"], **r["hvar"]} for r in rows], indent=2))
