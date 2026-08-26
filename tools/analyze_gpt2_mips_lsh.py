#!/usr/bin/env python3
"""Screen asymmetric random-hyperplane LSH for the frozen GPT-2 output head.

The index uses the standard one-coordinate MIPS lift

    w' = [w, sqrt(M^2 - ||w||^2)]
    q' = [q, 0]

and independent Gaussian random-hyperplane tables.  No model value is trained or
changed.  Candidate recall is measured against a fresh brute-force multiplication
over all unchanged tied embedding/lm-head rows.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-mips-lsh"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
VOCABULARY = 50_257
TABLE_COUNTS = (4, 8, 16, 32)
BITS_PER_TABLE = (8, 10, 12, 14)
PROBE_RADII = (0, 1)
MAX_TABLES = max(TABLE_COUNTS)
MAX_BITS = max(BITS_PER_TABLE)
RANDOM_SEED = 20_260_914
ORACLE_BATCH = 32
SPLITS = ("train", "validation", "test")


def percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q, method="higher"))


def sha256_array(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).view(np.uint8)).hexdigest()


def distribution(values: np.ndarray) -> dict[str, object]:
    return {
        "mean": float(np.mean(values)),
        "p95": percentile(values, 95),
        "maximum": int(np.max(values)),
        "minimum": int(np.min(values)),
    }


def brute_force_oracle(
    hidden: np.ndarray, weights: np.ndarray, saved_winners: np.ndarray
) -> tuple[np.ndarray, dict[str, object]]:
    winners = np.empty(len(hidden), dtype=np.int64)
    winner_scores = np.empty(len(hidden), dtype=np.float32)
    runner_up_scores = np.empty(len(hidden), dtype=np.float32)
    for start in range(0, len(hidden), ORACLE_BATCH):
        stop = min(start + ORACLE_BATCH, len(hidden))
        scores = hidden[start:stop] @ weights.T
        winners[start:stop] = np.argmax(scores, axis=1)
        rows = np.arange(stop - start)
        winner_scores[start:stop] = scores[rows, winners[start:stop]]
        runner_up_scores[start:stop] = np.partition(scores, -2, axis=1)[:, -2]
    matches = winners == saved_winners
    if not np.all(matches):
        first = int(np.flatnonzero(~matches)[0])
        raise RuntimeError(
            f"brute-force winner mismatch at state {first}: "
            f"fresh={int(winners[first])}, saved={int(saved_winners[first])}"
        )
    return winners, {
        "method": "batched float32 hidden @ unchanged float32 wte.weight.T",
        "savedWinnerMatches": int(np.sum(matches)),
        "savedWinnerFraction": float(np.mean(matches)),
        "minimumTop1Margin": float(np.min(winner_scores - runner_up_scores)),
        "winnerSha256": sha256_array(winners),
    }


def make_hash_codes(
    hidden: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    row_squared_norms = np.sum(weights * weights, axis=1, dtype=np.float64)
    maximum_squared_norm = float(np.max(row_squared_norms))
    maximum_norm = float(np.sqrt(maximum_squared_norm))
    lift_tail = np.sqrt(
        np.maximum(maximum_squared_norm - row_squared_norms, 0.0)
    ).astype(np.float32)

    rng = np.random.default_rng(RANDOM_SEED)
    planes = rng.standard_normal(
        (MAX_TABLES, MAX_BITS, weights.shape[1] + 1), dtype=np.float32
    )
    # Plane normalization is immaterial to signs, but makes the artifact's rows
    # well-scaled and easier to transport as fixed projection vectors.
    planes /= np.linalg.norm(planes, axis=2, keepdims=True)
    item_codes = np.zeros((MAX_TABLES, len(weights)), dtype=np.uint16)
    query_codes = np.zeros((MAX_TABLES, len(hidden)), dtype=np.uint16)
    powers = (np.uint16(1) << np.arange(MAX_BITS, dtype=np.uint16))[:, None]
    for table in range(MAX_TABLES):
        item_projection = (
            weights @ planes[table, :, :-1].T
            + lift_tail[:, None] * planes[table, :, -1][None, :]
        )
        query_projection = hidden @ planes[table, :, :-1].T
        item_codes[table] = np.sum(
            (item_projection.T >= 0).astype(np.uint16) * powers, axis=0
        )
        query_codes[table] = np.sum(
            (query_projection.T >= 0).astype(np.uint16) * powers, axis=0
        )
        if (table + 1) % 4 == 0:
            print(f"hashed {table + 1}/{MAX_TABLES} tables", flush=True)

    lifted_squared_norms = row_squared_norms + lift_tail.astype(np.float64) ** 2
    lift = {
        "formula": "w'=[w,sqrt(M^2-||w||^2)], q'=[q,0]",
        "M": maximum_norm,
        "minimumOriginalRowNorm": float(np.sqrt(np.min(row_squared_norms))),
        "maximumOriginalRowNorm": maximum_norm,
        "maximumLiftedNormAbsoluteError": float(
            np.max(np.abs(np.sqrt(lifted_squared_norms) - maximum_norm))
        ),
        "tailMinimum": float(np.min(lift_tail)),
        "tailMaximum": float(np.max(lift_tail)),
    }
    return planes, item_codes, query_codes, lift


def prefixes(codes: np.ndarray, bits: int) -> np.ndarray:
    return codes & np.uint16((1 << bits) - 1)


def build_buckets(
    item_codes: np.ndarray, bits: int
) -> tuple[list[list[np.ndarray]], np.ndarray, np.ndarray]:
    bucket_count = 1 << bits
    tables: list[list[np.ndarray]] = []
    sizes = np.zeros((MAX_TABLES, bucket_count), dtype=np.int32)
    maxima = np.zeros(MAX_TABLES, dtype=np.int32)
    token_ids = np.arange(item_codes.shape[1], dtype=np.int32)
    for table in range(MAX_TABLES):
        code = prefixes(item_codes[table], bits).astype(np.int32)
        order = np.argsort(code, kind="stable")
        counts = np.bincount(code, minlength=bucket_count).astype(np.int32)
        offsets = np.concatenate(([0], np.cumsum(counts, dtype=np.int64)))
        members = token_ids[order]
        table_buckets = [
            members[offsets[bucket] : offsets[bucket + 1]]
            for bucket in range(bucket_count)
        ]
        tables.append(table_buckets)
        sizes[table] = counts
        maxima[table] = int(np.max(counts))
    return tables, sizes, maxima


def selected_signatures(signature: int, bits: int, radius: int) -> Iterable[int]:
    yield signature
    if radius == 1:
        for bit in range(bits):
            yield signature ^ (1 << bit)


def summarize_split(
    ids: np.ndarray,
    winners: np.ndarray,
    included: np.ndarray,
    unique_candidates: np.ndarray,
    bucket_entries: np.ndarray,
    empty_buckets: np.ndarray,
    any_empty: np.ndarray,
    all_empty: np.ndarray,
    projection_rows: int,
    fixed_candidate_slots: int,
) -> dict[str, object]:
    lower = unique_candidates[ids] + projection_rows
    duplicate_work = bucket_entries[ids] + projection_rows
    return {
        "samples": int(len(ids)),
        "exactTop1Included": int(np.sum(included[ids])),
        "exactTop1Recall": float(np.mean(included[ids])),
        "uniqueUnionCandidates": distribution(unique_candidates[ids]),
        "selectedBucketEntriesWithDuplicates": distribution(bucket_entries[ids]),
        "runtimeRowsUniqueUnionLowerBound": distribution(lower),
        "runtimeRowsWithDuplicates": distribution(duplicate_work),
        "fixedSlotRuntimeRows": int(projection_rows + fixed_candidate_slots),
        "emptyBucketBehavior": {
            "meanSelectedEmptyBuckets": float(np.mean(empty_buckets[ids])),
            "p95SelectedEmptyBuckets": percentile(empty_buckets[ids], 95),
            "maximumSelectedEmptyBuckets": int(np.max(empty_buckets[ids])),
            "queriesWithAnyEmptyBucket": int(np.sum(any_empty[ids])),
            "queriesWithAnyEmptyBucketFraction": float(np.mean(any_empty[ids])),
            "queriesWithNoCandidateEntries": int(np.sum(all_empty[ids])),
            "queriesWithNoCandidateEntriesFraction": float(np.mean(all_empty[ids])),
        },
    }


def evaluate_bits_radius(
    bits: int,
    radius: int,
    buckets: list[list[np.ndarray]],
    bucket_sizes: np.ndarray,
    table_maxima: np.ndarray,
    query_codes: np.ndarray,
    item_codes: np.ndarray,
    winners: np.ndarray,
    split_ids: dict[str, np.ndarray],
) -> list[dict[str, object]]:
    sample_count = query_codes.shape[1]
    unique_at = {tables: np.empty(sample_count, dtype=np.int32) for tables in TABLE_COUNTS}
    entries_at = {tables: np.empty(sample_count, dtype=np.int32) for tables in TABLE_COUNTS}
    empty_at = {tables: np.empty(sample_count, dtype=np.int16) for tables in TABLE_COUNTS}
    any_empty_at = {tables: np.empty(sample_count, dtype=np.bool_) for tables in TABLE_COUNTS}
    all_empty_at = {tables: np.empty(sample_count, dtype=np.bool_) for tables in TABLE_COUNTS}
    included_at = {tables: np.empty(sample_count, dtype=np.bool_) for tables in TABLE_COUNTS}
    marker = np.zeros(VOCABULARY, dtype=np.bool_)
    query_prefixes = prefixes(query_codes, bits).astype(np.int32)
    item_prefixes = prefixes(item_codes, bits).astype(np.int32)

    for query in range(sample_count):
        marker.fill(False)
        unique_count = 0
        entry_count = 0
        empty_count = 0
        winner_found = False
        for table in range(MAX_TABLES):
            signature = int(query_prefixes[table, query])
            for selected in selected_signatures(signature, bits, radius):
                members = buckets[table][selected]
                size = int(bucket_sizes[table, selected])
                entry_count += size
                empty_count += size == 0
                if size:
                    new = ~marker[members]
                    unique_count += int(np.sum(new))
                    marker[members] = True
            if not winner_found:
                distance = signature ^ int(item_prefixes[table, winners[query]])
                winner_found = distance.bit_count() <= radius
            tables = table + 1
            if tables in TABLE_COUNTS:
                unique_at[tables][query] = unique_count
                entries_at[tables][query] = entry_count
                empty_at[tables][query] = empty_count
                any_empty_at[tables][query] = empty_count > 0
                all_empty_at[tables][query] = entry_count == 0
                included_at[tables][query] = winner_found

    rows = []
    probes_per_table = 1 + (bits if radius == 1 else 0)
    for tables in TABLE_COUNTS:
        projection_rows = tables * bits
        maxima = table_maxima[:tables]
        fixed_candidate_slots = probes_per_table * int(np.sum(maxima))
        configuration_id = f"T{tables}-b{bits}-r{radius}"
        rows.append({
            "configurationId": configuration_id,
            "tables": tables,
            "bitsPerTable": bits,
            "hammingRadius": radius,
            "bucketsProbedPerTable": probes_per_table,
            "hashProjectionRows": projection_rows,
            "bucketPopulation": {
                "bucketCountPerTable": 1 << bits,
                "occupiedBuckets": int(np.sum(bucket_sizes[:tables] > 0)),
                "emptyBuckets": int(np.sum(bucket_sizes[:tables] == 0)),
                "emptyBucketFraction": float(np.mean(bucket_sizes[:tables] == 0)),
                "maximumByTable": maxima.astype(int).tolist(),
                "maximumAcrossTables": int(np.max(maxima)),
                "meanMaximumByTable": float(np.mean(maxima)),
            },
            "fixedSlotAccounting": {
                "policy": (
                    "each selected bucket reserves its table-wide maximum bucket size"
                ),
                "candidateSlots": fixed_candidate_slots,
                "runtimeRowsIncludingHashProjections": int(
                    fixed_candidate_slots + projection_rows
                ),
            },
            "splits": {
                name: summarize_split(
                    ids,
                    winners,
                    included_at[tables],
                    unique_at[tables],
                    entries_at[tables],
                    empty_at[tables],
                    any_empty_at[tables],
                    all_empty_at[tables],
                    projection_rows,
                    fixed_candidate_slots,
                )
                for name, ids in split_ids.items()
            },
        })
    return rows


def selection_key(row: dict[str, object]) -> tuple[object, ...]:
    validation = row["splits"]["validation"]
    return (
        validation["exactTop1Recall"],
        -validation["runtimeRowsWithDuplicates"]["mean"],
        -row["fixedSlotAccounting"]["runtimeRowsIncludingHashProjections"],
        -row["hammingRadius"],
        -row["tables"],
        -row["bitsPerTable"],
    )


def select_configuration(
    rows: list[dict[str, object]], gate: str
) -> dict[str, object] | None:
    if gate == "mean-duplicate-2000":
        eligible = [
            row for row in rows
            if row["splits"]["validation"]["runtimeRowsWithDuplicates"]["mean"]
            <= 2_000
        ]
    elif gate == "observed-max-duplicate-2048":
        eligible = [
            row for row in rows
            if row["splits"]["validation"]["runtimeRowsWithDuplicates"]["maximum"]
            <= 2_048
        ]
    elif gate == "fixed-slot-2048":
        eligible = [
            row for row in rows
            if row["fixedSlotAccounting"]["runtimeRowsIncludingHashProjections"]
            <= 2_048
        ]
    else:
        raise ValueError(gate)
    return max(eligible, key=selection_key) if eligible else None


def compact_selected(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "configurationId": row["configurationId"],
        "tables": row["tables"],
        "bitsPerTable": row["bitsPerTable"],
        "hammingRadius": row["hammingRadius"],
        "bucketsProbedPerTable": row["bucketsProbedPerTable"],
        "hashProjectionRows": row["hashProjectionRows"],
        "fixedSlotAccounting": row["fixedSlotAccounting"],
        "splits": row["splits"],
    }


def pareto_frontier(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            row["splits"]["validation"]["runtimeRowsWithDuplicates"]["mean"],
            -row["splits"]["validation"]["exactTop1Recall"],
        ),
    )
    frontier = []
    best_recall = -1.0
    for row in ordered:
        recall = row["splits"]["validation"]["exactTop1Recall"]
        if recall > best_recall:
            frontier.append(compact_selected(row))
            best_recall = recall
    return frontier


def create_index_artifact(
    selected: dict[str, object],
    planes: np.ndarray,
    item_codes: np.ndarray,
) -> dict[str, object]:
    tables = int(selected["tables"])
    bits = int(selected["bitsPerTable"])
    codes = prefixes(item_codes[:tables], bits).astype(np.uint16)
    bucket_count = 1 << bits
    sorted_token_ids = np.empty((tables, VOCABULARY), dtype=np.int32)
    offsets = np.empty((tables, bucket_count + 1), dtype=np.int32)
    for table in range(tables):
        order = np.argsort(codes[table], kind="stable")
        sorted_token_ids[table] = order.astype(np.int32)
        counts = np.bincount(codes[table], minlength=bucket_count)
        offsets[table, 0] = 0
        offsets[table, 1:] = np.cumsum(counts, dtype=np.int32)
    path = OUTPUT / "index.npz"
    np.savez_compressed(
        path,
        planes=planes[:tables, :bits],
        token_hashes=codes,
        sorted_token_ids=sorted_token_ids,
        bucket_offsets=offsets,
        random_seed=np.asarray(RANDOM_SEED, dtype=np.int64),
        tables=np.asarray(tables, dtype=np.int32),
        bits_per_table=np.asarray(bits, dtype=np.int32),
        hamming_radius=np.asarray(selected["hammingRadius"], dtype=np.int32),
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "configurationId": selected["configurationId"],
        "contents": [
            "float32 random hyperplanes",
            "uint16 token hash signatures",
            "int32 bucket-sorted unchanged token IDs",
            "int32 bucket offsets",
        ],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }


def validate_index_artifact(
    artifact: dict[str, object], selected: dict[str, object]
) -> dict[str, object]:
    path = ROOT / str(artifact["path"])
    saved = np.load(path)
    tables = int(selected["tables"])
    bits = int(selected["bitsPerTable"])
    expected_ids = np.arange(VOCABULARY, dtype=np.int32)
    if saved["planes"].shape != (tables, bits, 769):
        raise RuntimeError("index plane shape mismatch")
    if saved["token_hashes"].shape != (tables, VOCABULARY):
        raise RuntimeError("index token hash shape mismatch")
    if saved["bucket_offsets"].shape != (tables, (1 << bits) + 1):
        raise RuntimeError("index bucket offset shape mismatch")
    for table in range(tables):
        ids = saved["sorted_token_ids"][table]
        offsets = saved["bucket_offsets"][table]
        if not np.array_equal(np.sort(ids), expected_ids):
            raise RuntimeError(f"index table {table} is not a token-ID permutation")
        if offsets[0] != 0 or offsets[-1] != VOCABULARY or np.any(np.diff(offsets) < 0):
            raise RuntimeError(f"invalid bucket offsets in index table {table}")
        if np.any(np.diff(saved["token_hashes"][table, ids].astype(np.int32)) < 0):
            raise RuntimeError(f"bucket members are not hash-sorted in table {table}")
    if int(saved["hamming_radius"]) != int(selected["hammingRadius"]):
        raise RuntimeError("index Hamming-radius metadata mismatch")
    return {
        "passed": True,
        "tablesChecked": tables,
        "tokensPerTableChecked": VOCABULARY,
        "checks": [
            "array shapes",
            "token-ID permutation per table",
            "monotone complete bucket offsets",
            "hash-sorted bucket membership",
            "Hamming-radius metadata",
        ],
    }


def markdown_distribution(values: dict[str, object]) -> str:
    return f'{values["mean"]:.1f}/{values["p95"]:.0f}/{values["maximum"]}'


def write_results_markdown(result: dict[str, object]) -> None:
    mean_selected = result["selection"]["selectedByValidationMeanDuplicate2000"]
    max_selected = result["selection"]["selectedByValidationObservedMaxDuplicate2048"]
    fixed_selected = result["selection"]["selectedByValidationFixedSlot2048"]
    verdict = result["verdict"]
    status = "GO" if verdict["go"] else "NO-GO"
    widest = max(
        result["configurations"],
        key=lambda row: (
            row["splits"]["validation"]["exactTop1Recall"],
            -row["splits"]["validation"]["runtimeRowsWithDuplicates"]["mean"],
        ),
    )
    widest_test = widest["splits"]["test"]
    mean_test = mean_selected["splits"]["test"]

    selected_rows = []
    for label, point in (
        ("mean duplicate rows <=2,000", mean_selected),
        ("observed duplicate max <=2,048", max_selected),
        ("fixed-slot padded rows <=2,048", fixed_selected),
    ):
        if point is None:
            selected_rows.append(f"| {label} | none eligible | | | | | |")
            continue
        test = point["splits"]["test"]
        selected_rows.append(
            f'| {label} | {point["configurationId"]} | '
            f'{point["splits"]["validation"]["exactTop1Recall"]:.2%} | '
            f'{test["exactTop1Recall"]:.2%} | '
            f'{markdown_distribution(test["uniqueUnionCandidates"])} | '
            f'{markdown_distribution(test["selectedBucketEntriesWithDuplicates"])} | '
            f'{point["fixedSlotAccounting"]["runtimeRowsIncludingHashProjections"]:,} |'
        )

    frontier_rows = []
    for point in result["validationParetoFrontier"]:
        validation = point["splits"]["validation"]
        test = point["splits"]["test"]
        frontier_rows.append(
            f'| {point["configurationId"]} | '
            f'{validation["exactTop1Recall"]:.2%} | '
            f'{test["exactTop1Recall"]:.2%} | '
            f'{markdown_distribution(test["uniqueUnionCandidates"])} | '
            f'{markdown_distribution(test["selectedBucketEntriesWithDuplicates"])} | '
            f'{markdown_distribution(test["runtimeRowsWithDuplicates"])} | '
            f'{point["fixedSlotAccounting"]["runtimeRowsIncludingHashProjections"]:,} |'
        )

    text = f"""# GPT-2 asymmetric MIPS LSH candidate screen

