#!/usr/bin/env python3
"""Build the minimal one-text-node GPT-2 min-content argmax gate."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-global11-shard256-inline-tie"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT = ROOT / "experiments" / "gpt2-mincontent-word-argmax"
GROUP_SIZE = 256
SCORE_STARTS = (0x20000, 0x30000, 0x40000)
TIE_START = 0xD0000
UPM = 16_384
SAFE_BASE = 1_024
SCORE_DISPLAY_SCALE = 4


def build_aux_font(path: Path) -> None:
    glyph_order = [".notdef", "space"] + [f"tie{tie}" for tie in range(GROUP_SIZE)]
    cmap = {0x20: "space", 0x2060: "space"}
    cmap.update({TIE_START + tie: f"tie{tie}" for tie in range(GROUP_SIZE)})
    glyphs = {}
    metrics = {".notdef": (0, 0), "space": (0, 0)}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        glyphs[name] = pen.glyph()
    for tie in range(GROUP_SIZE):
        metrics[f"tie{tie}"] = (tie, 0)

    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=UPM, descent=0)
    builder.setupOS2(
        sTypoAscender=UPM,
        sTypoDescender=0,
        usWinAscent=UPM,
        usWinDescent=0,
    )
    builder.setupNameTable({
        "familyName": "WordAux",
        "styleName": "Regular",
        "uniqueFontIdentifier": "WordAux Gate 1",
        "fullName": "WordAux Gate 1",
        "psName": "WordAux-Gate1",
    })
    builder.setupPost()
    builder.setupMaxp()
    temporary = path.with_suffix(".ttf")
    builder.save(temporary)
    font = TTFont(temporary)
    font.flavor = "woff2"
    font.save(path)
    temporary.unlink()


def build_rebased_score_fonts() -> list[Path]:
    source = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global11-shard256"
    outputs = []
    for shard in range(3):
        source_path = source / f"score-d{shard}.woff2"
        output_path = OUTPUT / f"score-d{shard}.woff2"
        font = TTFont(source_path)
        metrics = font["hmtx"].metrics
        for glyph, (_, left_side_bearing) in list(metrics.items()):
            metrics[glyph] = (SAFE_BASE, left_side_bearing)
        font.flavor = "woff2"
        font.save(output_path)
        outputs.append(output_path)
    return outputs


def score_word(token: int) -> str:
    tie = GROUP_SIZE - 1 - token
    glyphs = [*(chr(start + token) for start in SCORE_STARTS), chr(TIE_START + tie)]
    return "\u2060".join(glyphs)


def build_full_group_topology(source: dict[str, object], factor: float) -> dict[str, object]:
    vocabulary = int(source["vocabulary"])
    groups = math.ceil(vocabulary / GROUP_SIZE)
    group_markup = []
    for group in range(groups):
        start = group * GROUP_SIZE
        stop = min(vocabulary, start + GROUP_SIZE)
        words = " ".join(score_word(token) for token in range(start, stop))
        group_markup.append(
            f'<section class="group-wrapper" style="anchor-name:'
            f'--score-group-{group},--group-{group}">'
            f'<div class="group-grid word-run group-{group}">{words}</div></section>'
        )
    match_carriers = "".join(
        f'<i class="match-carrier match-carrier-{group}"></i>'
        for group in range(groups)
    )
    carriers = "".join(
        f'<i class="carrier carrier-{group}"></i>' for group in range(groups)
    )
    fan_in = 16
    chunks = math.ceil(groups / fan_in)
    chunk_markup = "".join(
        f'<i class="outer-max-chunk outer-max-chunk-{chunk}"></i>'
        for chunk in range(chunks)
    )
    html = f"""<!doctype html>
