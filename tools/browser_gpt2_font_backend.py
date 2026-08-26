"""Select Chromium's existing Fontations backend via identity avar2 metadata.

Exact Chromium revision 199a3a541d76237379e353b348e64045584db057 routes avar2
fonts to MakeTypefaceFontations. Ordinary variable fonts use the system font
manager on macOS. No browser modification, script, or extra executable runtime.
Original fonts are never overwritten; model/shaping tables are byte-checked.
"""

import hashlib
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "experiments/browser-gpt2/fontations-assets"
PROTECTED_TABLES = (
    "fvar",
    "HVAR",
    "hmtx",
    "cmap",
    "GSUB",
    "GPOS",
    "gvar",
    "VVAR",
    "MVAR",
    "CFF2",
)


def identity_avar2(source, destination=ASSETS):
    """Return a distinct immutable font with unchanged model/shaping tables."""
    source = source.resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{source.stem}-{digest[:20]}.woff2"
    if target.exists():
        return target
    font = TTFont(source, recalcTimestamp=False)
    if "fvar" not in font:
        return source
    if "avar" in font and font["avar"].majorVersion >= 2:
        return source
    original = {tag: font.getTableData(tag) for tag in PROTECTED_TABLES if tag in font}
    avar = font["avar"] if "avar" in font else newTable("avar")
    if not avar.segments:
        avar.segments = {
            axis.axisTag: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for axis in font["fvar"].axes
        }
    avar.majorVersion, avar.minorVersion = 2, 0
    avar.table = otTables.avar()
    avar.table.Reserved = 0
    avar.table.VarIdxMap = None
    avar.table.VarStore = None
    font["avar"] = avar
    font.flavor = "woff2"
    with tempfile.NamedTemporaryFile(
        dir=destination, suffix=".woff2", delete=False
    ) as staging:
        temporary = Path(staging.name)
    try:
        font.save(temporary)
        with TTFont(temporary, recalcTimestamp=False) as checked:
            for tag, data in original.items():
                if checked.getTableData(tag) != data:
                    raise ValueError(
                        f"Backend wrapper changed protected {tag} table: {source}"
                    )
            if (
                checked["avar"].majorVersion != 2
                or checked["avar"].table.VarStore is not None
            ):
                raise ValueError("Identity avar2 serialization failed")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def fontations_stylesheet(css, destination=ASSETS):
    rewritten = {}

    def replace(match):
        parsed = urlparse(match[1])
        source = Path(unquote(parsed.path))
        if source.suffix not in (".woff2", ".ttf", ".otf", ".woff"):
            return match[0]
        if source not in rewritten:
            rewritten[source] = identity_avar2(source, destination)
        return f'url("{rewritten[source].as_uri()}")'

    return re.sub(r'url\("(file:[^\"]+)"\)', replace, css)