**Verdict: {status}.** {verdict["reason"]}

This offline screen uses the standard asymmetric norm lift followed by seeded
Gaussian random-hyperplane hashing. GPT-2-small, its architecture, and all
50,257 tied `wte`/`lm_head` rows remain unchanged. The input is the existing
1,024-state corpus with its established 512 train / 256 validation / 256
untouched-test split. LSH itself is unsupervised and query-independent; every
reported operating point was selected using validation only.

## Validation-selected operating points

Costs are shown as mean/p95/max over the untouched test split. The unique union
is an optimistic lower bound. The deployment gate uses selected bucket entries
with duplicates retained, plus all `T*b` hash-projection rows. The stricter
fixed-slot estimate pads every selected bucket in a table to that table's
largest indexed bucket.

| Validation gate | Configuration | Validation recall | Test recall | Unique candidates | Duplicate entries | Fixed-slot rows incl. projections |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(selected_rows)}

The mean-budget choice reaches only **{mean_test["exactTop1Recall"]:.2%} test
recall** at {mean_test["runtimeRowsWithDuplicates"]["mean"]:.1f} mean
duplicate-aware rows; its p95/max are
{mean_test["runtimeRowsWithDuplicates"]["p95"]:.0f}/
{mean_test["runtimeRowsWithDuplicates"]["maximum"]}. The highest-validation-recall
point anywhere in the sweep is `{widest["configurationId"]}`. It reaches
{widest["splits"]["validation"]["exactTop1Recall"]:.2%} validation and
{widest_test["exactTop1Recall"]:.2%} test recall, but costs
{widest_test["runtimeRowsWithDuplicates"]["mean"]:.1f} mean duplicate-aware rows
and {widest["fixedSlotAccounting"]["runtimeRowsIncludingHashProjections"]:,}
fixed-slot rows. More work therefore does not rescue this family to 99%.

