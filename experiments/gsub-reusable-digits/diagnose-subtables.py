#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Check raw GSUB availability versus HarfBuzz's validated GSUB view.

Padding keeps the full arithmetic program. Rule-pruned probes deliberately do
not preserve arithmetic; they isolate validator acceptance near a table-count
boundary. No original font is changed and no engine limit is modified.
"""
import ctypes
import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable

HERE = Path(__file__).resolve().parent
OUT = HERE / "diagnostic-subtables"
OUT.mkdir(exist_ok=True)
LIB = ctypes.CDLL("/opt/homebrew/lib/libharfbuzz.0.dylib")
LIB.hb_blob_create_from_file_or_fail.argtypes = [ctypes.c_char_p]
LIB.hb_blob_create_from_file_or_fail.restype = ctypes.c_void_p
LIB.hb_face_create.argtypes = [ctypes.c_void_p, ctypes.c_uint]
LIB.hb_face_create.restype = ctypes.c_void_p
LIB.hb_face_reference_table.argtypes = [ctypes.c_void_p, ctypes.c_uint]
LIB.hb_face_reference_table.restype = ctypes.c_void_p
LIB.hb_blob_get_length.argtypes = [ctypes.c_void_p]
LIB.hb_blob_get_length.restype = ctypes.c_uint
LIB.hb_ot_layout_table_get_lookup_count.argtypes = [ctypes.c_void_p, ctypes.c_uint]
LIB.hb_ot_layout_table_get_lookup_count.restype = ctypes.c_uint
LIB.hb_ot_layout_has_substitution.argtypes = [ctypes.c_void_p]
LIB.hb_ot_layout_has_substitution.restype = ctypes.c_int
LIB.hb_blob_destroy.argtypes = [ctypes.c_void_p]
LIB.hb_face_destroy.argtypes = [ctypes.c_void_p]
LIB.hb_version_string.restype = ctypes.c_char_p
TAG = int.from_bytes(b"GSUB", "big")


def inspect(path, label, extra=None):
    decoded = TTFont(path)
    lookups = decoded["GSUB"].table.LookupList.Lookup
    blob = LIB.hb_blob_create_from_file_or_fail(str(path).encode())
    face = LIB.hb_face_create(blob, 0)
    raw = LIB.hb_face_reference_table(face, TAG)
    record = {
        "label": label, "path": str(path.relative_to(HERE)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "fontToolsLookupCount": len(lookups),
        "fontToolsTotalReferencedSubtables": sum(lookup.SubTableCount for lookup in lookups),
        "rawGsubBytes": LIB.hb_blob_get_length(raw),
        "harfbuzzHasSubstitution": bool(LIB.hb_ot_layout_has_substitution(face)),
        "harfbuzzValidatedLookupCount": LIB.hb_ot_layout_table_get_lookup_count(face, TAG),
        **(extra or {}),
    }
    LIB.hb_blob_destroy(raw); LIB.hb_face_destroy(face); LIB.hb_blob_destroy(blob)
    return record


original_path = HERE / "reusable-w256/weighted.ttf"
original = TTFont(original_path)
original_gsub = original.getTableData("GSUB")
records = [inspect(HERE / f"reusable-w{width}/weighted.ttf", f"original-w{width}") for width in (4, 16, 64, 256)]
for padding in (16384, 262144):
    font = TTFont(original_path)
    table = DefaultTable("GSUB"); table.data = original_gsub + bytes(padding)
    font["GSUB"] = table
    path = OUT / f"full-program-pad-{padding}.ttf"
    font.save(path)
    records.append(inspect(path, f"full-program-pad-{padding}", {"arithmeticPreserved": True, "trailingZeroBytes": padding}))

for target in (16000, 16383, 16384, 16400):
    font = TTFont(original_path)
    lookups = font["GSUB"].table.LookupList.Lookup
    remaining = sum(lookup.SubTableCount for lookup in lookups) - target
    assert remaining > 0
    for lookup in reversed(lookups):
        removed = min(remaining, len(lookup.SubTable) - 1)
        if removed:
            lookup.SubTable = lookup.SubTable[:-removed]
            lookup.SubTableCount = len(lookup.SubTable)
            remaining -= removed
    assert remaining == 0
    modified_gsub = font.getTableData("GSUB")
    table = DefaultTable("GSUB"); table.data = modified_gsub + bytes(262144)
    font["GSUB"] = table
    path = OUT / f"pruned-subtables-{target}-padded.ttf"
    font.save(path)
    records.append(inspect(path, f"pruned-subtables-{target}", {"arithmeticPreserved": False, "trailingZeroBytes": 262144,
                                                                "purpose": "validator threshold only; deliberately missing arithmetic rules"}))

report = {"harfbuzzVersion": LIB.hb_version_string().decode(), "sourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "originalFontSha256": hashlib.sha256(original_path.read_bytes()).hexdigest(), "records": records,
          "scope": "The installed HarfBuzz C API, not a direct inspection of Chromium's embedded library. Original artifacts unchanged."}
(HERE / "diagnosis-subtables.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(records, indent=2))
