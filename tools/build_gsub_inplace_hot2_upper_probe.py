#!/usr/bin/env python3
"""Prove or reject an in-place split-GSUB hot-two upper/fine topology.

This is deliberately an offline topology gate.  It emits no browser page when
the proposed GSUB scorer cannot remove the retained K=2 candidate rows.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-gsub-inplace-hot2-upper"
RETAINED = ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper"
SPLIT = ROOT / "experiments" / "gsub-split-complement-fine-scorer"

HOT_GROUPS = (0, 1)
GROUP_SIZE = 256
EXISTING_BROWSER_ALLOWANCE_BUCKETS = 24
OBSERVED_GSUB_ERROR_BUCKETS = 2
MARGIN_THRESHOLD_BUCKETS = 4


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def candidate_count(html: str, class_name: str) -> int:
    return len(re.findall(rf'<i class="[^"]*\b{re.escape(class_name)}\b[^"]*"', html))


def candidate_glyph_counts(html: str, class_name: str) -> list[int]:
    matches = re.findall(
        rf'<i class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</i>',
        html,
    )
    counts = []
    for content in matches:
        entities = re.findall(r"&#x[0-9A-Fa-f]+;", content)
        counts.append(len(entities) if entities else len(content))
    return counts


def hot_group_sections(html: str) -> list[str]:
    sections = []
    for group in HOT_GROUPS:
        match = re.search(
            rf'<section class="group-wrapper"[^>]*--score-group-{group};[^>]*>'
            rf'.*?</section>',
            html,
        )
        if not match:
            raise RuntimeError(f"retained hot group {group} section is missing")
        sections.append(match.group(0))
    return sections


def main() -> None:
    required = (
        RETAINED / "index.html",
        RETAINED / "reference.json",
        SPLIT / "index.html",
        SPLIT / "reference.json",
        SPLIT / "browser-results.json",
    )
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    retained_reference = read_json(RETAINED / "reference.json")
    split_reference = read_json(SPLIT / "reference.json")
    split_browser = read_json(SPLIT / "browser-results.json")
    retained_html = (RETAINED / "index.html").read_text()
    split_html = (SPLIT / "index.html").read_text()

    sections = hot_group_sections(retained_html)
    retained_hot_candidates = sum(
        candidate_count(section, "mixed-hot-candidate") for section in sections
    )
    split_candidates = candidate_count(split_html, "candidate")
    retained_glyph_counts = [
        count
        for section in sections
        for count in candidate_glyph_counts(section, "mixed-hot-candidate")
    ]
    split_glyph_counts = candidate_glyph_counts(split_html, "candidate")

    if retained_reference["hotGroups"] != list(HOT_GROUPS):
        raise RuntimeError("retained topology is no longer K=2")
    if retained_hot_candidates != len(HOT_GROUPS) * GROUP_SIZE:
        raise RuntimeError(
            f"expected 512 retained hot candidates, found {retained_hot_candidates}"
        )
    if split_candidates != GROUP_SIZE:
        raise RuntimeError(
            f"expected 256 candidates in one split scorer, found {split_candidates}"
        )
    if set(retained_glyph_counts) != {12}:
        raise RuntimeError("retained hot candidates no longer contain 12 glyphs each")
    # The split markup carries score/complement codepoint pairs for 12 faces,
    # plus the extra split complement.  The source reference's 13-position
    # metric counts the effective per-face glyph work after font routing.
    if set(split_glyph_counts) != {25}:
        raise RuntimeError("split candidates no longer contain 25 routed codepoints")
    if split_reference["glyphsPerCandidate"] != 13:
        raise RuntimeError("split scorer glyph geometry changed")
    if split_reference["baselineGsubGlyphsPerCandidate"] != 12:
        raise RuntimeError("source scorer glyph geometry changed")

    gate = split_browser["conservativeGate"]
    if (
        split_browser["maximumAbsoluteCandidateDelta"]
        != OBSERVED_GSUB_ERROR_BUCKETS
        or gate["winnerMarginThresholdBuckets"] != MARGIN_THRESHOLD_BUCKETS
        or gate["unsafeAccepts"] != 0
    ):
        raise RuntimeError("split scorer empirical certificate changed")

    # A CSS Grid max needs one element per candidate.  cv01 can select one group
    # per element tree, while the existing router needs both group maxima at the
    # same time.  Therefore the lower bound is two complete top grids.
    simultaneous_top_grids = len(HOT_GROUPS)
    minimum_top_candidates = simultaneous_top_grids * split_candidates
    upper_candidates_removed = retained_hot_candidates - minimum_top_candidates

    retained_glyphs_per_candidate = retained_glyph_counts[0]
    retained_upper_glyph_instances = (
        retained_hot_candidates * retained_glyphs_per_candidate
    )
    proposed_top_glyph_instances = (
        minimum_top_candidates * split_reference["glyphsPerCandidate"]
    )

    # Top-two certification cannot be obtained from the top grid alone.  It
    # needs a second Grid pass that masks the winner.  The best possible lazy
    # topology creates one runner only after a hot group is selected; an eager
    # upper-layer topology needs one runner for both simultaneous groups.
    lazy_runner_candidates_per_hot_visit = split_candidates
    eager_runner_candidates = len(HOT_GROUPS) * split_candidates
    lazy_runner_glyph_instances_per_hot_visit = (
        lazy_runner_candidates_per_hot_visit
        * split_reference["glyphsPerCandidate"]
    )
    eager_top_two_candidates = minimum_top_candidates + eager_runner_candidates
    eager_top_two_glyph_instances = (
        eager_top_two_candidates * split_reference["glyphsPerCandidate"]
    )

    conservative_upper_allowance = (
        EXISTING_BROWSER_ALLOWANCE_BUCKETS + OBSERVED_GSUB_ERROR_BUCKETS
    )
    fixture_comparisons = split_browser["comparisons"]
    fixture_accepts = [
        item
        for item in fixture_comparisons
        if item["gsubWinner"]["marginBuckets"] > MARGIN_THRESHOLD_BUCKETS
    ]
    fixture_fallbacks = [
        item
        for item in fixture_comparisons
        if item["gsubWinner"]["marginBuckets"] <= MARGIN_THRESHOLD_BUCKETS
    ]
    unsafe_accepts = [
        item
        for item in fixture_accepts
        if not item["winnerTokenMatches"]
    ]

    reasons = [
        "GSUB selects group-specific glyph rows but does not perform argmax; the maximum still requires 256 overlaid Grid candidates per group.",
        "The router needs groups 0 and 1 simultaneously, so cv01 feature selection cannot share one 256-candidate top grid between them.",
        "Two top grids require the same 512 candidate elements as retained K=2, so zero upper candidates are removed.",
        "A margin needs a winner-masked runner Grid: 256 additional candidates per selected hot visit, or 512 additional candidates if both runners are eager.",
        "Each split scorer candidate shapes 13 glyphs instead of the retained exact scorer's 12.",
    ]
    feasible = (
        upper_candidates_removed == retained_hot_candidates
        and proposed_top_glyph_instances <= retained_upper_glyph_instances
    )
    if feasible:
        raise RuntimeError("topology unexpectedly passed; add the browser builder first")

    report = {
        "experiment": "gpt2-gsub-inplace-hot2-upper",
        "decision": "reject-offline-topology",
        "browserGate": False,
        "browserLaunched": False,
        "browserArtifactBuilt": False,
        "sourceRetained": RETAINED.name,
        "sourceSplitGsub": SPLIT.name,
        "hotGroups": list(HOT_GROUPS),
        "groupSize": GROUP_SIZE,
        "topologyProof": {
            "gsubPerformsArgmax": False,
            "argmaxMechanism": "one CSS Grid element per candidate",
            "featureSelectionIsSingleValuedPerScorer": True,
            "simultaneousGroupMaximaRequiredByRouter": len(HOT_GROUPS),
            "splitCandidatesPerGrid": split_candidates,
            "retainedHotUpperCandidateElements": retained_hot_candidates,
            "minimumGsubTopCandidateElements": minimum_top_candidates,
            "upperCandidateElementsRemoved": upper_candidates_removed,
            "requestedUpperCandidateElementsRemoved": retained_hot_candidates,
            "removalShortfall": retained_hot_candidates - upper_candidates_removed,
            "sameTopAnchorCanCarryBucketAndWinner": True,
            "topAnchorAloneCanCarryRunnerMargin": False,
            "runnerGridRequiredForMargin": True,
        },
        "glyphWork": {
            "retainedGlyphsPerCandidate": retained_glyphs_per_candidate,
            "splitGlyphsPerCandidate": split_reference["glyphsPerCandidate"],
            "retainedMarkupCodepointsPerCandidate": retained_glyph_counts[0],
            "splitMarkupCodepointsPerCandidate": split_glyph_counts[0],
            "perCandidateIncrease": (
                split_reference["glyphsPerCandidate"]
                - retained_glyphs_per_candidate
            ),
            "perCandidateIncreasePercent": (
                split_reference["glyphsPerCandidate"]
                / retained_glyphs_per_candidate
                - 1
            ) * 100,
            "retainedHotUpperGlyphInstances": retained_upper_glyph_instances,
            "minimumGsubTopGlyphInstances": proposed_top_glyph_instances,
            "minimumTopIncrease": (
                proposed_top_glyph_instances - retained_upper_glyph_instances
            ),
            "minimumTopIncreasePercent": (
                proposed_top_glyph_instances / retained_upper_glyph_instances - 1
            ) * 100,
        },
        "lazyRunner": {
            "additionalCandidateElementsPerSelectedHotVisit": (
                lazy_runner_candidates_per_hot_visit
            ),
            "additionalGlyphInstancesPerSelectedHotVisit": (
                lazy_runner_glyph_instances_per_hot_visit
            ),
            "nearMarginExactFallbackCandidateElements": GROUP_SIZE,
            "note": "This is the least-DOM top-two variant, but it adds a second 256-way Grid evaluation to every selected hot visit before deciding whether exact fallback is needed.",
        },
        "eagerRunner": {
            "topAndRunnerCandidateElements": eager_top_two_candidates,
            "netCandidateElementsVsRetained": (
                eager_top_two_candidates - retained_hot_candidates
            ),
            "topAndRunnerGlyphInstances": eager_top_two_glyph_instances,
            "netGlyphInstancesVsRetained": (
                eager_top_two_glyph_instances - retained_upper_glyph_instances
            ),
            "increasePercentVsRetained": (
                eager_top_two_glyph_instances / retained_upper_glyph_instances - 1
            ) * 100,
        },
        "upperAllowance": {
            "existingBrowserAllowanceBuckets": EXISTING_BROWSER_ALLOWANCE_BUCKETS,
            "observedGsubMaximumErrorBuckets": OBSERVED_GSUB_ERROR_BUCKETS,
            "requiredWrapperAllowanceBuckets": conservative_upper_allowance,
            "scoreStridePx": split_reference["scoreStridePx"],
            "requiredWrapperAllowancePx": (
                conservative_upper_allowance * split_reference["scoreStridePx"]
            ),
            "empiricalChromeBoundOnly": True,
            "portableBoundProved": False,
        },
        "fixtureSemantics": {
            "comparisons": len(fixture_comparisons),
            "winnerMatches": split_browser["winnerTokenMatches"],
            "acceptedAtMarginGreaterThan4": len(fixture_accepts),
            "nearMarginFallbacks": len(fixture_fallbacks),
            "unsafeAccepts": len(unsafe_accepts),
            "maximumAbsoluteCandidateDeltaBuckets": (
                split_browser["maximumAbsoluteCandidateDelta"]
            ),
            "source": "existing split-complement Chrome fixture measurements",
        },
        "corpusSemantics": {
            "available": False,
            "reason": "No browser-realized split-GSUB candidate deltas exist for the 1,024-state corpus; the fixture ±2 bound is empirical and cannot be promoted to a portable corpus proof.",
        },
        "assets": {
            "splitGsubWoff2BytesAdded": split_reference["fontWoff2Bytes"],
            "retainedExactWoff2BytesStillRequiredForNonHotAndFallback": (
                retained_reference["assets"]["exactFontWoff2Bytes"]
            ),
            "splitBankReplacesExactBank": False,
        },
        "rejectionReasons": reasons,
        "browserGateReasons": [
            "The required 512-row removal is impossible: the lower-bound GSUB top layer still has 512 candidate elements.",
            "Even before the runner, split-GSUB glyph work rises from 12 to 13 glyphs per candidate.",
            "The requested offline gate therefore fails, so no HTML/browser topology or timing run is authorized.",
        ],
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    if (OUTPUT / "index.html").exists():
        raise RuntimeError("offline rejection must not retain a browser artifact")
    (OUTPUT / "reference.json").write_text(json.dumps(report, indent=2) + "\n")

    result = f"""# In-place GSUB hot-2 upper/fine feasibility

