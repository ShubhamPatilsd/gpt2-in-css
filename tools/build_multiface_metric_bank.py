#!/usr/bin/env python3
"""Build a linear-size bank of five-output variable-font matrix rows."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont

from build_font_multimetric_probe import (
    BASE,
    FONT_SIZE,
    UNITS_PER_EM,
    axis_tag,
    build_font,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(
    os.environ.get(
        "MULTIFACE_BANK_OUT", ROOT / "experiments" / "multiface-metric-bank"
    )
).resolve()
INPUT_WIDTH = int(os.environ.get("MULTIFACE_BANK_INPUTS", "64"))
OUTPUT_WIDTH = int(os.environ.get("MULTIFACE_BANK_OUTPUTS", "64"))
SHARD_COUNT = int(os.environ.get("MULTIFACE_BANK_SHARDS", "1"))
TOTAL_INPUT_WIDTH = INPUT_WIDTH * SHARD_COUNT
REUSE_SHARDS = os.environ.get("MULTIFACE_BANK_REUSE_SHARDS", "0") == "1"
SKIP_FONT_BUILD = os.environ.get("MULTIFACE_BANK_SKIP_FONT_BUILD", "0") == "1"
DOCUMENT_FORMAT = os.environ.get("MULTIFACE_BANK_DOCUMENT", "html")
if DOCUMENT_FORMAT not in {"html", "xhtml"}:
    raise ValueError("MULTIFACE_BANK_DOCUMENT must be html or xhtml")
USE_EX = os.environ.get("MULTIFACE_BANK_EX", "1") == "1"
CHANNELS = (("ex", 0), ("cap", 1), ("ch", 2), ("ic", 3), ("lh", 4)) if USE_EX else (
    ("cap", 1), ("ch", 2), ("ic", 3), ("lh", 4)
)
LEAN = os.environ.get("MULTIFACE_BANK_LEAN", "0") == "1"
FONT_FORMAT = os.environ.get("MULTIFACE_BANK_FORMAT", "ttf")
if FONT_FORMAT not in {"ttf", "woff", "woff2"}:
    raise ValueError("MULTIFACE_BANK_FORMAT must be ttf, woff, or woff2")
SHIFTED = os.environ.get("MULTIFACE_BANK_SHIFTED", "1") == "1"


def settings(values: np.ndarray) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {float(value):.12g}'
        for index, value in enumerate(values)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not SKIP_FONT_BUILD:
        for stale in OUT.glob("face-*.*"):
            stale.unlink()
    rng = np.random.default_rng(0x4D46414345)
    weights = rng.integers(
        -16, 17, size=(OUTPUT_WIDTH, TOTAL_INPUT_WIDTH), dtype=np.int16
    )
    if REUSE_SHARDS:
        weights[:, INPUT_WIDTH:] = np.tile(
            weights[:, :INPUT_WIDTH], (1, SHARD_COUNT - 1)
        )
    inputs = rng.integers(-4, 5, size=TOTAL_INPUT_WIDTH).astype(np.float64) / 4
    alternate_inputs = inputs.copy()
    alternate_inputs[::7] = np.clip(alternate_inputs[::7] + 0.25, -1, 1)
    expected = weights.astype(np.float64) @ inputs
    alternate_expected = weights.astype(np.float64) @ alternate_inputs
    group_count = math.ceil(OUTPUT_WIDTH / len(CHANNELS))

    faces: list[str] = []
    rules: list[str] = []
    sfnt_bytes = 0
    face_records: list[tuple[int, int, str, str]] = []
    for shard in range(SHARD_COUNT):
        input_start = shard * INPUT_WIDTH
        input_stop = input_start + INPUT_WIDTH
        for group in range(group_count):
            start = group * len(CHANNELS)
            rows = np.zeros((7, INPUT_WIDTH), dtype=np.int16)
            stop = min(start + len(CHANNELS), OUTPUT_WIDTH)
            for channel, (_, font_row) in enumerate(CHANNELS[: stop - start]):
                rows[font_row] = weights[start + channel, input_start:input_stop]
            filename = f"face-s{shard:02d}-{group:03d}.{FONT_FORMAT}"
            family = f"MetricFaceS{shard:02d}G{group:03d}"
            destination = OUT / filename
            if REUSE_SHARDS and shard > 0:
                filename = f"face-s00-{group:03d}.{FONT_FORMAT}"
                faces.append(filename)
                face_records.append((shard, group, filename, family))
            else:
                if SKIP_FONT_BUILD:
                    if not destination.exists():
                        raise FileNotFoundError(destination)
                    sfnt_bytes += destination.stat().st_size
                elif FONT_FORMAT == "ttf":
                    build_font(
                        rows,
                        destination,
                        family_name=family,
                        shifted_axes=SHIFTED,
                        outline_variations=USE_EX,
                    )
                    sfnt_bytes += destination.stat().st_size
                else:
                    temporary = OUT / f"face-{group:03d}.ttf"
                    build_font(
                        rows,
                        temporary,
                        family_name=family,
                        shifted_axes=SHIFTED,
                        outline_variations=USE_EX,
                    )
                    font = TTFont(temporary, recalcTimestamp=False)
                    if LEAN:
                        del font["VVAR"]
                        font["gvar"].variations["H"] = []
                    font.flavor = None
                    font.save(temporary)
                    sfnt_bytes += temporary.stat().st_size
                    font.flavor = FONT_FORMAT
                    font.save(destination)
                    temporary.unlink()
                if LEAN and FONT_FORMAT == "ttf" and not SKIP_FONT_BUILD:
                    font = TTFont(destination, recalcTimestamp=False)
                    del font["VVAR"]
                    font["gvar"].variations["H"] = []
                    font.save(destination)
                faces.append(filename)
                face_records.append((shard, group, filename, family))
            declarations = []
            for channel, (metric, _) in enumerate(CHANNELS):
                output = start + channel
                if output >= OUTPUT_WIDTH:
                    break
                target = (
                    f"--o{output}"
                    if shard == SHARD_COUNT - 1
                    else f"--s{shard}-o{output}"
                )
                previous = (
                    "" if shard == 0 else f"var(--s{shard - 1}-o{output}) + "
                )
                declarations.append(
                    f"{target}:calc({previous}1{metric} / 1px * {UNITS_PER_EM} / "
                    f"{FONT_SIZE} - {BASE + (int(weights[output, input_start:input_stop].sum()) if SHIFTED else 0)})"
                )
            rules.append(
                f'.s{shard:02d}g{group:03d}{{font-family:"{family}";'
                + ";".join(declarations)
                + "}"
            )

    property_names = [f"--o{output}" for output in range(OUTPUT_WIDTH)]
    for shard in range(SHARD_COUNT - 1):
        property_names.extend(f"--s{shard}-o{output}" for output in range(OUTPUT_WIDTH))
    properties = "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:-99999}}'
        for name in property_names
    )
    font_faces = "".join(
        f'@font-face{{font-family:"{family}";'
        f'src:url("{filename}") format("{("truetype" if FONT_FORMAT == "ttf" else FONT_FORMAT)}")}}'
        for _, _, filename, family in face_records
    )
    content = '<div id="result">metric bank</div>'
    nodes = []
    shard_rules = []
    for shard in range(SHARD_COUNT):
        values = inputs[shard * INPUT_WIDTH:(shard + 1) * INPUT_WIDTH]
        nodes.append(f"shard shard{shard:02d}")
        nodes.extend(f"s{shard:02d}g{group:03d}" for group in range(group_count))
        shard_rules.append(
            f'.shard{shard:02d}{{font-variation-settings:'
            + settings((values + 1) / 2 if SHIFTED else values)
            + "}"
        )
    for classes in reversed(nodes):
        content = f'<div class="{classes}">{content}</div>'
    css = (
        font_faces
        + properties
        + '.bank{font-size:'
        + str(FONT_SIZE)
        + 'px;line-height:normal;position:fixed}'
        + "".join(shard_rules)
        + "".join(rules)
    )
    if DOCUMENT_FORMAT == "xhtml":
        html = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            '<meta charset="utf-8"/><title>Multiface metric bank</title>'
            + f"<style><![CDATA[{css}]]></style></head><body>"
            + f'<div id="bank" class="bank">{content}</div></body></html>'
        )
    else:
        html = (
            '<!doctype html><meta charset="utf-8">'
            '<title>Multiface metric bank</title><style>'
            + css
            + "</style>"
            + f'<div id="bank" class="bank">{content}</div>'
        )
    (OUT / f"index.{DOCUMENT_FORMAT}").write_text(html)
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "inputWidth": INPUT_WIDTH,
                "totalInputWidth": TOTAL_INPUT_WIDTH,
                "shardCount": SHARD_COUNT,
                "outputWidth": OUTPUT_WIDTH,
                "groupCount": group_count,
                "channels": [metric for metric, _ in CHANNELS],
                "fontSize": FONT_SIZE,
                "unitsPerEm": UNITS_PER_EM,
                "base": BASE,
                "inputs": inputs.tolist(),
                "alternateInputs": alternate_inputs.tolist(),
                "weights": weights.tolist(),
                "expected": expected.tolist(),
                "alternateExpected": alternate_expected.tolist(),
                "htmlBytes": len(html.encode()),
                "fontBytes": sum((OUT / filename).stat().st_size for filename in set(faces)),
                "logicalFontBytes": sum((OUT / filename).stat().st_size for filename in faces),
                "sfntBytes": sfnt_bytes,
                "logicalSfntBytes": sfnt_bytes * SHARD_COUNT if REUSE_SHARDS else sfnt_bytes,
                "lean": LEAN,
                "fontFormat": FONT_FORMAT,
                "shifted": SHIFTED,
                "useEx": USE_EX,
                "reuseShards": REUSE_SHARDS,
                "documentFormat": DOCUMENT_FORMAT,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "inputs": TOTAL_INPUT_WIDTH,
            "shard_width": INPUT_WIDTH,
            "outputs": OUTPUT_WIDTH,
            "faces": len(face_records),
            "html_bytes": len(html.encode()),
            "font_bytes": sum((OUT / filename).stat().st_size for filename in set(faces)),
            "sfnt_bytes": sfnt_bytes,
            "logical_sfnt_bytes": sfnt_bytes * SHARD_COUNT if REUSE_SHARDS else sfnt_bytes,
        }
    )


if __name__ == "__main__":
    main()
