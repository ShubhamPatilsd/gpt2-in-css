"""F4 (2026-09-19): cut the retained-transition count of the reused runtime.

F5 §4 measured ≈5.7 µs per in-delay CSS transition on EVERY style pass of the
document (the transition idiom is the only CSS-only value latch, so its COUNT is
the lever). Both changes are behind environment flags (default ON):

  F4_PACKED_BANKS=0  keep 48 latches per KV slot (12 heads × {k, v, ks, vs});
                     ON: 26 per slot — one 768-axis `*` list per kind (k, v) with
                     the 12 heads on disjoint axis tags + the 24 per-head scales
  F4_PACKED_HEAD=0   keep the 769 `--h*` head-input latches;
                     ON: 2 — the finished 768-entry head font-variation-settings
                     list (exact integers) + the epoch

Fonts ignore variation tags they do not define (the mechanism F2's global
projection relies on), so one list can feed 12 differently-tagged fonts. The
retagged operator fonts differ from font-vector-operators-v2 only in fvar tags,
STAT and name (HVAR/hmtx/cmap/glyf/loca/maxp/hhea asserted byte-identical).
"""

import hashlib
import os
import re
import tempfile
from pathlib import Path

from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont

HEADS, DIM = 12, 64
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "font-vector-operators-f4"
PROTECTED = ("HVAR", "hmtx", "cmap", "glyf", "loca", "maxp", "hhea")


def flag(name):
    return os.environ.get(name, "1") not in ("0", "false", "no", "off")


PACKED_BANKS = flag("F4_PACKED_BANKS")
PACKED_HEAD = flag("F4_PACKED_HEAD")
# F4 micro-test 2: the per-pass cost of the retained `*` lists tracks their BYTES
# (49.6 ms for `calc(a / b)` entries vs 35.7 ms for plain numbers, same entries),
# so the live lists carry pre-evaluated typed numbers (6 significant digits when
# substituted, like the calc operands were) instead of an unevaluated quotient.
NUMERIC_LISTS = flag("F4_NUMERIC_LISTS")


def head_axis(kind, head, coordinate):
    """Disjoint per-head tags: K000..K2FF for keys, V000..V2FF for values."""
    if kind not in ("k", "v") or not 0 <= head < HEADS or not 0 <= coordinate < DIM:
        raise ValueError("Bad head axis")
    return f"{kind.upper()}{head * DIM + coordinate:03X}"


def zero_list(kind):
    return ",".join(
        f'"{head_axis(kind, head, i)}" 0' for head in range(HEADS) for i in range(DIM)
    )


def kind_of(name):
    """--fc-{kind}-{slot}[-{head}] -> kind (works for packed and unpacked names)."""
    return name.split("-")[3]


def slot_of(name):
    return int(name.split("-")[4])


def packed_operator_fonts(source_dir):
    """[(dot_path, value_path)] per head, retagged from the v2 operator fonts."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    result = []
    for head in range(HEADS):
        pair = []
        for kind, family in (("dot", "k"), ("value", "v")):
            source = Path(source_dir) / f"{kind}.woff2"
            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
            target = ASSETS / f"{kind}-h{head}-{digest}-f4.woff2"
            if not target.exists():
                font = TTFont(source, recalcTimestamp=False)
                protected = {
                    tag: font.getTableData(tag) for tag in PROTECTED if tag in font
                }
                retagged = 0
                for axis in font["fvar"].axes:
                    if re.fullmatch(r"K\d{3}", axis.axisTag):
                        axis.axisTag = head_axis(family, head, int(axis.axisTag[1:]))
                        retagged += 1
                if retagged != DIM:
                    raise ValueError(f"Expected {DIM} K axes in {source}, found {retagged}")
                buildStatTable(
                    font,
                    [
                        {"tag": a.axisTag, "name": a.axisNameID, "ordering": i}
                        for i, a in enumerate(font["fvar"].axes)
                    ],
                )
                for name_id in (1, 3, 4, 6):
                    font["name"].setName(
                        f"Fvs{kind.title()}H{head}F4", name_id, 3, 1, 0x409
                    )
                with tempfile.NamedTemporaryFile(
                    dir=ASSETS, suffix=".woff2", delete=False
                ) as staging:
                    temporary = Path(staging.name)
                try:
                    font.save(temporary)
                    checked = TTFont(temporary, recalcTimestamp=False)
                    for tag, original in protected.items():
                        if checked.getTableData(tag) != original:
                            raise ValueError(f"Retagging changed {tag}: {source}")
                    tags = [a.axisTag for a in checked["fvar"].axes]
                    expected = [
                        head_axis(family, head, int(t[1:])) if re.fullmatch(r"K\d{3}", t) else t
                        for t in (a.axisTag for a in TTFont(source, lazy=True)["fvar"].axes)
                    ]
                    if tags != expected:
                        raise ValueError(f"Unexpected fvar tags after retagging: {source}")
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            pair.append(target)
        result.append(tuple(pair))
    return result


_HEAD_ENTRY = re.compile(
    r'"(X[0-9A-Z]{3})" round\(nearest,calc\(var\(--h(\d+)\)/([0-9.]+)\*16384\),1\)'
)
_HEAD_LIST = re.compile(
    r'font-variation-settings:((?:"X[0-9A-Z]{3}" round\(nearest,calc\(var\(--h\d+\)/[0-9.]+\*16384\),1\),?)+)'
)


def pack_head_input(head_css, width=768, final="final-h"):
    """Replace head.css's two identical --h lists by var(--head-fvs).

    Returns (head_css, registrations, bank_declarations). The bank computes the
    768 rounded axis integers as typed numbers (same double ops, same order as
    the head.css expression on --h_i == --final-h-i) and latches ONE list of
    them; integers serialise exactly into the `*` property.
    """
    lists = _HEAD_LIST.findall(head_css)
    if len(lists) != 2 or lists[0] != lists[1]:
        raise ValueError(f"Expected two identical head input lists, found {len(lists)}")
    entries = _HEAD_ENTRY.findall(lists[0])
    if len(entries) != width or lists[0].count('"') != 2 * width:
        raise ValueError(f"Expected {width} head axes, found {len(entries)}")
    divisors = {d for _, _, d in entries}
    if len(divisors) != 1 or [int(i) for _, i, _ in entries] != list(range(width)):
        raise ValueError("Head input list is not the regular per-coordinate form")
    divisor = divisors.pop()
    head_css, replaced = _HEAD_LIST.subn("font-variation-settings:var(--head-fvs)", head_css)
    if replaced != 2:
        raise ValueError("Head list replacement mismatch")
    quantized = [f"--hq-{i}" for i in range(width)]
    regs = "".join(
        f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}' for p in quantized
    ) + '@property --head-fvs{syntax:"*";inherits:true;initial-value:"X000" 0}'
    decls = ";".join(
        f"{p}:round(nearest,calc(var(--{final}-{i:03d})/{divisor}*16384),1)"
        for i, p in enumerate(quantized)
    )
    decls += ";--head-fvs:" + ",".join(
        f'"{tag}" var(--hq-{i})' for tag, i, _ in entries
    )
    return head_css, regs, decls