<meta charset="utf-8">
<title>GPT-2 shard-256 min-content word-run argmax</title>
<link rel="stylesheet" href="index.css">
<main id="model" class="model"><div class="group-scroller"><div class="group-track">
{''.join(group_markup)}</div></div></main>
{chunk_markup}<i class="direct-outer-max"></i>
<div class="outer-reader"><div class="selection">
{match_carriers}<i class="group-choice"></i>
<div class="group-choice-reader"><div class="group-selection">
{carriers}<i class="selected"></i>
<div class="selected-reader"><output id="result" class="result"></output></div>
</div></div></div></div>
"""

    css = (SOURCE / "index.css").read_text()
    for shard in range(3):
        css += (
            f'@font-face{{font-family:WordScore;src:url("score-d{shard}.woff2") '
            f'format("woff2");unicode-range:U+{SCORE_STARTS[shard]:X}-'
            f'{SCORE_STARTS[shard] + vocabulary - 1:X}}}'
        )
    css += (
        f'@font-face{{font-family:WordScore;src:url("word-aux.woff2") '
        f'format("woff2");size-adjust:6.4%;unicode-range:U+20,U+2060,'
        f'U+{TIE_START:X}-{TIE_START + GROUP_SIZE - 1:X}}}'
        '.word-run{display:block!important;width:min-content!important;height:1px!important;'
        'white-space:normal!important;word-break:keep-all!important;overflow-wrap:normal!important;'
        'overflow:visible!important;anchor-name:none!important;'
        'font-family:WordScore!important;font-size:4000px!important}'
        f'.group-wrapper{{width:calc-size(max-content,calc(round(nearest,'
        f'(size - mod(size,4px) - {SAFE_BASE * 3 * SCORE_DISPLAY_SCALE}px) * '
        f'{factor / SCORE_DISPLAY_SCALE:.12g} + var(--score-offset),4px) + mod(size,4px)))}}'
        '.model{timeline-scope:none!important}.group-proxy{display:none!important}'
        '.outer-reader{position-anchor:--direct-outer-max!important;'
        'width:anchor-size(--direct-outer-max width)!important}'
        '.outer-max-chunk,.direct-outer-max{position:fixed;left:0;top:-94000px;height:1px}'
    )
    chunk_names = []
    for chunk in range(chunks):
        start = chunk * fan_in
        stop = min(groups, start + fan_in)
        terms = ",".join(
            f"anchor-size(--score-group-{group} width)" for group in range(start, stop)
        )
        css += (
            f'.outer-max-chunk-{chunk}{{anchor-name:--outer-max-chunk-{chunk};'
            f'width:max({terms})}}'
        )
        chunk_names.append(f"anchor-size(--outer-max-chunk-{chunk} width)")
    css += (
        '.direct-outer-max{anchor-name:--direct-outer-max;'
        f'width:max({",".join(chunk_names)})}}\n'
    )

    (OUTPUT / "index.html").write_text(html)
    (OUTPUT / "index.css").write_text(css)
    return {
        "topology": "A-197-group-word-runs",
        "groups": groups,
        "groupRunElements": groups,
        "words": vocabulary,
        "scoreGlyphs": vocabulary * len(SCORE_STARTS),
        "identityGlyphs": vocabulary,
        "wordJoiners": vocabulary * len(SCORE_STARTS),
        "spaces": vocabulary - groups,
        "outerMaximumFanIn": fan_in,
        "outerMaximumChunks": chunks,
        "scoreDisplayScale": SCORE_DISPLAY_SCALE,
        "rebasedAdvancePerShard": SAFE_BASE,
        "rebasedWordBasePx": SAFE_BASE * 3 * SCORE_DISPLAY_SCALE,
        "runtimeJavaScript": False,
        "htmlBytes": len(html.encode()),
        "cssBytes": len(css.encode()),
    }


def build_scaling_curve() -> None:
    source = json.loads((SOURCE / "reference.json").read_text())
    retained = json.loads((
        ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max-shard256" /
        "reference.json"
    ).read_text())
    fixtures = retained["certifiedFixtures"]
    scaling = OUTPUT / "scaling"
    scaling.mkdir(parents=True, exist_ok=True)
    settings = ",".join(
        f'"X{dimension:03X}" calc(var(--h{dimension}) / {source["inputRange"]:.12g})'
        for dimension in range(int(source["width"]))
    )
    css = f"""@font-face{{font-family:Score0;src:url("../../gpt2-hvar-grid-output-head-global11-shard256/score-d0.woff2") format("woff2")}}