## Validation Pareto frontier

| Configuration | Validation recall | Test recall | Test unique candidates | Test duplicate entries | Test duplicate runtime rows | Fixed-slot rows |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(frontier_rows)}

`Tn-bm-r0` means `n` tables, `m` bits/table, and exact-bucket lookup. `r1`
adds all Hamming-distance-one buckets. Full per-split mean/p95/max counts,
empty-bucket behavior, per-table maximum bucket sizes, and all 32 swept points
are in `results.json`.

## Accounting and interpretation

For each query, the candidate generator takes the union only to measure the
best possible deduplicated lower bound. Strict CSS cannot cheaply form that
arbitrary union, so feasibility is judged on the sum of actual bucket lengths
including cross-table duplicates. Runtime work adds the unique `T*b` projection
rows needed to compute the hashes. Fixed-slot work is still more conservative:
for each configuration, every selected bucket uses the measured maximum
population of its own table as its capacity. Radius-one multiprobe selects
`1+b` such slots per table. The direct positive-tail lift produces severely
imbalanced buckets, which is why no tested configuration fits a 2,048-row
fixed-slot layout even when its typical queried buckets are small.

Candidate recall means that the fresh brute-force top-1 token is present in the
bucket union. Exact rescoring of unchanged rows would therefore recover that
same winner whenever inclusion succeeds. No approximate score is called exact.