Decision: **reject offline topology; browser not launched**.

The requested 512-row removal is impossible with the production split-complement scorer. GSUB selects group-specific glyph rows, but it does not compute argmax: each group maximum still needs 256 overlaid CSS Grid candidates. Because the router needs groups 0 and 1 at the same time, two independently feature-selected top grids are required. Their lower bound is **512 candidate elements**, exactly the retained K=2 count, so **0/512 rows are removed**.

## Top-two cost

The top anchor can carry its score bucket and tie-coded winner through the existing router, but it cannot also reveal the runner-up margin. Certification needs a winner-masked second Grid pass.

- Lazy runner: +256 candidate elements and +{lazy_runner_glyph_instances_per_hot_visit:,} shaped glyph instances per selected hot visit, before any exact fallback.
- Eager runners for both simultaneous groups: 1,024 top-plus-runner candidates, **+512** versus retained K=2.
- A near-margin case still needs the 256-row exact fallback.

The split scorer uses 13 glyphs per candidate versus 12 for the retained exact rows. The unavoidable top layer therefore rises from {retained_upper_glyph_instances:,} to {proposed_top_glyph_instances:,} glyph instances (**+{proposed_top_glyph_instances - retained_upper_glyph_instances:,}, {report['glyphWork']['minimumTopIncreasePercent']:.1f}%**) before the runner. Eager top-two reaches {eager_top_two_glyph_instances:,}, **+{eager_top_two_glyph_instances - retained_upper_glyph_instances:,} ({report['eagerRunner']['increasePercentVsRetained']:.1f}%)**.

