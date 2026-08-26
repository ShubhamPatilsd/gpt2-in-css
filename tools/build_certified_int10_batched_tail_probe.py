#!/usr/bin/env python3
"""Build configurable fixed-batch certified tails after the six-stage prefix."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated"
SOURCE = ROOT / "experiments" / SOURCE_NAME
OUTPUT_ROOT_NAME = "gpt2-hvar-grid-output-head-certified-int10-batched-tail"
OUTPUT_ROOT = ROOT / "experiments" / OUTPUT_ROOT_NAME
FIXTURE_REFERENCE = (
    ROOT / "experiments"
    / "gpt2-hvar-grid-output-head-certified-int10-parallel-tail"
    / "reference.json"
)
FINE_REFERENCE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)
BATCH_SIZES = tuple(
    int(value) for value in os.environ.get("GPT2_CERTIFIED_BATCH_SIZES", "1,2,4,8")
    .split(",") if value
)
GROUPS = 197
PREFIX_GROUPS = 6
SCORE_STRIDE_PX = 1024
GROUP_TIE_STRIDE_PX = 4
CHROME_LAYOUT_LIMIT_PX = 33_554_428


def registration(name: str, initial: int = 0) -> str:
    return (
        f'@property --{name}{{syntax:"<number>";inherits:true;'
        f'initial-value:{initial}}}'
    )


def candidate_markup(html: str) -> str:
    marker = '<span id="fine-stage" class="fine-stage">'
    start = html.index(marker) + len(marker)
    stop = html.index('</span><span class="fine-reader">', start)
    return html[start:stop]


def router_markup(
    router: int,
    output_class: str,
    child: str,
    result_id: str | None = None,
) -> str:
    sources = "".join(
        f'<i class="batch-router-source batch-router-{router}-source-{group}"></i>'
        for group in range(GROUPS)
    )
    matches = "".join(
        f'<i class="batch-router-match batch-router-{router}-match-{group}"></i>'
        for group in range(GROUPS)
    )
    return (
        f'<span class="batch-router-sources">{sources}</span>'
        f'<i class="batch-router-max batch-router-{router}-max"></i>'
        f'<span class="batch-router-upper-reader batch-router-{router}-upper-reader">'
        f'<span class="batch-router-selection batch-router-{router}-selection">'
        f'{matches}<i class="batch-router-choice batch-router-{router}-choice"></i>'
        f'<span class="batch-router-group-reader batch-router-{router}-group-reader">'
        f'<output id="{result_id or output_class}" '
        f'class="batch-router-result {output_class}">'
        f'{child}</output></span></span></span>'
    )


def router_css(
    router: int,
    selected: list[str],
    group_property: str,
    upper_property: str,
    certificate: bool = False,
) -> str:
    def mask(group: int) -> str:
        return "clamp(0,min(" + ",".join(
            f"abs(var(--{name}) - {group})" for name in selected
        ) + "),1)"

    source_rules = "".join(
        f'.batch-router-{router}-source-{group}{{'
        f'position-anchor:--score-group-{group};'
        f'anchor-name:--batch-router-{router}-source-anchor-{group};'
        f'width:calc(anchor-size(--score-group-{group} width)*{mask(group)})}}'
        for group in range(GROUPS)
    )
    source_sizes = ",".join(
        f'anchor-size(--batch-router-{router}-source-anchor-{group} width)'
        for group in range(GROUPS)
    )
    match_rules = "".join(
        f'.batch-router-{router}-match-{group}{{'
        f'position-anchor:--batch-router-{router}-source-anchor-{group};'
        f'anchor-name:--batch-router-{router}-match-anchor-{group};'
        f'width:calc(clamp(0px,'
        f'anchor-size(--batch-router-{router}-source-anchor-{group} width) - '
        f'(var(--{upper_property}) - .5)*4px,1px)*{GROUPS - group})}}'
        for group in range(GROUPS)
    )
    match_sizes = ",".join(
        f'anchor-size(--batch-router-{router}-match-anchor-{group} width)'
        for group in range(GROUPS)
    )
    result_rules = (
        f'--{group_property}:calc({GROUPS} - round(nearest,100cqi/1px,1));'
    )
    if certificate:
        result_rules += (
            '--batch-certificate-gap:calc(var(--batch-merged-bucket) - '
            f'var(--{upper_property}));'
            '--batch-done:clamp(0,sign(var(--batch-certificate-gap) - '
            'var(--tail-allowance)),1);'
            '--batch-certified-winner:var(--batch-final-winner);'
        )
    return "".join((
        source_rules,
        f'.batch-router-{router}-max{{'
        f'position-anchor:--batch-router-{router}-source-anchor-0;'
        f'anchor-name:--batch-router-{router}-max-anchor;'
        f'width:max({source_sizes})}}',
        f'.batch-router-{router}-upper-reader{{'
        f'position-anchor:--batch-router-{router}-max-anchor;'
        f'width:anchor-size(--batch-router-{router}-max-anchor width);'
        f'container:batch-router-upper-{router}/inline-size}}',
        f'@container batch-router-upper-{router} (width >= 0px){{'
        f'.batch-router-{router}-selection{{--{upper_property}:'
        'round(down,100cqi/4px,1)}',
        match_rules,
        f'.batch-router-{router}-choice{{'
        f'position-anchor:--batch-router-{router}-match-anchor-0;'
        f'anchor-name:--batch-router-{router}-choice-anchor;'
        f'width:max({match_sizes})}}',
        f'.batch-router-{router}-group-reader{{'
        f'position-anchor:--batch-router-{router}-choice-anchor;'
        f'width:anchor-size(--batch-router-{router}-choice-anchor width);'
        f'container:batch-router-group-{router}/inline-size}}',
        f'@container batch-router-group-{router} (width >= 0px){{'
        f'.batch-router-result.{group_property}{{{result_rules}'
        f'display:block;width:calc(var(--{group_property})*1px)}}}}}}',
    ))


def scorer_markup(slot: int, candidates: str) -> str:
    return (
        f'<span id="batch-fine-stage-{slot}" '
        f'class="fine-stage batch-fine-stage batch-fine-stage-{slot}" '
        f'style="--group:var(--batch-group-{slot});'
        f'anchor-name:--batch-fine-winner-{slot}">{candidates}</span>'
        f'<span id="batch-fine-reader-{slot}" '
        f'class="batch-fine-reader batch-fine-reader-{slot}" '
        f'style="--group:var(--batch-group-{slot});'
        f'position-anchor:--batch-fine-winner-{slot}">'
        f'<i id="batch-fine-result-{slot}" '
        f'class="batch-fine-result batch-fine-result-{slot}">'
        f'<i id="batch-score-carrier-{slot}" '
        f'class="batch-score-carrier batch-score-carrier-{slot}"></i>'
        f'<i id="batch-token-carrier-{slot}" '
        f'class="batch-token-carrier batch-token-carrier-{slot}"></i>'
        '</i></span>'
    )


def scorer_css(slot: int) -> str:
    return "".join((
        f'.batch-fine-stage-{slot}{{top:{-28_000 + slot * 5}px}}',
        f'.batch-fine-reader-{slot}{{'
        f'position-anchor:--batch-fine-winner-{slot};'
        f'width:anchor-size(--batch-fine-winner-{slot} width,0px);'
        f'container:batch-fine-read-{slot}/inline-size}}',
        f'@container batch-fine-read-{slot} (width >= 1px){{'
        f'.batch-fine-result-{slot}{{'
        f'--batch-bucket-{slot}:round(down,100cqi/4px,1);'
        f'--batch-local-{slot}:calc(255 - '
        'round(nearest,mod(100cqi,4px)/1px*64,1));'
        f'--batch-winner-{slot}:calc(var(--batch-group-{slot})*256 + '
        f'var(--batch-local-{slot}));display:block}}'
        f'.batch-score-carrier-{slot}{{width:calc('
        f'var(--batch-bucket-{slot})*{SCORE_STRIDE_PX}px + '
        f'({GROUPS} - var(--batch-group-{slot}))*{GROUP_TIE_STRIDE_PX}px)}}'
        f'.batch-token-carrier-{slot}{{'
        f'width:calc(var(--batch-winner-{slot})*1px)}}}}',
    ))


def merge_markup(batch: int, certificate: str, candidates: str) -> str:
    token_sources = '<i class="batch-token-source batch-prefix-token-source"></i>'
    token_sources += "".join(
        f'<i class="batch-token-source batch-token-source-{slot}"></i>'
        for slot in range(batch)
    )
    scorers = "".join(scorer_markup(slot, candidates) for slot in range(batch))
    return (
        '<span id="batch-compute" class="batch-compute">'
        '<i id="batch-prefix-score" class="batch-prefix-score"></i>'
        '<i id="batch-prefix-token" class="batch-prefix-token"></i>'
        f'{scorers}<i id="batch-score-max" class="batch-score-max"></i>'
        '<span id="batch-score-reader" class="batch-score-reader">'
        '<output id="batch-score-result" class="batch-score-result">'
        f'{token_sources}<i id="batch-token-max" class="batch-token-max"></i>'
        '<span id="batch-token-reader" class="batch-token-reader">'
        '<output id="batch-final-result" class="batch-final-result">'
        f'{certificate}</output></span></output></span></span>'
    )


def merge_css(batch: int) -> str:
    score_anchors = ['anchor-size(--batch-prefix-score-anchor width)'] + [
        f'anchor-size(--batch-score-anchor-{slot} width)' for slot in range(batch)
    ]
    token_anchors = ['anchor-size(--batch-prefix-token-source-anchor width)'] + [
        f'anchor-size(--batch-token-source-anchor-{slot} width)'
        for slot in range(batch)
    ]
    slot_rules = "".join(
        f'.batch-score-carrier-{slot}{{anchor-name:--batch-score-anchor-{slot}}}'
        f'.batch-token-carrier-{slot}{{anchor-name:--batch-token-anchor-{slot}}}'
        f'.batch-token-source-{slot}{{'
        f'position-anchor:--batch-token-anchor-{slot};'
        f'anchor-name:--batch-token-source-anchor-{slot};'
        f'width:calc(anchor-size(--batch-token-anchor-{slot} width)*'
        f'(1 - clamp(0,abs(var(--batch-winning-group) - '
        f'var(--batch-group-{slot})),1)))}}'
        for slot in range(batch)
    )
    return "".join((
        '.batch-prefix-score{anchor-name:--batch-prefix-score-anchor;'
        f'width:calc(var(--best-bucket-5)*{SCORE_STRIDE_PX}px + '
        f'({GROUPS} - round(down,var(--best-winner-5)/256,1))*'
        f'{GROUP_TIE_STRIDE_PX}px)}}',
        '.batch-prefix-token{anchor-name:--batch-prefix-token-anchor;'
        'width:calc(var(--best-winner-5)*1px)}',
        slot_rules,
        '.batch-score-max{position-anchor:--batch-prefix-score-anchor;'
        'anchor-name:--batch-score-max-anchor;'
        f'width:max({",".join(score_anchors)})}}',
        '.batch-score-reader{position-anchor:--batch-score-max-anchor;'
        'width:anchor-size(--batch-score-max-anchor width);'
        'container:batch-score-read/inline-size}',
        '@container batch-score-read (width >= 0px){.batch-score-result{'
        f'--batch-merged-bucket:round(down,100cqi/{SCORE_STRIDE_PX}px,1);'
        f'--batch-winning-group:calc({GROUPS} - round(nearest,'
        f'mod(100cqi,{SCORE_STRIDE_PX}px)/{GROUP_TIE_STRIDE_PX}px,1));'
        'display:block}}',
        '.batch-prefix-token-source{position-anchor:--batch-prefix-token-anchor;'
        'anchor-name:--batch-prefix-token-source-anchor;'
        'width:calc(anchor-size(--batch-prefix-token-anchor width)*'
        '(1 - clamp(0,abs(var(--batch-winning-group) - '
        'round(down,var(--best-winner-5)/256,1)),1)))}',
        '.batch-token-max{position-anchor:--batch-prefix-token-source-anchor;'
        'anchor-name:--batch-token-max-anchor;'
        f'width:max({",".join(token_anchors)})}}',
        '.batch-token-reader{position-anchor:--batch-token-max-anchor;'
        'width:anchor-size(--batch-token-max-anchor width);'
        'container:batch-token-read/inline-size}',
        '@container batch-token-read (width >= 0px){.batch-final-result{'
        '--batch-final-winner:round(nearest,100cqi/1px,1);'
        'display:block;width:calc(var(--batch-final-winner)*1px)}}',
    ))


def build_serial_comparator(batch: int, destination: Path) -> None:
    serial_name = f"{OUTPUT_ROOT_NAME}/b{batch}/serial"
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(ROOT / "tools"),
        "GPT2_CERTIFIED_STAGES": str(PREFIX_GROUPS + batch),
        "GPT2_CERTIFIED_GATE": "1",
        "GPT2_CERTIFIED_SLACK_BUCKETS": "8",
        "GPT2_CERTIFIED_CASCADE_DIR": serial_name,
    }
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_certified_int10_unrolled_cascade.py")],
        cwd=ROOT,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    css_path = destination / "index.css"
    css = css_path.read_text()
    pattern = re.compile(
        r'--done-(\d+):clamp\(0,sign\(var\(--certificate-gap-\1\) - 17\) '
        r'\+ 1,1\)'
    )
    css, replacements = pattern.subn(
        lambda match: (
            f'--done-{match.group(1)}:clamp(0,sign('
            f'var(--certificate-gap-{match.group(1)}) - var(--tail-allowance)),1)'
        ),
        css,
    )
    if replacements != PREFIX_GROUPS + batch:
        raise RuntimeError(f"serial b{batch}: replaced {replacements} stop rules")
    css = css.replace('url("../gpt', 'url("../../../gpt')
    css += registration("tail-allowance", -100_000) + "\n"
    css_path.write_text(css)
    html_path = destination / "index.html"
    serial_html = html_path.read_text()
    inherited_link = (
        'href="../gpt2-hvar-grid-output-head-certified-upper-int10/index.css"'
    )
    if serial_html.count(inherited_link) != 1:
        raise RuntimeError(f"serial b{batch}: inherited stylesheet link missing")
    serial_html = serial_html.replace(
        inherited_link,
        'href="../../../gpt2-hvar-grid-output-head-certified-upper-int10/index.css"',
    )
    html_path.write_text(serial_html)


def fixture_oracles(batch: int, source_reference: dict[str, object]) -> list[dict[str, object]]:
    fixtures = source_reference["parallelTailFixtures"]["selected"]
    hidden = np.asarray([fixture["hiddenVector"] for fixture in fixtures], dtype=np.float64)
    floors = np.asarray([fixture["scoreFloor"] for fixture in fixtures], dtype=int)
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    row_scales = np.max(np.abs(weights), axis=1) / head.WEIGHT_MAX
    row_scales[row_scales == 0] = 1.0
    coarse = np.rint(weights / row_scales[:, None]) * row_scales[:, None]
    errors = np.linalg.norm(weights - coarse, axis=1)
    fine_reference = json.loads(FINE_REFERENCE.read_text())
    fine_scale = float(fine_reference["weightScale"])
    fine = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
    upper = hidden @ coarse.T + np.linalg.norm(hidden, axis=1)[:, None] * errors
    fine_scores = hidden @ fine.T
    upper_buckets = np.floor(
        (upper - floors[:, None]) * head.SCORE_SCALE
    ).astype(int) + 1
    fine_buckets = np.rint(
        (fine_scores - floors[:, None]) * head.SCORE_SCALE
    ).astype(int)
    group_upper = np.empty((len(hidden), GROUPS), dtype=int)
    group_winner = np.empty_like(group_upper)
    group_bucket = np.empty_like(group_upper)
    for group in range(GROUPS):
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        group_upper[:, group] = np.max(upper_buckets[:, start:stop], axis=1)
        local = np.argmax(fine_buckets[:, start:stop], axis=1)
        winners = start + local
        group_winner[:, group] = winners
        group_bucket[:, group] = fine_buckets[np.arange(len(hidden)), winners]
    order = np.argsort(-group_upper, axis=1, kind="stable")
    output = []
    for fixture_index, fixture in enumerate(fixtures):
        prefix_groups = order[fixture_index, :PREFIX_GROUPS]
        prefix_pairs = [
            (int(group_bucket[fixture_index, group]), int(group_winner[fixture_index, group]))
            for group in prefix_groups
        ]
        prefix_bucket, prefix_winner = min(prefix_pairs, key=lambda x: (-x[0], x[1]))
        groups = order[fixture_index, PREFIX_GROUPS:PREFIX_GROUPS + batch].astype(int)
        winners = group_winner[fixture_index, groups].astype(int)
        buckets = group_bucket[fixture_index, groups].astype(int)
        merged_bucket, merged_winner = min(
            [(prefix_bucket, prefix_winner), *zip(buckets.tolist(), winners.tolist())],
            key=lambda x: (-x[0], x[1]),
        )
        next_group = int(order[fixture_index, PREFIX_GROUPS + batch])
        next_upper = int(group_upper[fixture_index, next_group])
        gap = merged_bucket - next_upper
        allowance = int(fixture["totalAllowanceBuckets"])
        output.append({
            **fixture,
            "batchSize": batch,
            "batchGroups": groups.tolist(),
            "batchFineWinners": winners.tolist(),
            "batchFineBuckets": buckets.tolist(),
            "batchMergedWinner": merged_winner,
            "batchMergedBucket": merged_bucket,
            "batchNextGroup": next_group,
            "batchNextUpperBucket": next_upper,
            "batchCertificateGap": gap,
            "batchCertified": gap > allowance,
        })
    return output


def build_variant(batch: int) -> dict[str, object]:
    if batch < 1 or batch > 16:
        raise ValueError("batch size must be between 1 and 16")
    destination = OUTPUT_ROOT / f"b{batch}"
    destination.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / "index.html").read_text()
    candidates = candidate_markup(html)

    selected = ["group", *(f"remaining-group-{stage}" for stage in range(1, 6))]
    batch_selected = ["batch-group-0"]
    cert_router = batch
    certificate = router_markup(
        cert_router,
        "batch-next-group",
        "",
        result_id="batch-certificate-result",
    )
    compute = merge_markup(batch, certificate, candidates)
    child = compute
    for slot in range(batch - 1, 0, -1):
        child = router_markup(slot, f"batch-group-{slot}", child)
    tail = f'<span id="batch-start" class="batch-start">{child}</span>'
    marker = '<output id="remaining-result-6" class="remaining-result-6"></output>'
    if html.count(marker) != 1:
        raise RuntimeError("sixth prefix result insertion point missing")
    html = html.replace(
        marker,
        '<output id="remaining-result-6" class="remaining-result-6">'
        + tail + '</output>',
        1,
    ).replace(
        "Certified int10 6-stage unrolled cascade",
        f"Certified int10 six-stage plus batch-{batch} exact tail",
        1,
    )
    inherited_link = (
        'href="../gpt2-hvar-grid-output-head-certified-upper-int10/index.css"'
    )
    if html.count(inherited_link) != 1:
        raise RuntimeError("inherited coarse stylesheet link missing")
    html = html.replace(
        inherited_link,
        'href="../../gpt2-hvar-grid-output-head-certified-upper-int10/index.css"',
    )

    css = (SOURCE / "index.css").read_text()
    for stage in range(PREFIX_GROUPS):
        old = (
            f"--done-{stage}:clamp(0,sign(var(--certificate-gap-{stage}) - "
            "49) + 1,1)"
        )
        new = (
            f"--done-{stage}:clamp(0,sign(var(--certificate-gap-{stage}) - "
            "var(--tail-allowance)),1)"
        )
        if css.count(old) != 1:
            raise RuntimeError(f"prefix stage {stage} stop expression missing")
        css = css.replace(old, new, 1)
    css = css.replace('url("../gpt', 'url("../../gpt')

    registrations = [
        registration("tail-allowance", -100_000),
        registration("batch-merged-bucket"),
        registration("batch-winning-group"),
        registration("batch-final-winner"),
        registration("batch-certificate-gap"),
        registration("batch-done"),
        registration("batch-certified-winner"),
    ]
    for slot in range(batch):
        registrations.extend((
            registration(f"batch-group-{slot}"),
            registration(f"batch-upper-{slot}"),
            registration(f"batch-bucket-{slot}"),
            registration(f"batch-local-{slot}"),
            registration(f"batch-winner-{slot}"),
        ))
    registrations.extend((
        registration("batch-next-group"),
        registration("batch-next-upper"),
    ))
    fixed = (
        'body{anchor-scope:all}'
        '.batch-start,.batch-router-source,.batch-router-max,'
        '.batch-router-upper-reader,.batch-router-match,.batch-router-choice,'
        '.batch-router-group-reader,.batch-router-result,.batch-compute,'
        '.batch-fine-stage,.batch-fine-reader,.batch-fine-result,'
        '.batch-score-carrier,.batch-token-carrier,.batch-prefix-score,'
        '.batch-prefix-token,.batch-score-max,.batch-score-reader,'
        '.batch-score-result,.batch-token-source,.batch-token-max,'
        '.batch-token-reader,.batch-final-result{'
        'position:fixed;left:0;top:-30000px;height:1px}'
        '.batch-start{--batch-group-0:var(--remaining-group-6);'
        '--batch-upper-0:var(--upper-bucket-6);'
        'display:if(style(--done-0:1):none;style(--done-1:1):none;'
        'style(--done-2:1):none;style(--done-3:1):none;'
        'style(--done-4:1):none;style(--done-5:1):none;else:block)}'
        '.batch-fine-reader{width:0;top:-27500px}'
        '.batch-score-carrier,.batch-token-carrier,.batch-token-source{width:0}'
    )
    css_parts = [css, "".join(registrations), fixed]
    for slot in range(1, batch):
        selected_now = [*selected, *batch_selected]
        css_parts.append(router_css(
            slot,
            selected_now,
            f"batch-group-{slot}",
            f"batch-upper-{slot}",
        ))
        batch_selected.append(f"batch-group-{slot}")
    for slot in range(batch):
        css_parts.append(scorer_css(slot))
    css_parts.append(merge_css(batch))
    css_parts.append(router_css(
        cert_router,
        [*selected, *batch_selected],
        "batch-next-group",
        "batch-next-upper",
        certificate=True,
    ))
    css = "".join(css_parts) + "\n"

    source_reference = json.loads(FIXTURE_REFERENCE.read_text())
    oracles = fixture_oracles(batch, source_reference)
    reference = {
        "model": "openai-community/gpt2",
        "backend": f"certified-int10-six-stage-plus-batch-{batch}-parallel-tail",
        "source": SOURCE_NAME,
        "batchSize": batch,
        "groups": GROUPS,
        "prefixGroups": PREFIX_GROUPS,
        "scoreGeometryPixelsPerBucket": SCORE_STRIDE_PX,
        "groupTiePixelsPerGroup": GROUP_TIE_STRIDE_PX,
        "chromeLayoutLimitPixels": CHROME_LAYOUT_LIMIT_PX,
        "fixtures": oracles,
    }
    (destination / "index.html").write_text(html)
    (destination / "index.css").write_text(css)
    reference["htmlBytes"] = (destination / "index.html").stat().st_size
    reference["cssBytes"] = (destination / "index.css").stat().st_size
    reference["domElements"] = len(re.findall(
        r'<(?:div|span|i|main|section|output|input|label)\b', html
    ))
    maximum = max(
        int(fixture["batchMergedBucket"]) * SCORE_STRIDE_PX
        + (GROUPS - int(fixture["batchMergedWinner"]) // head.GROUP_SIZE)
        * GROUP_TIE_STRIDE_PX
        for fixture in oracles
    )
    reference["maxFixtureMergeGeometryPixels"] = maximum
    if maximum >= CHROME_LAYOUT_LIMIT_PX:
        raise RuntimeError(f"batch {batch} merge exceeds Chrome layout limit")
    (destination / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    build_serial_comparator(batch, destination / "serial")
    return {
        "batchSize": batch,
        "htmlBytes": reference["htmlBytes"],
        "cssBytes": reference["cssBytes"],
        "domElements": reference["domElements"],
        "certifiedFixtures": sum(bool(fixture["batchCertified"]) for fixture in oracles),
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if not BATCH_SIZES:
        raise ValueError("at least one batch size is required")
    results = [build_variant(batch) for batch in BATCH_SIZES]
    (OUTPUT_ROOT / "build-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"output": str(OUTPUT_ROOT.relative_to(ROOT)), "variants": results}, indent=2))


if __name__ == "__main__":
    main()