@font-face{{font-family:Score1;src:url("../../gpt2-hvar-grid-output-head-global11-shard256/score-d1.woff2") format("woff2")}}
@font-face{{font-family:Score2;src:url("../../gpt2-hvar-grid-output-head-global11-shard256/score-d2.woff2") format("woff2")}}
@font-face{{font-family:WordAux;src:url("../word-aux.woff2") format("woff2");size-adjust:.105879643486%}}
*{{box-sizing:border-box}}html,body{{margin:0}}main{{font-variation-settings:{settings};font-kerning:none}}
.runs{{position:fixed;left:0;top:0}}.word-run{{display:block;width:min-content;height:1px;overflow:visible;white-space:normal;word-break:keep-all;overflow-wrap:normal;font-family:Score0,Score1,Score2,WordAux;font-size:399px;line-height:1px}}
.controls{{position:fixed;left:0;top:0}}.control{{display:block;width:max-content;height:0;font-family:Score0,Score1,Score2;font-size:399px;line-height:1px}}.control>i{{display:block;width:max-content;height:0;overflow:visible;white-space:pre;font-style:normal}}
"""
    (scaling / "scaling.css").write_text(css)
    initial_style = ";".join(
        f"--h{dimension}:{value}"
        for dimension, value in enumerate(fixtures["hiddenVectors"][0])
    )
    counts = (1, 4, 16, 64, 128, 197)
    for count in counts:
        word_groups = []
        control_groups = []
        for group in range(count):
            start = group * GROUP_SIZE
            stop = min(int(source["vocabulary"]), start + GROUP_SIZE)
            word_groups.append(
                f'<div class="word-run">{" ".join(score_word(token) for token in range(start, stop))}</div>'
            )
            candidates = []
            for token in range(start, stop):
                score = "".join(chr(base + token) for base in SCORE_STARTS)
                candidates.append(f"<i>{score}</i>")
            control_groups.append(f'<div class="control">{"".join(candidates)}</div>')
        prefix = (
            '<!doctype html><meta charset="utf-8"><link rel="stylesheet" '
            f'href="scaling.css"><main style="{initial_style}">'
        )
        (scaling / f"word-{count}.html").write_text(
            prefix + f'<div class="runs">{"".join(word_groups)}</div></main>'
        )
        if count <= 64:
            (scaling / f"control-{count}.html").write_text(
                prefix + f'<div class="controls">{"".join(control_groups)}</div></main>'
            )
    (scaling / "reference.json").write_text(json.dumps({
        "counts": list(counts),
        "controlCounts": [1, 4, 16, 64],
        "displayScale": 0.399,
        "fixtures": fixtures["hiddenVectors"][:2],
        "wordTopology": "one text node per 256-token group; U+2060 within candidates; U+0020 between candidates",
        "fullAttemptSymptom": (
            "197-run full topology did not return from document.fonts.ready plus first layout "
            "after more than 180 seconds; no network requests remained, renderer stayed alive/idle, "
            "and no browser result JSON was produced"
        ),
    }, indent=2) + "\n")
    print(json.dumps({"scaling": str(scaling.relative_to(ROOT)), "counts": counts}, indent=2))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = json.loads((SOURCE / "reference.json").read_text())
    total_base = sum(source["rowBaseMaximums"])
    factor = (
        source["inputRange"]
        * source["weightScale"]
        * source["scoreScale"]
        * source["scoreStridePx"]
    )
    words = [score_word(token) for token in range(GROUP_SIZE)]
    candidates = []
    for token in range(GROUP_SIZE):
        tie = GROUP_SIZE - 1 - token
        score = "".join(chr(start + token) for start in SCORE_STARTS)
        candidates.append(f'<i style="--local-tie:{tie}">{score}</i>')

    settings = ",".join(
        f'"X{dimension:03X}" calc(var(--h{dimension}) / {source["inputRange"]:.12g})'
        for dimension in range(source["width"])
    )
    html = f"""<!doctype html>
<meta charset="utf-8">
<title>GPT-2 min-content word argmax Gate 1</title>
<link rel="stylesheet" href="gate1.css">
<main id="gate">
  <section id="word-side"><div id="word-run">{' '.join(words)}</div></section>
  <section id="control-side"><div id="control">{''.join(candidates)}</div></section>