## Oracle and determinism

The brute-force float32 oracle matches all
{result["oracle"]["savedWinnerMatches"]:,}/1,024 saved winners. Random planes
come from NumPy `default_rng` seed {RANDOM_SEED}; table and bit sweeps use nested
prefixes so every comparison is deterministic. The selected index artifact is
`{result["indexArtifact"]["path"]}` (SHA-256
`{result["indexArtifact"]["sha256"]}`). It contains projection planes and
bucket membership by unchanged token ID, not copied or modified model rows.

## Reproduce and validate

```sh
python3 tools/analyze_gpt2_mips_lsh.py
python3 -m py_compile tools/analyze_gpt2_mips_lsh.py
python3 -m json.tool experiments/gpt2-mips-lsh/results.json >/dev/null
```
"""
    (OUTPUT / "RESULTS.md").write_text(text)


def main() -> None:
    if not STATES.exists():
        raise RuntimeError(
            "missing 1,024-state corpus; run the supervised group-router analysis first"
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    saved = np.load(STATES)
    hidden = saved["hidden"].astype(np.float32)
    saved_winners = saved["dense_winners"].astype(np.int64)
    split_ids = {
        name: saved[f"{name}_ids"].astype(np.int64) for name in SPLITS
    }
    if len(hidden) != 1_024 or [len(split_ids[name]) for name in SPLITS] != [512, 256, 256]:
        raise RuntimeError("unexpected corpus or split size")

    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(tensors.tensor("wte.weight")[:VOCABULARY], dtype=np.float32)
    if weights.shape != (VOCABULARY, hidden.shape[1]):
        raise RuntimeError(f"unexpected wte shape {weights.shape}")
    winners, oracle = brute_force_oracle(hidden, weights, saved_winners)
    print("brute-force oracle verified all 1,024 winners", flush=True)
    planes, item_codes, query_codes, lift = make_hash_codes(hidden, weights)

    configurations: list[dict[str, object]] = []
    for bits in BITS_PER_TABLE:
        print(f"building b={bits} buckets", flush=True)
        buckets, bucket_sizes, table_maxima = build_buckets(item_codes, bits)
        for radius in PROBE_RADII:
            print(f"evaluating b={bits} radius={radius}", flush=True)
            configurations.extend(evaluate_bits_radius(
                bits,
                radius,
                buckets,
                bucket_sizes,
                table_maxima,
                query_codes,
                item_codes,
                winners,
                split_ids,
            ))

    mean_selected = select_configuration(configurations, "mean-duplicate-2000")
    max_selected = select_configuration(configurations, "observed-max-duplicate-2048")
    fixed_selected = select_configuration(configurations, "fixed-slot-2048")
    if mean_selected is None:
        raise RuntimeError("sweep unexpectedly has no mean-budget configuration")
    index_artifact = create_index_artifact(mean_selected, planes, item_codes)
    index_validation = validate_index_artifact(index_artifact, mean_selected)

    mean_test = mean_selected["splits"]["test"]
    mean_go = (
        mean_test["exactTop1Recall"] >= 0.99
        and mean_test["runtimeRowsWithDuplicates"]["mean"] <= 2_000
    )
    fixed_go = fixed_selected is not None and (
        fixed_selected["splits"]["test"]["exactTop1Recall"] >= 0.99
        and fixed_selected["fixedSlotAccounting"]["runtimeRowsIncludingHashProjections"]
        <= 2_048
    )
    if mean_go:
        reason = (
            "The validation-selected duplicate-aware mean-budget point reaches "
            "at least 99% untouched-test recall under 2,000 mean runtime rows."
        )
    else:
        reason = (
            "No validation-selected point reaches at least 99% untouched-test "
            "recall while staying under 2,000 mean duplicate-aware runtime rows."
        )
    if fixed_go:
        reason += " A fixed-slot padded point also meets the 2,048-row cap."
    else:
        reason += " No validation-selected fixed-slot padded point also meets 99%."

    result: dict[str, object] = {
        "schemaVersion": 1,
        "model": "openai-community/gpt2",
        "modelPath": str(MODEL_PATH.relative_to(ROOT)),
        "weights": {
            "tensor": "wte.weight (tied lm_head)",
            "rows": VOCABULARY,
            "dimensions": int(weights.shape[1]),
            "dtype": str(weights.dtype),
            "unchanged": True,
            "sha256": sha256_array(weights),
        },
        "corpus": {
            "path": str(STATES.relative_to(ROOT)),
            "samples": len(hidden),
            "splitSamples": {name: int(len(ids)) for name, ids in split_ids.items()},
            "hiddenSha256": sha256_array(hidden),
            "testUsedForSelection": False,
        },
        "method": {
            "name": "asymmetric-norm-lift random-hyperplane LSH",
            "lift": lift,
            "planeDistribution": "independent standard Gaussian, L2-normalized",
            "randomSeed": RANDOM_SEED,
            "planesSha256": sha256_array(planes),
            "tables": list(TABLE_COUNTS),
            "bitsPerTable": list(BITS_PER_TABLE),
            "hammingRadii": list(PROBE_RADII),
            "nestedPrefixes": True,
        },
        "accounting": {
            "uniqueUnionCandidates": "distinct token IDs in all selected buckets",
            "selectedBucketEntriesWithDuplicates": (
                "sum of bucket populations; duplicates across tables are retained"
            ),
            "runtimeRowsWithDuplicates": (
                "selected bucket entries with duplicates plus T*b hash projections"
            ),
            "fixedSlotRuntimeRows": (
                "T*b plus selected buckets padded to each table's maximum bucket size"
            ),
            "cssGateUsesUniqueUnion": False,
        },
        "oracle": oracle,
        "selection": {
            "rule": (
                "validation recall descending, then validation mean duplicate-aware "
                "runtime rows ascending, then fixed-slot rows ascending; test is hidden"
            ),
            "selectedByValidationMeanDuplicate2000": compact_selected(mean_selected),
            "selectedByValidationObservedMaxDuplicate2048": compact_selected(max_selected),
            "selectedByValidationFixedSlot2048": compact_selected(fixed_selected),
        },
        "validationParetoFrontier": pareto_frontier(configurations),
        "configurations": configurations,
        "indexArtifact": index_artifact,
        "validation": {
            "fullSweepCompleted": True,
            "configurationCount": len(configurations),
            "expectedConfigurationCount": (
                len(TABLE_COUNTS) * len(BITS_PER_TABLE) * len(PROBE_RADII)
            ),
            "bruteForceWinnerAssertionPassed": True,
            "indexArtifact": index_validation,
        },
        "verdict": {
            "go": bool(mean_go),
            "fixedSlotGo": bool(fixed_go),
            "targetTestRecall": 0.99,
            "meanDuplicateRuntimeRowBudget": 2_000,
            "preferredFixedSlotRowCap": 2_048,
            "reason": reason,
        },
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    write_results_markdown(result)
    print(json.dumps({
        "verdict": result["verdict"],
        "selection": result["selection"],
        "indexArtifact": result["indexArtifact"],
        "results": str((OUTPUT / "results.json").relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
