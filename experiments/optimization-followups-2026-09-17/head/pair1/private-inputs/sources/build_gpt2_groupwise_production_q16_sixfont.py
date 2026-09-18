#!/usr/bin/env python3
"""Integrate the bounded six-font global-q16 bank into the production cascade."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
RETAINED = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-production-range"
BANK = ROOT / "experiments" / "gpt2-global-q16-layernorm-integer-full"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
OUTPUT = (
    ROOT
    / "experiments"
    / "gpt2-groupwise-cauchy-blockflow-production-range-q16-sixfont"
)

VOCABULARY = 50_257
WIDTH = 768
GROUP_SIZE = 256
GROUPS = 197
HOT_ROWS = 512
AXIS_STEPS = 16_384
R = 266.2483969116211
WEIGHT_SCALE = 5.448031520794028e-05
SCORE_GAIN = 0.5082061049039431
FACTOR = "120.777609693"
FONT_SIZE_PX = 62.5
Q16_CODES_SHA256 = "d49d4e7ec27e17409959b2d48d694c880279f78332a3f6a3081668e7b2e6a329"
FONT_SHA256 = {
    "score-high-0.woff2": "e16c70210fdd1223a4cb82d005bf0d68cd566f6868e3b880e0a6b376980ef918",
    "score-residual-0.woff2": "894822cee1c02c90b9ccbae54205a357edc3152871066444e37e40140d60a588",
    "score-high-1.woff2": "5fdfc47e3c3dc0b60237b7c1be88d1af858c7a1f966c4ef94497bbf3caa5c171",
    "score-residual-1.woff2": "4c7fd5190ffd84815ef578f178b851f089b962682444cf186440e563fb7c2ad4",
    "score-high-2.woff2": "5fb5d699df3a2f29a0935c394883b1a19dc9ee7d40faa87ff289ed59d1536c38",
    "score-residual-2.woff2": "b6639ac11634e6020d8c2dbef9a9273ea3390c99b2e49200c61cac0b7ad0720e",
}


def css_number(value: float) -> str:
    text = f"{float(value):.12g}"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def css_if(branches: list[tuple[int, str]], fallback: str) -> str:
    return "if(" + ";".join(
        f"style(--group:{group}):{value}" for group, value in branches
    ) + f";else:{fallback})"


def parse_bank_rows() -> list[dict[str, object]]:
    html = (BANK / "index.html").read_text()
    matches = re.findall(
        r'<i class="candidate" data-token="(\d+)" '
        r'style="--base:([^;]+);--factor:([^;]+);--local-tie:([^\"]+)">'
        r'(.*?)</i>',
        html,
    )
    if len(matches) != VOCABULARY:
        raise RuntimeError(f"expected {VOCABULARY} six-font rows, found {len(matches)}")
    rows: list[dict[str, object]] = []
    for expected_token, (token_text, base, factor, tie, glyphs) in enumerate(matches):
        token = int(token_text)
        if token != expected_token:
            raise RuntimeError(f"six-font row order changed at token {expected_token}")
        expected_glyphs = "".join(chr(start + token) for start in range(0x20000, 0x80000, 0x10000))
        if glyphs != expected_glyphs:
            raise RuntimeError(f"six-font codepoints changed at token {token}")
        if factor != FACTOR:
            raise RuntimeError(f"six-font factor changed at token {token}: {factor}")
        if float(base) * 16 != round(float(base) * 16):
            raise RuntimeError(f"token {token} base is not an integer analytic-base sum / 16")
        if int(float(tie) * 64) != (255 - token % GROUP_SIZE) * 64:
            raise RuntimeError(f"six-font local tie changed at token {token}")
        rows.append({"token": token, "base": base, "tie": tie, "glyphs": glyphs})
    return rows


def assert_bank_contract(bank_reference: dict[str, object]) -> dict[str, object]:
    q16 = bank_reference["q16"]
    coordinates = bank_reference["coordinates"]
    if bank_reference["vocabulary"] != VOCABULARY or bank_reference["width"] != WIDTH:
        raise RuntimeError("six-font bank shape changed")
    if q16["codesSha256"] != Q16_CODES_SHA256:
        raise RuntimeError("six-font q16 code hash changed")
    if float(q16["weightScale"]) != WEIGHT_SCALE:
        raise RuntimeError("six-font q16 scale changed")
    if q16["radix"] != 256 or q16["glyphsPerRow"] != 6:
        raise RuntimeError("six-font radix/row layout changed")
    if float(coordinates["declaredRangeR"]) != R:
        raise RuntimeError("six-font production range changed")
    if coordinates["fvarUserRange"] != [-AXIS_STEPS, 0, AXIS_STEPS]:
        raise RuntimeError("six-font fvar user range changed")
    if float(coordinates["fontSizePx"]) != FONT_SIZE_PX:
        raise RuntimeError("six-font display scale changed")
    if float(coordinates["scoreGain"]) != SCORE_GAIN:
        raise RuntimeError("six-font score gain changed")
    if not bank_reference["layerNormBound"]["belowChromeAdvanceCeiling"]:
        raise RuntimeError("six-font analytic advance cap gate is not certified")

    manifest = []
    face_by_font = {record["font"]: record for record in bank_reference["faceRecords"]}
    if set(face_by_font) != set(FONT_SHA256):
        raise RuntimeError("six-font face manifest changed")
    for filename, expected_digest in FONT_SHA256.items():
        path = BANK / filename
        actual_digest = sha256(path)
        if actual_digest != expected_digest:
            raise RuntimeError(f"six-font artifact hash changed: {filename}")
        record = face_by_font[filename]
        if record["rows"] != VOCABULARY or record["axes"] != 256:
            raise RuntimeError(f"six-font face shape changed: {filename}")
        if record["fvarUserRange"] != [-AXIS_STEPS, 0, AXIS_STEPS]:
            raise RuntimeError(f"six-font face axis range changed: {filename}")
        manifest.append({
            "file": filename,
            "bytes": path.stat().st_size,
            "sha256": actual_digest,
            "hvarSha256": record["hvarSha256"],
            "plane": record["plane"],
            "shard": record["shard"],
        })
    return {"faces": manifest, "fontBytes": sum(item["bytes"] for item in manifest)}


def direct_q16_reference(retained_reference: dict[str, object]) -> dict[str, object]:
    fixtures = retained_reference["certifiedFixtures"]
    hidden = np.asarray(fixtures["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(fixtures["scoreFloors"], dtype=np.int64)
    realized = np.rint(hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY], dtype=np.float64
    )
    codes = np.rint(weights / WEIGHT_SCALE).astype(np.int16)
    if hashlib.sha256(codes.tobytes()).hexdigest() != Q16_CODES_SHA256:
        raise RuntimeError("source-checkpoint q16 codes do not match six-font bank")
    q16_weights = codes.astype(np.float64) * WEIGHT_SCALE
    q16_scores = realized @ q16_weights.T * SCORE_GAIN
    float_scores = realized @ weights.T * SCORE_GAIN
    q16_buckets = np.rint((q16_scores - floors[:, None]) * 256).astype(np.int64)

    group_winners: list[list[int]] = []
    group_buckets: list[list[int]] = []
    group_scores: list[list[float]] = []
    for fixture in range(len(hidden)):
        winners = []
        buckets = []
        scores = []
        for group in range(GROUPS):
            start = group * GROUP_SIZE
            stop = min(start + GROUP_SIZE, VOCABULARY)
            local = int(np.argmax(q16_buckets[fixture, start:stop]))
            token = start + local
            winners.append(token)
            buckets.append(int(q16_buckets[fixture, token]))
            scores.append(float(q16_scores[fixture, token]))
        group_winners.append(winners)
        group_buckets.append(buckets)
        group_scores.append(scores)

    q16_winners = np.argmax(q16_scores, axis=1).astype(np.int64)
    q16_bucket_winners = np.argmax(q16_buckets, axis=1).astype(np.int64)
    float_winners = np.argmax(float_scores, axis=1).astype(np.int64)
    if q16_winners.tolist() != fixtures["denseWinners"]:
        raise RuntimeError("retained fixture q16 winners changed")
    saved = np.load(STATES)
    state519_hidden = np.asarray(saved["hidden"][519], dtype=np.float64)
    state519_realized = np.rint(state519_hidden / R * AXIS_STEPS) / AXIS_STEPS * R
    state519_q16_scores = state519_realized @ q16_weights.T * SCORE_GAIN
    state519_float_scores = state519_realized @ weights.T * SCORE_GAIN
    state519_floor = int(np.floor(np.min(state519_q16_scores))) - 2
    state519_buckets = np.rint(
        (state519_q16_scores - state519_floor) * 256
    ).astype(np.int64)
    state519_winner = int(np.argmax(state519_q16_scores))
    state519_group = state519_winner // GROUP_SIZE
    state519_start = state519_group * GROUP_SIZE
    state519_stop = min(state519_start + GROUP_SIZE, VOCABULARY)
    state519_group_winner = state519_start + int(
        np.argmax(state519_buckets[state519_start:state519_stop])
    )
    if state519_winner != 37_848 or state519_group_winner != 37_848:
        raise RuntimeError(
            "state519 immutable global-q16 oracle no longer selects token 37848"
        )

    return {
        "realizedCoordinates": realized.tolist(),
        "q16Winners": q16_winners.tolist(),
        "q16BucketWinners": q16_bucket_winners.tolist(),
        "floatWinners": float_winners.tolist(),
        "groupQ16Winners": group_winners,
        "groupQ16Buckets": group_buckets,
        "groupQ16Scores": group_scores,
        "state519Present": 519 in fixtures["sourceStateIndices"],
        "forcedState519": {
            "state": 519,
            "hiddenVector": state519_hidden.tolist(),
            "realizedCoordinates": state519_realized.tolist(),
            "scoreFloor": state519_floor,
            "q16Winner": state519_winner,
            "q16BucketWinner": int(np.argmax(state519_buckets)),
            "floatWinner": int(np.argmax(state519_float_scores)),
            "forcedGroup": state519_group,
            "forcedGroupQ16Winner": state519_group_winner,
            "forcedGroupQ16Bucket": int(state519_buckets[state519_group_winner]),
            "forcedGroupQ16Score": float(state519_q16_scores[state519_group_winner]),
            "legacyBrowserTokenForComparison": 2032,
        },
    }


def font_settings() -> str:
    return ",".join(
        f'"{head.global_axis_tag(dimension)}" '
        f"round(nearest,calc(var(--h{dimension})/{css_number(R)}*{AXIS_STEPS}),1)"
        for dimension in range(WIDTH)
    )


def six_font_faces() -> tuple[str, str]:
    faces = []
    families = []
    for shard in range(3):
        for plane, short in (("high", "H"), ("residual", "R")):
            family = f"ProdQ16{short}{shard}"
            families.append(family)
            adjust = ";size-adjust:25600%" if plane == "high" else ""
            faces.append(
                f'@font-face{{font-family:{family};src:url("../{BANK.name}/score-{plane}-{shard}.woff2") '
                f'format("woff2"){adjust}}}'
            )
    return "".join(faces), ",".join(families)


def build_fine_stage_css(rows: list[dict[str, object]]) -> str:
    """Transform retained fine CSS, replacing its q16 graph exactly once."""
    source = (RETAINED / "fine-stage-production.css").read_text()
    source, face_count = re.subn(r"@font-face\{[^{}]*\}", "", source, count=12)
    if face_count != 12:
        raise RuntimeError(f"expected 12 retained q16 font faces, removed {face_count}")

    faces, family_text = six_font_faces()
    settings = font_settings()
    stage_rule = (
        ".fine-stage{position:fixed;left:0;top:-80000px;display:grid;"
        "grid-template-columns:max-content;grid-template-rows:1px;width:max-content;"
        "height:1px;anchor-name:--fine-winner;"
        f"font-family:{family_text};font-size:{FONT_SIZE_PX}px;line-height:1;"
        f"font-variation-settings:{settings};font-kerning:none}}"
    )
    candidate_rule = (
        ".fine-candidate{grid-area:1/1;display:block;justify-self:start;height:1px;"
        "overflow:hidden;white-space:pre;font-style:normal;"
        "width:calc-size(max-content,calc(round(nearest,"
        f"(size - var(--fine-base)*1px)*{FACTOR} + var(--score-offset),4px)"
        " + var(--local-tie)/64*1px))}"
    )
    phase_rule = f".fine-phase-0{{font-variation-settings:{settings}}}"
    source, stage_count = re.subn(r"\.fine-stage\{[^{}]*\}", stage_rule, source, count=1)
    source, candidate_count = re.subn(
        r"\.fine-candidate\{[^{}]*\}", candidate_rule, source, count=1
    )
    source, phase_count = re.subn(
        r"\.fine-phase-0\{[^{}]*\}", phase_rule, source, count=1
    )
    if (stage_count, candidate_count, phase_count) != (1, 1, 1):
        raise RuntimeError(
            "retained fine-stage q16 rule structure changed: "
            f"stage={stage_count}, candidate={candidate_count}, phase={phase_count}"
        )

    replacements: dict[int, str] = {}
    for local in range(GROUP_SIZE):
        base_branches = []
        glyph_branches = []
        for group in range(GROUPS):
            token = group * GROUP_SIZE + local
            if token >= VOCABULARY:
                break
            row = rows[token]
            base_branches.append((group, str(row["base"])))
            glyph_branches.append((group, f'"{row["glyphs"]}"'))
        replacements[local + 1] = (
            f".fine-candidate:nth-child({local + 1}){{"
            f"--fine-base:{css_if(base_branches, base_branches[0][1])};"
            f"--fine-glyphs:{css_if(glyph_branches, glyph_branches[0][1])}}}"
        )

    branch_pattern = re.compile(
        r"\.fine-candidate:nth-child\((\d+)\)\{"
        r"--fine-base:[^{}]*;--fine-glyphs:[^{}]*\}"
    )
    seen: set[int] = set()

    def replace_branch(match: re.Match[str]) -> str:
        position = int(match.group(1))
        if position not in replacements or position in seen:
            raise RuntimeError(f"unexpected retained fine branch {position}")
        seen.add(position)
        return replacements[position]

    source = branch_pattern.sub(replace_branch, source)
    if seen != set(replacements):
        missing = sorted(set(replacements) - seen)
        raise RuntimeError(f"retained fine branches not replaced: {missing[:8]}")
    if source.count("--fine-base:if(") != GROUP_SIZE:
        raise RuntimeError("replacement fine stylesheet has a duplicate/missing base graph")
    if source.count("--fine-glyphs:if(") != GROUP_SIZE:
        raise RuntimeError("replacement fine stylesheet has a duplicate/missing glyph graph")
    if "ScoreH0" in source or "ScoreL0" in source:
        raise RuntimeError("old q16 font family survived fine stylesheet transform")
    return faces + "\n" + source + "\n"


def build_hot_css() -> str:
    _faces, family_text = six_font_faces()
    return (
        ".mixed-hot-candidate{width:calc-size(max-content,calc(round(nearest,"
        f"(size - var(--base)*1px)*{FACTOR} + var(--score-offset),4px)"
        " + var(--local-tie)/64*1px));"
        f"font-family:{family_text};font-size:{FONT_SIZE_PX}px;line-height:1;"
        f"font-variation-settings:{font_settings()};font-kerning:none}}\n"
    )


def build_html(rows: list[dict[str, object]], stages: int) -> str:
    html = (RETAINED / "index.html").read_text()
    if html.count('class="candidate mixed-hot-candidate"') != HOT_ROWS:
        raise RuntimeError("retained hot-row count changed")
    if html.count('class="fine-candidate"') != stages * GROUP_SIZE:
        raise RuntimeError("retained dynamic fine-row topology changed")

    hot_index = 0

    def replace_hot(match: re.Match[str]) -> str:
        nonlocal hot_index
        row = rows[hot_index]
        token = hot_index
        hot_index += 1
        return (
            '<i class="candidate mixed-hot-candidate" '
            f'data-token="{token}" style="--base:{row["base"]};--factor:{FACTOR};'
            f'--local-tie:{row["tie"]}">{row["glyphs"]}</i>'
        )

    html = re.sub(
        r'<i class="candidate mixed-hot-candidate"[^>]*>.*?</i>',
        replace_hot,
        html,
    )
    if hot_index != HOT_ROWS:
        raise RuntimeError(f"replaced {hot_index} retained hot rows, expected {HOT_ROWS}")

    links = (
        f'<link rel="stylesheet" href="../{RETAINED.name}/coarse-production.css">\n'
        '<link rel="stylesheet" href="fine-stage-sixfont.css">\n'
        f'<link rel="stylesheet" href="../{RETAINED.name}/topology.css">\n'
        '<link rel="stylesheet" href="hot-sixfont.css">'
    )
    html, replacements = re.subn(
        r'<link rel="stylesheet" href="coarse-production\.css">\s*'
        r'<link rel="stylesheet" href="fine-stage-production\.css">\s*'
        r'<link rel="stylesheet" href="topology\.css">',
        links,
        html,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("retained stylesheet insertion point changed")
    html = html.replace(
        '<meta charset="utf-8">',
        '<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'self\'; script-src \'none\'; style-src \'self\' \'unsafe-inline\'; '
        'font-src \'self\'; img-src \'none\'; connect-src \'none\'">',
        1,
    )
    html = re.sub(
        r"<title>.*?</title>",
        f"<title>Production-range groupwise-Cauchy {stages}-stage six-font q16 cascade</title>",
        html,
        count=1,
    )
    return html


def main() -> None:
    required = [
        RETAINED / "index.html",
        RETAINED / "coarse-production.css",
        RETAINED / "fine-stage-production.css",
        RETAINED / "topology.css",
        RETAINED / "reference.json",
        BANK / "index.html",
        BANK / "reference.json",
        STATES,
        *[BANK / filename for filename in FONT_SHA256],
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    retained_reference = json.loads((RETAINED / "reference.json").read_text())
    bank_reference = json.loads((BANK / "reference.json").read_text())
    if retained_reference["groups"] != GROUPS or retained_reference["groupSize"] != GROUP_SIZE:
        raise RuntimeError("retained production routing topology changed")
    if retained_reference["hotGroups"] != [0, 1]:
        raise RuntimeError("retained hot routing changed")
    if retained_reference["stopGapBuckets"] != 49:
        raise RuntimeError("retained 49-bucket stop gate changed")
    if float(retained_reference["productionInputRange"]) != R:
        raise RuntimeError("retained production input range changed")
    if float(retained_reference["scoreGain"]) != SCORE_GAIN:
        raise RuntimeError("retained score gain changed")

    bank_manifest = assert_bank_contract(bank_reference)
    rows = parse_bank_rows()
    direct = direct_q16_reference(retained_reference)
    stages = int(retained_reference["stages"])
    html = build_html(rows, stages)
    css = build_fine_stage_css(rows)
    hot_css = build_hot_css()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "fine-stage-sixfont.css").write_text(css)
    (OUTPUT / "hot-sixfont.css").write_text(hot_css)
    obsolete_override = OUTPUT / "q16-sixfont.css"
    if obsolete_override.exists():
        obsolete_override.unlink()
    base_reference = dict(retained_reference)
    base_reference.pop("architectureAndWeightsChanged", None)
    base_reference.pop("checkpointChanged", None)
    reference = {
        **base_reference,
        "backend": "production-range-groupwise-cauchy-blockflow-sixfont-global-q16",
        "sourceRetained": RETAINED.name,
        "sixFontBankSource": BANK.name,
        "modelArchitectureChanged": False,
        "sourceCheckpointWeightsChanged": False,
        "quantizedRepresentation": "immutable global-q16 approximation",
        "runtimeContainsJavaScript": False,
        "q10Changed": False,
        "cauchyBoundsChanged": False,
        "routingTopologyChanged": False,
        "q16ConsumersReplaced": {
            "dynamicFineStages": stages,
            "rowsPerDynamicStage": GROUP_SIZE,
            "hotRows": HOT_ROWS,
            "glyphsPerRow": 6,
        },
        "q16SixFont": {
            "codesSha256": Q16_CODES_SHA256,
            "weightScale": WEIGHT_SCALE,
            "productionInputRange": R,
            "radix": 256,
            "planes": ["high", "residual"],
            "shards": 3,
            "codepointStarts": [hex(value) for value in range(0x20000, 0x80000, 0x10000)],
            "rowBase": "sum of six analytic LayerNorm bases / 16",
            "fontSizePx": FONT_SIZE_PX,
            "factor": float(FACTOR),
            "fvarUserRange": [-AXIS_STEPS, 0, AXIS_STEPS],
            "coordinateCSS": "round(nearest,h/R*16384,1)",
            "exactTransportScope": bank_reference["coordinates"]["exactTransportScope"],
            "analyticCoordinateMaximumAbsolute": bank_reference["coordinates"]["analyticCoordinateMaximumAbsolute"],
            "layerNormBound": bank_reference["layerNormBound"],
            "manifest": bank_manifest,
        },
        "directMathematicalOracle": direct,
        "lastPartialGroup": {
            "group": GROUPS - 1,
            "validRows": VOCABULARY - (GROUPS - 1) * GROUP_SIZE,
            "invalidDynamicLocalsHiddenByRetainedCSS": GROUP_SIZE - (
                VOCABULARY - (GROUPS - 1) * GROUP_SIZE
            ),
        },
        "state519": (
            "present in retained fixture suite" if direct["state519Present"]
            else "not present in retained six-fixture suite"
        ),
        "stopCertificateNote": (
            "The routing threshold remains the immutable retained 49 buckets. "
            "The verifier reports signed six-font candidate bucket deltas so any "
            "one-bucket incumbent transport effect is explicit."
        ),
        "generatedBytes": {
            "index.html": len(html.encode()),
            "fine-stage-sixfont.css": len(css.encode()),
            "hot-sixfont.css": len(hot_css.encode()),
            "referencedSixFontWoff2": bank_manifest["fontBytes"],
            "copiedFontBytes": 0,
        },
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "stages": stages,
        "dynamicRows": stages * GROUP_SIZE,
        "hotRows": HOT_ROWS,
        "htmlBytes": len(html.encode()),
        "cssBytes": len(css.encode()),
        "referencedFontBytes": bank_manifest["fontBytes"],
        "state519Present": direct["state519Present"],
    }, indent=2))


if __name__ == "__main__":
    main()
