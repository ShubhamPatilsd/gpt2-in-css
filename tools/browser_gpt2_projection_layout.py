"""Use one inherited axis list and one fallback run per MLP output.

The 12 ordinary 256-axis projection fonts retain identical HVAR weights and
glyph advances. Only their private axis tags are made globally disjoint, so
3,072 output-child pack elements are unnecessary. Original assets are intact.
"""

import hashlib
import tempfile
from pathlib import Path

import build_gpt2_block_css as block
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "experiments/browser-gpt2/global-projection-assets"


def global_projection_fonts(directory, group):
    ASSETS.mkdir(parents=True, exist_ok=True)
    names, tags = [], []
    for shard, name in enumerate(group.names):
        source = directory / f"{name}.woff2"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        stem = f"{name}-{digest[:16]}-global-v1"
        target = ASSETS / f"{stem}.woff2"
        if not target.exists():
            with TTFont(source, recalcTimestamp=False) as font:
                protected = {
                    tag: font.getTableData(tag)
                    for tag in ("HVAR", "hmtx", "cmap", "gvar")
                    if tag in font
                }
                axes = font["fvar"].axes
                if not 1 <= len(axes) <= 256:
                    raise ValueError(
                        "Expected an ordinary at-most-256-axis source shard"
                    )
                mapping = {
                    a.axisTag: block.global_axis_tag(shard * 256 + i)
                    for i, a in enumerate(axes)
                }
                for axis in axes:
                    axis.axisTag = mapping[axis.axisTag]
                if "avar" in font:
                    font["avar"].segments = {
                        mapping[tag]: values
                        for tag, values in font["avar"].segments.items()
                    }
                if "STAT" in font:
                    for axis in font["STAT"].table.DesignAxisRecord.Axis:
                        axis.AxisTag = mapping.get(axis.AxisTag, axis.AxisTag)
                for name_id in (1, 3, 4, 6):
                    font["name"].setName(
                        f"GlobalProjection{digest[:16]}S{shard}", name_id, 3, 1, 0x409
                    )
                with tempfile.NamedTemporaryFile(
                    dir=ASSETS, suffix=".woff2", delete=False
                ) as staging:
                    temporary = Path(staging.name)
                try:
                    font.save(temporary)
                    with TTFont(temporary, recalcTimestamp=False) as checked:
                        for tag, original in protected.items():
                            if checked.getTableData(tag) != original:
                                raise ValueError(f"Retagging changed {tag}: {source}")
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
        names.append(stem)
        tags.append(hashlib.sha256(target.read_bytes()).hexdigest()[:12])
    return ASSETS, block.FontGroup(
        tuple(names),
        tuple(tags),
        group.bases,
        group.codepoint_starts,
        group.output_count,
        group.row_bases,
    )