The 963,044-byte split bank is additive, not a substitute for the retained exact bank: non-hot groups and near-margin fallbacks still require the full exact fonts.

## Semantics and allowance

Existing Chrome fixture evidence remains favorable in isolation: {len(fixture_accepts)}/{len(fixture_comparisons)} group cases accept at GSUB margin >4, {len(fixture_fallbacks)} falls back, all {split_browser['winnerTokenMatches']} winners match, and there are {len(unsafe_accepts)} unsafe accepts. A routing wrapper would need **{conservative_upper_allowance} buckets ({report['upperAllowance']['requiredWrapperAllowancePx']:.0f}px)**: the existing 24-bucket browser allowance plus the observed ±2 GSUB candidate error.

No corpus claim is made. The ±2 error radius is an empirical Chrome/fixture observation, and no browser-realized split-GSUB deltas exist for the 1,024-state corpus.

## Gate outcome

The offline gate fails both requested scaling conditions: candidate rows are not removed and per-candidate glyph work increases. Consequently this probe emits only the feasibility report and reference; it does not emit `index.html`, does not launch Chrome, and does not run the two-fixture or full-ten screens.
"""
    (OUTPUT / "RESULTS.md").write_text(result)

    print(json.dumps({
        "decision": report["decision"],
        "browserGate": report["browserGate"],
        "upperCandidateElementsRemoved": upper_candidates_removed,
        "minimumGsubTopCandidateElements": minimum_top_candidates,
        "lazyRunnerCandidatesPerHotVisit": lazy_runner_candidates_per_hot_visit,
        "eagerTopTwoCandidateElements": eager_top_two_candidates,
        "retainedHotUpperGlyphInstances": retained_upper_glyph_instances,
        "minimumGsubTopGlyphInstances": proposed_top_glyph_instances,
    }, indent=2))


if __name__ == "__main__":
    main()