</main>
"""
    css = f"""@font-face{{font-family:Score0;src:url(\"../{SOURCE_NAME}/../gpt2-hvar-grid-output-head-global11-shard256/score-d0.woff2\") format(\"woff2\")}}
@font-face{{font-family:Score1;src:url(\"../{SOURCE_NAME}/../gpt2-hvar-grid-output-head-global11-shard256/score-d1.woff2\") format(\"woff2\")}}
@font-face{{font-family:Score2;src:url(\"../{SOURCE_NAME}/../gpt2-hvar-grid-output-head-global11-shard256/score-d2.woff2\") format(\"woff2\")}}
@font-face{{font-family:WordAux;src:url(\"word-aux.woff2\") format(\"woff2\");size-adjust:{25.6 / factor:.12g}%}}
*{{box-sizing:border-box}}html,body{{margin:0}}#gate{{--display-scale:.4;font-variation-settings:{settings};font-kerning:none;line-height:1px}}
#word-side,#control-side{{position:absolute;left:0;top:0}}
#word-run{{display:block;width:min-content;white-space:normal;word-break:keep-all;overflow-wrap:normal;font-family:Score0,Score1,Score2,WordAux;font-size:calc(1000px * var(--display-scale));height:1px;overflow:visible}}
#control{{display:grid;grid-template-columns:max-content;grid-template-rows:1px;width:max-content;height:1px;font-family:Score0,Score1,Score2;font-size:calc(1000px * var(--display-scale))}}
#control>i{{grid-area:1/1;display:block;justify-self:start;height:1px;overflow:hidden;white-space:pre;font-style:normal;width:calc-size(max-content,calc(round(nearest,(size - {total_base}px * var(--display-scale)) * {factor:.12g} + var(--score-offset) * var(--display-scale),4px * var(--display-scale)) + var(--local-tie)/64*1px * var(--display-scale)))}}
"""

    fixtures = [{
        "name": "synthetic-all-tied",
        "hidden": [0.0] * source["width"],
        "scoreFloor": 0,
    }] + [
        {
            "name": f"source-{index}",
            "hidden": hidden,
            "scoreFloor": source["scoreFloors"][index],
        }
        for index, hidden in enumerate(source.get("hiddenVectors", []))
    ]
    validation = source["validation"]
    fixtures.extend(
        {
            "name": f"token-{token}",
            "hidden": hidden,
            "scoreFloor": floor,
        }
        for token, hidden, floor in zip(
            validation["tokenIds"],
            validation["hiddenVectors"],
            validation["scoreFloors"],
            strict=True,
        )
    )
    if not fixtures:
        raise RuntimeError("source has no saved hidden-vector fixtures")

    build_aux_font(OUTPUT / "word-aux.woff2")
    score_fonts = build_rebased_score_fonts()
    (OUTPUT / "gate1.html").write_text(html)
    (OUTPUT / "gate1.css").write_text(css)
    full = build_full_group_topology(source, factor)
    retained = json.loads((
        ROOT / "experiments" / "gpt2-mixed-hot2-blockflow-group-max-shard256" /
        "reference.json"
    ).read_text())
    reference = {
        "gate": 1,
        "source": SOURCE_NAME,
        "group": 0,
        "tokens": GROUP_SIZE,
        "wordRunElements": 1,
        "wordTextNodes": 1,
        "words": GROUP_SIZE,
        "scoreGlyphsPerWord": len(SCORE_STARTS),
        "identityGlyphsPerWord": 1,
        "wordJoinersPerWord": len(SCORE_STARTS),
        "spaces": GROUP_SIZE - 1,
        "controlCandidateElements": GROUP_SIZE,
        "scoreFontFilesReused": 3,
        "totalBase": total_base,
        "factor": factor,
        "fixtures": fixtures,
        "full": full,
        "fullFixtures": retained["certifiedFixtures"],
        "rebasedScoreFontBytes": sum(path.stat().st_size for path in score_fonts),
        "globalRunFeasibility": {
            "topology": "B-one-50257-word-run",
            "built": False,
            "reason": (
                "a global lower-token tie needs 50,257 distinct width ranks; at 1/64px "
                "layout precision its tie span is 785.25px, requiring a score stride "
                "above that span. Scaling one HVAR font-unit score step that far cannot "
                "keep the observed signed score range and a nonnegative base below the "
                "32,768px per-word advance clamp"
            ),
            "minimumTieSpanPx": vocabulary / 64 if (vocabulary := int(source["vocabulary"])) else 0,
            "requiredScoreStrideGreaterThanPx": vocabulary / 64,
            "perWordClampPx": 32768,
        },
        "runtimeJavaScript": False,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "fixtures": len(fixtures),
        "words": GROUP_SIZE,
        "controlElements": GROUP_SIZE,
    }, indent=2))


if __name__ == "__main__":
    if "--scaling-only" in sys.argv:
        build_scaling_curve()
    else:
        main()
