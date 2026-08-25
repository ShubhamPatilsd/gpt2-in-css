#!/usr/bin/env python3
"""Compile an exact lazy clustered TinyStories output head to CSS."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output-head-benchmark" / "generated"
CLUSTERS = 256
WINNER_TOLERANCE = 0.0001
FEEDBACK_BITS = 8
FEEDBACK_COORDINATES_PER_PACK = 3
WIDE_FEEDBACK_COORDINATES_PER_PACK = 6
COMPACT_FEEDBACK_BITS = 6
COMPACT_FEEDBACK_COORDINATES_PER_PACK = 4
TOKEN_SCORE_PACK_BASE = 65536
TOKEN_SCORE_CLUSTER_BASE = 256
TOKEN_SCORE_PAYLOAD_BASE = TOKEN_SCORE_PACK_BASE * TOKEN_SCORE_CLUSTER_BASE
TOKEN_SCORE_PACK_SCALE = 1_000_000
TOKEN_SCORE_PACK_OFFSET = 64
TOKEN_SCORE_TIE_MAX = 50_256
TOKEN_SCORE_INACTIVE = -9_007_199_254_740_991
ROW_SCORE_BITS = 8
ROW_SCORE_SAFER_BITS = 10


def import_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = import_module(
    "output_head_builder", ROOT / "tools" / "build_output_head_benchmark.py"
)
SEARCH = import_module(
    "output_head_search", ROOT / "tools" / "analyze_output_head_search.py"
)


def number(value: float) -> str:
    return BUILDER.css_number(float(value))


def registration(name: str, syntax: str = "<number>") -> str:
    return (
        f'@property --{name}{{syntax:"{syntax}";inherits:false;initial-value:0}}'
    )


def reduce_registered(
    registrations: list[str], declarations: list[str], names: list[str], prefix: str
) -> str:
    level = names
    depth = 0
    while len(level) > 1:
        next_level = []
        for group_index, start in enumerate(range(0, len(level), 32)):
            group = level[start : start + 32]
            if len(group) == 1:
                next_level.append(group[0])
                continue
            name = f"{prefix}{depth}x{group_index}"
            registrations.append(registration(name))
            declarations.append(
                f"--{name}:max({','.join(f'var(--{item})' for item in group)});"
            )
            next_level.append(name)
        level = next_level
        depth += 1
    return level[0]


def cluster_function(
    cluster: int, indices: np.ndarray, embeddings: np.ndarray
) -> str:
    arguments = ",".join(
        f"--x{dimension} <number>" for dimension in range(embeddings.shape[1])
    )
    declarations = []
    level = []
    for local, token in enumerate(indices):
        name = f"l{local}"
        level.append(name)
        terms = [
            f"var(--x{dimension})*{number(embeddings[token, dimension])}"
            for dimension in range(embeddings.shape[1])
        ]
        declarations.append(f"--{name}:calc({' + '.join(terms)});")
    depth = 0
    while len(level) > 1:
        next_level = []
        for group_index, start in enumerate(range(0, len(level), 32)):
            group = level[start : start + 32]
            if len(group) == 1:
                next_level.append(group[0])
                continue
            name = f"m{depth}x{group_index}"
            declarations.append(
                f"--{name}:max({','.join(f'var(--{item})' for item in group)});"
            )
            next_level.append(name)
        level = next_level
        depth += 1
    return "\n".join(
        [
            f"@function --c{cluster}({arguments}) returns <number>{{",
            *declarations,
            f"result:var(--{level[0]});",
            "}",
        ]
    )


def cluster_token_function(
    cluster: int, indices: np.ndarray, embeddings: np.ndarray
) -> str:
    arguments = ",".join(
        f"--x{dimension} <number>" for dimension in range(embeddings.shape[1])
    )
    declarations = []
    level = []
    for local, token in enumerate(indices):
        products = [
            f"var(--x{dimension})*{number(embeddings[token, dimension])}"
            for dimension in range(embeddings.shape[1])
        ]
        logit = f"l{local}"
        term = f"t{local}"
        tolerance = number(WINNER_TOLERANCE)
        declarations.append(f"--{logit}:calc({' + '.join(products)});")
        declarations.append(
            f"--{term}:calc((1 - max(0,sign("
            f"abs(var(--{logit}) - var(--target)) - {tolerance}"
            f")))*{int(token)});"
        )
        level.append(term)
    depth = 0
    while len(level) > 1:
        next_level = []
        for group_index, start in enumerate(range(0, len(level), 32)):
            group = level[start : start + 32]
            if len(group) == 1:
                next_level.append(group[0])
                continue
            name = f"s{depth}x{group_index}"
            declarations.append(
                f"--{name}:calc({' + '.join(f'var(--{item})' for item in group)});"
            )
            next_level.append(name)
        level = next_level
        depth += 1
    return "\n".join(
        [
            f"@function --t{cluster}({arguments},--target <number>) returns <number>{{",
            *declarations,
            f"result:var(--{level[0]});",
            "}",
        ]
    )


def cluster_embedding_function(
    cluster: int,
    dimension: int,
    indices: np.ndarray,
    embeddings: np.ndarray,
) -> str:
    cases = ";".join(
        f"style(--winner-id:{int(token)}):{number(embeddings[token, dimension])}"
        for token in indices
    )
    return "\n".join(
        [
            f"@function --e{cluster}x{dimension}() returns <number>{{",
            f"result:if({cases};else:0);",
            "}",
        ]
    )


def packed_embedding_function(
    cluster: int,
    pack: int,
    indices: np.ndarray,
    packed_embeddings: np.ndarray,
    typed_return: bool = True,
) -> str:
    cases = ";".join(
        f"style(--winner-id:{int(token)}):{int(packed_embeddings[token, pack])}"
        for token in indices
    )
    return "\n".join(
        [
            f"@function --pe{cluster}x{pack}()"
            f"{' returns <number>' if typed_return else ''}{{",
            f"result:if({cases};else:0);",
            "}",
        ]
    )


def quantize_and_pack_embeddings(
    embeddings: np.ndarray,
    coordinates_per_pack: int = FEEDBACK_COORDINATES_PER_PACK,
    feedback_bits: int = FEEDBACK_BITS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    maximum_code = 2 ** (feedback_bits - 1) - 1
    scales = np.max(np.abs(embeddings), axis=0) / maximum_code
    signed = np.rint(embeddings / scales).clip(-maximum_code, maximum_code)
    signed = signed.astype(np.int64)
    unsigned = signed + maximum_code
    packs = (
        embeddings.shape[1] + coordinates_per_pack - 1
    ) // coordinates_per_pack
    packed = np.zeros((embeddings.shape[0], packs), dtype=np.int64)
    base = 2**feedback_bits
    for dimension in range(embeddings.shape[1]):
        pack = dimension // coordinates_per_pack
        offset = dimension % coordinates_per_pack
        packed[:, pack] += unsigned[:, dimension] * (base**offset)
    reconstructed = signed.astype(np.float64) * scales
    return packed, scales, reconstructed


def shared_token_function(token: int, embedding: np.ndarray) -> str:
    terms = [
        f"var(--h{dimension})*{number(weight)}"
        for dimension, weight in enumerate(embedding)
    ]
    return "\n".join(
        [
            f"@function --d{token}() returns <number>{{",
            f"result:calc({' + '.join(terms)});",
            "}",
        ]
    )


def quantize_token_rows(
    embeddings: np.ndarray, bits: int = ROW_SCORE_BITS
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    maximum_code = 2 ** (bits - 1) - 1
    scales = np.max(np.abs(embeddings), axis=1) / maximum_code
    codes = np.rint(embeddings / scales[:, None]).clip(
        -maximum_code, maximum_code
    )
    codes = codes.astype(np.int64)
    reconstructed = codes.astype(np.float64) * scales[:, None]
    return codes, scales, reconstructed


def shared_row_quantized_token_function(
    token: int, codes: np.ndarray, scale: float
) -> str:
    terms = [
        f"var(--h{dimension})*{int(code)}"
        for dimension, code in enumerate(codes)
    ]
    return "\n".join(
        [
            f"@function --d{token}() returns <number>{{",
            f"result:calc(({' + '.join(terms)})*{number(scale)});",
            "}",
        ]
    )


def shared_cluster_function(cluster: int, indices: np.ndarray) -> str:
    declarations = []
    level = []
    for local, token in enumerate(indices):
        name = f"l{local}"
        declarations.append(f"--{name}:--d{int(token)}();")
        level.append(name)
    depth = 0
    while len(level) > 1:
        next_level = []
        for group_index, start in enumerate(range(0, len(level), 32)):
            group = level[start : start + 32]
            if len(group) == 1:
                next_level.append(group[0])
                continue
            name = f"m{depth}x{group_index}"
            declarations.append(
                f"--{name}:max({','.join(f'var(--{item})' for item in group)});"
            )
            next_level.append(name)
        level = next_level
        depth += 1
    return "\n".join(
        [
            f"@function --dc{cluster}() returns <number>{{",
            *declarations,
            f"result:var(--{level[0]});",
            "}",
        ]
    )


def shared_packed_cluster_function(cluster: int, indices: np.ndarray) -> str:
    """Return a maximum carrying both a quantized score and its token ID."""
    declarations = []
    level = []
    for local, token in enumerate(indices):
        name = f"l{local}"
        payload = (
            (TOKEN_SCORE_TIE_MAX - int(token)) * TOKEN_SCORE_CLUSTER_BASE
            + cluster
        )
        declarations.append(
            f"--{name}:calc(round(nearest,calc((--d{int(token)}() + "
            f"{TOKEN_SCORE_PACK_OFFSET})*{TOKEN_SCORE_PACK_SCALE}),1)*"
            f"{TOKEN_SCORE_PAYLOAD_BASE} + {payload});"
        )
        level.append(name)
    depth = 0
    while len(level) > 1:
        next_level = []
        for group_index, start in enumerate(range(0, len(level), 32)):
            group = level[start : start + 32]
            if len(group) == 1:
                next_level.append(group[0])
                continue
            name = f"m{depth}x{group_index}"
            declarations.append(
                f"--{name}:max({','.join(f'var(--{item})' for item in group)});"
            )
            next_level.append(name)
        level = next_level
        depth += 1
    return "\n".join(
        [
            f"@function --pc{cluster}(){{",
            *declarations,
            f"result:var(--{level[0]});",
            "}",
        ]
    )


def packed_global_max_function() -> str:
    """Lazily reduce active packed clusters without a typed large-number hop."""
    declarations = []
    level = []
    for cluster in range(CLUSTERS):
        name = f"l{cluster}"
        declarations.append(
            f"--{name}:if(style(--a{cluster}:1):--pc{cluster}();"
            f"else:{TOKEN_SCORE_INACTIVE});"
        )
        level.append(name)
    depth = 0
    while len(level) > 1:
        next_level = []
        for group_index, start in enumerate(range(0, len(level), 32)):
            group = level[start : start + 32]
            if len(group) == 1:
                next_level.append(group[0])
                continue
            name = f"m{depth}x{group_index}"
            declarations.append(
                f"--{name}:max({','.join(f'var(--{item})' for item in group)});"
            )
            next_level.append(name)
        level = next_level
        depth += 1
    return "\n".join(
        [
            "@function --packed-global-max(){",
            *declarations,
            f"result:var(--{level[0]});",
            "}",
        ]
    )


def shared_cluster_token_function(cluster: int, indices: np.ndarray) -> str:
    declarations = []
    level = []
    tolerance = number(WINNER_TOLERANCE)
    for local, token in enumerate(indices):
        logit = f"l{local}"
        term = f"t{local}"
        declarations.append(f"--{logit}:--d{int(token)}();")
        declarations.append(
            f"--{term}:calc((1 - max(0,sign("
            f"abs(var(--{logit}) - var(--target)) - {tolerance}"
            f")))*{int(token)});"
        )
        level.append(term)
    depth = 0
    while len(level) > 1:
        next_level = []
        for group_index, start in enumerate(range(0, len(level), 32)):
            group = level[start : start + 32]
            if len(group) == 1:
                next_level.append(group[0])
                continue
            name = f"s{depth}x{group_index}"
            declarations.append(
                f"--{name}:calc({' + '.join(f'var(--{item})' for item in group)});"
            )
            next_level.append(name)
        level = next_level
        depth += 1
    return "\n".join(
        [
            f"@function --dt{cluster}(--target <number>) returns <number>{{",
            *declarations,
            f"result:var(--{level[0]});",
            "}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--packed-candidates-only",
        action="store_true",
        help="write only the packed feedback candidates and metadata",
    )
    args = parser.parse_args()
    write_full_benchmark = not args.packed_candidates_only
    OUT.mkdir(parents=True, exist_ok=True)
    state = BUILDER.load_torch_zip(BUILDER.download_checkpoint())
    embeddings = state["transformer.wte.weight"].astype(np.float64)
    tokenizer = BUILDER.BUILDER.Gpt2Tokenizer(
        ROOT / "data" / "tiny-gpt2" / "vocab.json",
        ROOT / "data" / "tiny-gpt2" / "merges.txt",
    )
    prompts = ["Once upon a time", "The little girl", "One day"]
    hidden_vectors = np.stack(
        [BUILDER.final_hidden(tokenizer.encode(prompt), state) for prompt in prompts]
    ).astype(np.float64)
    logits = hidden_vectors @ embeddings.T
    reference_maximums = logits.max(axis=1).tolist()
    reference_winners = logits.argmax(axis=1).astype(int).tolist()

    print("training exact cluster bounds...", flush=True)
    centers, radii, labels = SEARCH.train_kmeans(
        embeddings, CLUSTERS, 8, 20260824 + CLUSTERS
    )
    members = [np.flatnonzero(labels == cluster) for cluster in range(CLUSTERS)]
    sizes = np.asarray([len(indices) for indices in members])
    print(
        f"cluster sizes: min={sizes.min()} median={int(np.median(sizes))} "
        f"max={sizes.max()}",
        flush=True,
    )
    if sizes.max() > 1280:
        raise RuntimeError("cluster exceeds measured CSS @function expansion limit")

    invocation = ",".join(
        f"var(--h{dimension})" for dimension in range(embeddings.shape[1])
    )
    functions = [
        cluster_function(cluster, indices, embeddings)
        for cluster, indices in enumerate(members)
    ]
    registrations = [registration("hnorm")]
    declarations = [
        "--hnorm:sqrt(calc("
        + " + ".join(
            f"var(--h{dimension})*var(--h{dimension})"
            for dimension in range(embeddings.shape[1])
        )
        + "));"
    ]
    upper_names = []
    for cluster in range(CLUSTERS):
        name = f"u{cluster}"
        upper_names.append(name)
        registrations.append(registration(name))
        terms = [
            f"var(--h{dimension})*{number(centers[cluster, dimension])}"
            for dimension in range(embeddings.shape[1])
        ]
        terms.append(f"var(--hnorm)*{number(radii[cluster])}")
        declarations.append(f"--{name}:calc({' + '.join(terms)});")
    upper_maximum = reduce_registered(
        registrations, declarations, upper_names, "um"
    )

    seed_terms = []
    for cluster in range(CLUSTERS):
        difference = f"sd{cluster}"
        indicator = f"si{cluster}"
        term = f"st{cluster}"
        registrations.extend(
            [registration(difference), registration(indicator), registration(term)]
        )
        declarations.append(
            f"--{difference}:calc(abs(var(--u{cluster}) - var(--{upper_maximum})));"
        )
        declarations.append(
            f"--{indicator}:calc(1 - max(0,sign(var(--{difference}) - .000001)));"
        )
        declarations.append(f"--{term}:calc(var(--{indicator})*{cluster});")
        seed_terms.append(term)
    registrations.append(registration("seed", "<integer>"))
    seed_sum_terms = ",".join(f"var(--{term})" for term in seed_terms)
    declarations.append(f"--seed:calc({seed_sum_terms.replace(',', ' + ')});")

    seed_cases = ";".join(
        f"style(--seed:{cluster}):--c{cluster}({invocation})"
        for cluster in range(CLUSTERS)
    )
    registrations.append(registration("seed-best"))
    declarations.append(f"--seed-best:if({seed_cases};else:-999999);")

    result_names = []
    active_replacements = []
    for cluster in range(CLUSTERS):
        active = f"a{cluster}"
        result = f"z{cluster}"
        registrations.extend([registration(active, "<integer>"), registration(result)])
        active_declaration = (
            f"--{active}:calc(1 - max(0,sign((var(--seed-best) - var(--u{cluster})) - .000001)));"
        )
        declarations.append(active_declaration)
        active_replacements.append((active_declaration, f"--{active}:1;"))
        declarations.append(
            f"--{result}:if(style(--{active}:1):--c{cluster}({invocation});else:-999999);"
        )
        result_names.append(result)
    final_name = reduce_registered(
        registrations, declarations, result_names, "fm"
    )
    registrations.append(registration("maximum"))
    declarations.append(f"--maximum:var(--{final_name});")
    registrations.append(registration("active-count"))
    declarations.append(
        "--active-count:calc("
        + " + ".join(f"var(--a{cluster})" for cluster in range(CLUSTERS))
        + ");"
    )

    rules = [BUILDER.query_rules(hidden_vectors)]
    for start in range(0, len(declarations), 1000):
        rules.append(".model{" + "".join(declarations[start : start + 1000]) + "}")
    css = "\n".join(functions + registrations + rules) + "\n"
    css_path = OUT / "clustered-256.css"
    benchmark_query_rules = BUILDER.query_rules(hidden_vectors) + "\n"
    if write_full_benchmark:
        css_path.write_text(css)
        (OUT / "clustered-256-runtime.css").write_text(
            css.replace(benchmark_query_rules, "")
        )
    all_active_css = css
    for original, replacement in active_replacements:
        all_active_css = all_active_css.replace(original, replacement)
    if write_full_benchmark:
        (OUT / "clustered-256-all.css").write_text(all_active_css)

    token_functions = [
        cluster_token_function(cluster, indices, embeddings)
        for cluster, indices in enumerate(members)
    ]
    winner_registrations = registrations.copy()
    winner_declarations = declarations.copy()
    winner_cluster_terms = []
    for cluster in range(CLUSTERS):
        difference = f"wcd{cluster}"
        indicator = f"wci{cluster}"
        term = f"wct{cluster}"
        winner_registrations.extend(
            [registration(difference), registration(indicator), registration(term)]
        )
        winner_declarations.append(
            f"--{difference}:calc(abs(var(--z{cluster}) - var(--maximum)));"
        )
        winner_declarations.append(
            f"--{indicator}:calc(1 - max(0,sign(var(--{difference}) - .000001)));"
        )
        winner_declarations.append(
            f"--{term}:calc(var(--{indicator})*{cluster});"
        )
        winner_cluster_terms.append(term)
    winner_registrations.append(registration("winner-cluster", "<integer>"))
    winner_declarations.append(
        "--winner-cluster:calc("
        + " + ".join(f"var(--{term})" for term in winner_cluster_terms)
        + ");"
    )
    winner_cases = ";".join(
        f"style(--winner-cluster:{cluster}):--t{cluster}({invocation},var(--maximum))"
        for cluster in range(CLUSTERS)
    )
    winner_registrations.append(registration("winner-id", "<integer>"))
    winner_declarations.append(f"--winner-id:if({winner_cases};else:-1);")
    winner_rules = [BUILDER.query_rules(hidden_vectors)]
    for start in range(0, len(winner_declarations), 1000):
        winner_rules.append(
            ".model{" + "".join(winner_declarations[start : start + 1000]) + "}"
        )
    winner_css = "\n".join(
        functions + token_functions + winner_registrations + winner_rules
    ) + "\n"
    if write_full_benchmark:
        (OUT / "clustered-256-winner.css").write_text(winner_css)
        (OUT / "clustered-256-winner-runtime.css").write_text(
            winner_css.replace(benchmark_query_rules, "")
        )

    print("building exact 64-number embedding lookup...", flush=True)
    embedding_functions = [
        cluster_embedding_function(cluster, dimension, indices, embeddings)
        for dimension in range(embeddings.shape[1])
        for cluster, indices in enumerate(members)
    ]
    embedding_registrations = winner_registrations.copy()
    embedding_declarations = winner_declarations.copy()
    for dimension in range(embeddings.shape[1]):
        embedding_registrations.append(registration(f"next{dimension}"))
        cases = ";".join(
            f"style(--winner-cluster:{cluster}):--e{cluster}x{dimension}()"
            for cluster in range(CLUSTERS)
        )
        embedding_declarations.append(
            f"--next{dimension}:if({cases};else:0);"
        )
    embedding_rules = [BUILDER.query_rules(hidden_vectors)]
    for start in range(0, len(embedding_declarations), 1000):
        embedding_rules.append(
            ".model{" + "".join(embedding_declarations[start : start + 1000]) + "}"
        )
    embedding_css = "\n".join(
        functions
        + token_functions
        + embedding_functions
        + embedding_registrations
        + embedding_rules
    ) + "\n"
    if write_full_benchmark:
        (OUT / "clustered-256-embedding.css").write_text(embedding_css)
        (OUT / "clustered-256-embedding-runtime.css").write_text(
            embedding_css.replace(benchmark_query_rules, "")
        )

    print("building shared-dot output head...", flush=True)
    shared_dot_functions = [
        shared_token_function(token, embedding)
        for token, embedding in enumerate(embeddings)
    ]
    row_score_codes, row_score_scales, row_score_embeddings = quantize_token_rows(
        embeddings
    )
    row_score_dot_functions = [
        shared_row_quantized_token_function(
            token, row_score_codes[token], row_score_scales[token]
        )
        for token in range(len(embeddings))
    ]
    row_score_radii = np.asarray(
        [
            np.linalg.norm(
                row_score_embeddings[indices] - centers[cluster], axis=1
            ).max()
            for cluster, indices in enumerate(members)
        ]
    )
    (
        row10_score_codes,
        row10_score_scales,
        row10_score_embeddings,
    ) = quantize_token_rows(embeddings, ROW_SCORE_SAFER_BITS)
    row10_score_dot_functions = [
        shared_row_quantized_token_function(
            token, row10_score_codes[token], row10_score_scales[token]
        )
        for token in range(len(embeddings))
    ]
    row10_score_radii = np.asarray(
        [
            np.linalg.norm(
                row10_score_embeddings[indices] - centers[cluster], axis=1
            ).max()
            for cluster, indices in enumerate(members)
        ]
    )
    shared_max_functions = [
        shared_cluster_function(cluster, indices)
        for cluster, indices in enumerate(members)
    ]
    shared_token_functions = [
        shared_cluster_token_function(cluster, indices)
        for cluster, indices in enumerate(members)
    ]
    shared_declarations = embedding_declarations.copy()
    for cluster in range(CLUSTERS):
        score_call = f"--c{cluster}({invocation})"
        shared_declarations = [
            declaration.replace(score_call, f"--dc{cluster}()")
            for declaration in shared_declarations
        ]
        token_call = f"--t{cluster}({invocation},var(--maximum))"
        shared_declarations = [
            declaration.replace(token_call, f"--dt{cluster}(var(--maximum))")
            for declaration in shared_declarations
        ]
    shared_rules = []
    for start in range(0, len(shared_declarations), 1000):
        shared_rules.append(
            ".model{" + "".join(shared_declarations[start : start + 1000]) + "}"
        )
    shared_css = "\n".join(
        shared_dot_functions
        + shared_max_functions
        + shared_token_functions
        + embedding_functions
        + embedding_registrations
        + shared_rules
    ) + "\n"
    if write_full_benchmark:
        (OUT / "clustered-256-embedding-shared-runtime.css").write_text(shared_css)

    def build_packed_feedback(
        coordinates_per_pack: int,
        typed_intermediate: bool,
        feedback_bits: int = FEEDBACK_BITS,
    ) -> tuple[str, int, np.ndarray, dict[str, list[str]]]:
        packed_embeddings, feedback_scales, reconstructed_embeddings = (
            quantize_and_pack_embeddings(
                embeddings, coordinates_per_pack, feedback_bits
            )
        )
        feedback_packs = packed_embeddings.shape[1]
        packed_embedding_functions = [
            packed_embedding_function(
                cluster,
                pack,
                indices,
                packed_embeddings,
                typed_return=typed_intermediate,
            )
            for pack in range(feedback_packs)
            for cluster, indices in enumerate(members)
        ]
        packed_registrations = winner_registrations.copy()
        packed_declarations = winner_declarations.copy()
        for pack in range(feedback_packs):
            if typed_intermediate:
                packed_registrations.append(registration(f"feedback-pack-{pack}"))
            cases = ";".join(
                f"style(--winner-cluster:{cluster}):--pe{cluster}x{pack}()"
                for cluster in range(CLUSTERS)
            )
            packed_declarations.append(
                f"--feedback-pack-{pack}:if({cases};else:0);"
            )
        feedback_base = 2**feedback_bits
        feedback_offset = 2 ** (feedback_bits - 1) - 1
        for dimension in range(embeddings.shape[1]):
            packed_registrations.append(registration(f"next{dimension}"))
            pack = dimension // coordinates_per_pack
            offset = dimension % coordinates_per_pack
            divisor = feedback_base**offset
            code = (
                f"mod(round(down,calc(var(--feedback-pack-{pack})/{divisor}),1),"
                f"{feedback_base})"
            )
            packed_declarations.append(
                f"--next{dimension}:calc(({code} - {feedback_offset})*"
                f"{number(feedback_scales[dimension])});"
            )
        for cluster in range(CLUSTERS):
            score_call = f"--c{cluster}({invocation})"
            packed_declarations = [
                declaration.replace(score_call, f"--dc{cluster}()")
                for declaration in packed_declarations
            ]
            token_call = f"--t{cluster}({invocation},var(--maximum))"
            packed_declarations = [
                declaration.replace(token_call, f"--dt{cluster}(var(--maximum))")
                for declaration in packed_declarations
            ]
        packed_rules = [
            ".model{" + "".join(packed_declarations[start : start + 1000]) + "}"
            for start in range(0, len(packed_declarations), 1000)
        ]
        components = {
            "token_dot_functions": shared_dot_functions,
            "cluster_max_functions": shared_max_functions,
            "winner_recovery_functions": shared_token_functions,
            "feedback_lookup_functions": packed_embedding_functions,
            "registrations": packed_registrations,
            "runtime_rules": packed_rules,
        }
        css = "\n".join(
            item for group in components.values() for item in group
        ) + "\n"
        return css, feedback_packs, reconstructed_embeddings, components

    def build_score_packed_feedback() -> tuple[
        str, int, np.ndarray, dict[str, list[str]]
    ]:
        """Build the 8-bit feedback head without per-token winner recovery."""
        packed_embeddings, feedback_scales, reconstructed_embeddings = (
            quantize_and_pack_embeddings(
                embeddings, FEEDBACK_COORDINATES_PER_PACK, FEEDBACK_BITS
            )
        )
        feedback_packs = packed_embeddings.shape[1]
        packed_score_functions = [
            shared_packed_cluster_function(cluster, indices)
            for cluster, indices in enumerate(members)
        ]
        packed_embedding_functions = [
            packed_embedding_function(
                cluster,
                pack,
                indices,
                packed_embeddings,
                typed_return=True,
            )
            for pack in range(feedback_packs)
            for cluster, indices in enumerate(members)
        ]

        removed_names = set(result_names)
        removed_names.add("maximum")
        removed_names.update(
            line.split("--", 1)[1].split("{", 1)[0]
            for line in registrations
            if line.startswith("@property --fm")
        )
        score_registrations = [
            line
            for line in registrations
            if line.split("--", 1)[1].split("{", 1)[0] not in removed_names
        ]
        score_declarations = [
            line
            for line in declarations
            if line.removeprefix("--").split(":", 1)[0] not in removed_names
        ]
        for cluster in range(CLUSTERS):
            raw_call = f"--c{cluster}({invocation})"
            score_declarations = [
                declaration.replace(raw_call, f"--dc{cluster}()")
                for declaration in score_declarations
            ]

        score_declarations.append("--packed-maximum:--packed-global-max();")
        score_registrations.append(registration("winner-cluster", "<integer>"))
        score_declarations.append(
            f"--winner-cluster:calc(mod(var(--packed-maximum),"
            f"{TOKEN_SCORE_CLUSTER_BASE}));"
        )
        score_registrations.append(registration("winner-id", "<integer>"))
        score_declarations.append(
            f"--winner-id:calc({TOKEN_SCORE_TIE_MAX} - "
            f"round(down,calc(mod(var(--packed-maximum),"
            f"{TOKEN_SCORE_PAYLOAD_BASE})/{TOKEN_SCORE_CLUSTER_BASE}),1));"
        )

        for pack in range(feedback_packs):
            score_registrations.append(registration(f"feedback-pack-{pack}"))
            cases = ";".join(
                f"style(--winner-cluster:{cluster}):--pe{cluster}x{pack}()"
                for cluster in range(CLUSTERS)
            )
            score_declarations.append(
                f"--feedback-pack-{pack}:if({cases};else:0);"
            )
        feedback_base = 2**FEEDBACK_BITS
        feedback_offset = 2 ** (FEEDBACK_BITS - 1) - 1
        for dimension in range(embeddings.shape[1]):
            score_registrations.append(registration(f"next{dimension}"))
            pack = dimension // FEEDBACK_COORDINATES_PER_PACK
            offset = dimension % FEEDBACK_COORDINATES_PER_PACK
            divisor = feedback_base**offset
            code = (
                f"mod(round(down,calc(var(--feedback-pack-{pack})/{divisor}),1),"
                f"{feedback_base})"
            )
            score_declarations.append(
                f"--next{dimension}:calc(({code} - {feedback_offset})*"
                f"{number(feedback_scales[dimension])});"
            )

        score_rules = [
            ".model{" + "".join(score_declarations[start : start + 1000]) + "}"
            for start in range(0, len(score_declarations), 1000)
        ]
        components = {
            "token_dot_functions": shared_dot_functions,
            "raw_cluster_max_functions": shared_max_functions,
            "packed_cluster_max_functions": packed_score_functions,
            "packed_global_max_function": [packed_global_max_function()],
            "feedback_lookup_functions": packed_embedding_functions,
            "registrations": score_registrations,
            "runtime_rules": score_rules,
        }
        css = "\n".join(
            item for group in components.values() for item in group
        ) + "\n"
        return css, feedback_packs, reconstructed_embeddings, components

    print("building packed 8-bit embedding feedback...", flush=True)
    (
        packed_shared_css,
        feedback_packs,
        reconstructed_embeddings,
        packed_components,
    ) = (
        build_packed_feedback(FEEDBACK_COORDINATES_PER_PACK, True)
    )
    if write_full_benchmark or args.packed_candidates_only:
        (OUT / "clustered-256-embedding-packed8-shared-runtime.css").write_text(
            packed_shared_css
        )
    def build_row_score_css(
        dot_functions: list[str], candidate_radii: np.ndarray
    ) -> str:
        candidate = packed_shared_css.replace(
            "\n".join(shared_dot_functions), "\n".join(dot_functions), 1
        )
        for cluster in range(CLUSTERS):
            old_radius = f"var(--hnorm)*{number(radii[cluster])}"
            new_radius = (
                f"var(--hnorm)*{number(candidate_radii[cluster])}"
            )
            if candidate.count(old_radius) != 1:
                raise RuntimeError(
                    f"expected one radius declaration for cluster {cluster}"
                )
            candidate = candidate.replace(old_radius, new_radius, 1)
        return candidate

    row_score_packed_shared_css = build_row_score_css(
        row_score_dot_functions, row_score_radii
    )
    (
        OUT
        / "clustered-256-embedding-packed8-row-int8-shared-runtime.css"
    ).write_text(row_score_packed_shared_css)
    row10_score_packed_shared_css = build_row_score_css(
        row10_score_dot_functions, row10_score_radii
    )
    (
        OUT
        / "clustered-256-embedding-packed8-row-int10-shared-runtime.css"
    ).write_text(row10_score_packed_shared_css)
    print("building packed score/token winner recovery...", flush=True)
    (
        score_packed_shared_css,
        score_packed_feedback_packs,
        score_packed_reconstructed_embeddings,
        score_packed_components,
    ) = build_score_packed_feedback()
    (
        OUT
        / "clustered-256-embedding-packed8-score-token-shared-runtime.css"
    ).write_text(score_packed_shared_css)
    print("building untyped 48-bit packed feedback...", flush=True)
    (
        wide_packed_shared_css,
        wide_feedback_packs,
        wide_reconstructed_embeddings,
        _wide_components,
    ) = build_packed_feedback(WIDE_FEEDBACK_COORDINATES_PER_PACK, False)
    (
        OUT
        / "clustered-256-embedding-packed8x6-untyped-shared-runtime.css"
    ).write_text(wide_packed_shared_css)
    print("building typed 24-bit 6-bit packed feedback...", flush=True)
    (
        compact_packed_shared_css,
        compact_feedback_packs,
        compact_reconstructed_embeddings,
        _compact_components,
    ) = build_packed_feedback(
        COMPACT_FEEDBACK_COORDINATES_PER_PACK,
        True,
        COMPACT_FEEDBACK_BITS,
    )

    expected_active = []
    for query, reference in zip(hidden_vectors, reference_maximums):
        upper = centers @ query + radii * np.linalg.norm(query)
        seed = int(upper.argmax())
        seed_best = float((embeddings[members[seed]] @ query).max())
        expected_active.append(int((upper >= seed_best - 1e-6).sum()))

    h0 = float(hidden_vectors[0, 0])
    generated_hidden, _generations = SEARCH.generate_hidden_states(state, 24)
    seed_misses = []
    for query in generated_hidden:
        upper = centers @ query + radii * np.linalg.norm(query)
        seed = int(upper.argmax())
        winner = int((embeddings @ query).argmax())
        if labels[winner] != seed:
            seed_misses.append(query)
    if len(seed_misses) < 4:
        raise RuntimeError(f"only found {len(seed_misses)} seed-miss queries")
    benchmark_queries = [query.tolist() for query in seed_misses]
    perturbed_maximums = [
        float((embeddings @ np.asarray(query)).max()) for query in benchmark_queries
    ]
    perturbed_winners = [
        int((embeddings @ np.asarray(query)).argmax()) for query in benchmark_queries
    ]
    expected_embeddings = embeddings[reference_winners].tolist()
    perturbed_embeddings = embeddings[perturbed_winners].tolist()
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Exact clustered TinyStories output head</title>
  <link rel="stylesheet" href="clustered-256.css?v=clustered-2">
</head>
<body>
  <input type="radio" name="query" id="q0" checked>
  <input type="radio" name="query" id="q1">
  <input type="radio" name="query" id="q2">
  <main class="model"></main>
  <pre id="results">running...</pre>
  <script>
    const scriptStartMilliseconds = performance.now();
    const model = document.querySelector('.model');
    const inputs = [...document.querySelectorAll('input[name="query"]')];
    const expectedMaximums = {json.dumps(reference_maximums)};
    const expectedActive = {json.dumps(expected_active)};
    const benchmarkQueries = {json.dumps(benchmark_queries)};
    const perturbedMaximums = {json.dumps(perturbed_maximums)};
    const perturbedWinners = {json.dumps(perturbed_winners)};
    const expectedEmbeddings = {json.dumps(expected_embeddings)};
    const perturbedEmbeddings = {json.dumps(perturbed_embeddings)};
    const expectedWinners = {json.dumps(reference_winners)};
    const checkWinner = false;
    const checkEmbedding = false;
    const h0 = {h0!r};
    function readEmbedding(styles) {{
      if (!checkEmbedding) return null;
      return Array.from(
        {{length: {embeddings.shape[1]}}},
        (_, dimension) => Number.parseFloat(styles.getPropertyValue(`--next${{dimension}}`)),
      );
    }}
    function infer(query, perturbation = null) {{
      const started = performance.now();
      inputs[query].checked = true;
      if (perturbation === null) model.style.removeProperty('--h0');
      else model.style.setProperty('--h0', String(h0 + perturbation));
      const styles = getComputedStyle(model);
      const maximum = Number.parseFloat(styles.getPropertyValue('--maximum'));
      const active = Number.parseFloat(styles.getPropertyValue('--active-count'));
      const winner = Number.parseFloat(styles.getPropertyValue('--winner-id'));
      const embedding = readEmbedding(styles);
      return {{
        elapsed: performance.now() - started,
        maximum,
        active,
        winner,
        embedding,
      }};
    }}
    function inferVector(vector) {{
      const started = performance.now();
      inputs[0].checked = true;
      for (let dimension = 0; dimension < vector.length; dimension += 1) {{
        model.style.setProperty(`--h${{dimension}}`, String(vector[dimension]));
      }}
      const styles = getComputedStyle(model);
      const maximum = Number.parseFloat(styles.getPropertyValue('--maximum'));
      const winner = Number.parseFloat(styles.getPropertyValue('--winner-id'));
      const embedding = readEmbedding(styles);
      return {{
        elapsed: performance.now() - started,
        maximum,
        winner,
        embedding,
      }};
    }}
    requestAnimationFrame(() => requestAnimationFrame(() => {{
      let maximumError = 0;
      let activeError = 0;
      const correctnessMilliseconds = [];
      let wrongWinners = 0;
      let embeddingError = 0;
      for (let query = 0; query < inputs.length; query += 1) {{
        const result = infer(query);
        correctnessMilliseconds.push(result.elapsed);
        maximumError = Math.max(maximumError, Math.abs(result.maximum - expectedMaximums[query]));
        activeError = Math.max(activeError, Math.abs(result.active - expectedActive[query]));
        if (checkWinner && result.winner !== expectedWinners[query]) wrongWinners += 1;
        if (checkEmbedding) {{
          for (let dimension = 0; dimension < result.embedding.length; dimension += 1) {{
            embeddingError = Math.max(
              embeddingError,
              Math.abs(result.embedding[dimension] - expectedEmbeddings[query][dimension]),
            );
          }}
        }}
      }}
      inferVector(benchmarkQueries[0]);
      inferVector(benchmarkQueries[1]);
      const samples = [];
      const sampledMaximums = [];
      let perturbedMaximumError = 0;
      let perturbedWrongWinners = 0;
      let perturbedEmbeddingError = 0;
      const batchStarted = performance.now();
      for (let iteration = 0; iteration < benchmarkQueries.length; iteration += 1) {{
        const result = inferVector(benchmarkQueries[iteration]);
        samples.push(result.elapsed);
        sampledMaximums.push(result.maximum);
        perturbedMaximumError = Math.max(
          perturbedMaximumError,
          Math.abs(result.maximum - perturbedMaximums[iteration]),
        );
        if (checkWinner && result.winner !== perturbedWinners[iteration]) {{
          perturbedWrongWinners += 1;
        }}
        if (checkEmbedding) {{
          for (let dimension = 0; dimension < result.embedding.length; dimension += 1) {{
            perturbedEmbeddingError = Math.max(
              perturbedEmbeddingError,
              Math.abs(result.embedding[dimension] - perturbedEmbeddings[iteration][dimension]),
            );
          }}
        }}
      }}
      const batchMilliseconds = performance.now() - batchStarted;
      samples.sort((a, b) => a - b);
      const result = {{
        variant: 'clustered-functions',
        clusters: {CLUSTERS},
        sourceBytes: {len(css.encode())},
        scriptStartMilliseconds,
        samples,
        medianMilliseconds: samples[Math.floor(samples.length / 2)],
        batchMilliseconds,
        queryCount: benchmarkQueries.length,
        correctnessMilliseconds,
        maximumError,
        perturbedMaximumError,
        sampledMaximums,
        perturbedMaximums,
        wrongWinners,
        perturbedWrongWinners,
        embeddingError,
        perturbedEmbeddingError,
        activeError,
        expectedWinners: {json.dumps(reference_winners)},
        expectedActive,
        winnerTolerance: {WINNER_TOLERANCE},
        benchmarkCompleteMilliseconds: performance.now(),
      }};
      document.querySelector('#results').textContent = JSON.stringify(result, null, 2);
      document.documentElement.dataset.benchmarkComplete = 'true';
    }}));
  </script>
</body>
</html>
"""
    if write_full_benchmark:
        (OUT / "clustered-256.html").write_text(document)
    winner_document = document.replace(
        "clustered-256.css?v=clustered-2",
        "clustered-256-winner.css?v=clustered-winner-5",
    ).replace(
        "const checkWinner = false;",
        "const checkWinner = true;",
    ).replace(
        "variant: 'clustered-functions'",
        "variant: 'clustered-functions-winner'",
    ).replace(
        f"sourceBytes: {len(css.encode())}",
        f"sourceBytes: {len(winner_css.encode())}",
    )
    if write_full_benchmark:
        (OUT / "clustered-256-winner.html").write_text(winner_document)
    embedding_document = document.replace(
        "clustered-256.css?v=clustered-2",
        "clustered-256-embedding.css?v=clustered-embedding-4",
    ).replace(
        "const checkWinner = false;",
        "const checkWinner = true;",
    ).replace(
        "const checkEmbedding = false;",
        "const checkEmbedding = true;",
    ).replace(
        "variant: 'clustered-functions'",
        "variant: 'clustered-functions-embedding'",
    ).replace(
        f"sourceBytes: {len(css.encode())}",
        f"sourceBytes: {len(embedding_css.encode())}",
    )
    if write_full_benchmark:
        (OUT / "clustered-256-embedding.html").write_text(embedding_document)
    all_active_document = document.replace(
        "clustered-256.css?v=clustered-2",
        "clustered-256-all.css?v=clustered-all-1",
    ).replace(
        f"const expectedActive = {json.dumps(expected_active)};",
        f"const expectedActive = {json.dumps([CLUSTERS] * len(expected_active))};",
    )
    if write_full_benchmark:
        (OUT / "clustered-256-all.html").write_text(all_active_document)

    def component_bytes(components: dict[str, list[str]]) -> dict[str, int]:
        return {
            name: sum(len(item.encode()) + 1 for item in items)
            for name, items in components.items()
        }

    score_pack_reference_scores = generated_hidden @ embeddings.T
    score_pack_reference_winners = score_pack_reference_scores.argmax(axis=1)
    score_pack_codes = (
        np.rint(
            (score_pack_reference_scores + TOKEN_SCORE_PACK_OFFSET)
            * TOKEN_SCORE_PACK_SCALE
        ).astype(np.int64)
        * TOKEN_SCORE_PAYLOAD_BASE
        + (
            (
                TOKEN_SCORE_TIE_MAX
                - np.arange(embeddings.shape[0], dtype=np.int64)
            )
            * TOKEN_SCORE_CLUSTER_BASE
            + labels.astype(np.int64)
        )
    )
    score_pack_winners = score_pack_codes.argmax(axis=1)
    top_two = np.partition(score_pack_reference_scores, -2, axis=1)[:, -2:]
    score_pack_margins = top_two[:, 1] - top_two[:, 0]
    row_score_winners = (generated_hidden @ row_score_embeddings.T).argmax(axis=1)
    row10_score_winners = (
        generated_hidden @ row10_score_embeddings.T
    ).argmax(axis=1)
    metadata = {
        "clusters": CLUSTERS,
        "cluster_size": {
            "minimum": int(sizes.min()),
            "median": int(np.median(sizes)),
            "maximum": int(sizes.max()),
        },
        "reference_winners": reference_winners,
        "reference_maximums": reference_maximums,
        "expected_active": expected_active,
        "seed_miss_queries": len(seed_misses),
        "winner_tolerance": WINNER_TOLERANCE,
        "css_bytes": len(css.encode()),
        "winner_css_bytes": len(winner_css.encode()),
        "embedding_css_bytes": len(embedding_css.encode()),
        "shared_embedding_css_bytes": len(shared_css.encode()),
        "packed8_shared_embedding_css_bytes": len(packed_shared_css.encode()),
        "packed8_feedback_packs": int(feedback_packs),
        "packed8_maximum_embedding_error": float(
            np.max(np.abs(reconstructed_embeddings - embeddings))
        ),
        "packed8_component_bytes": component_bytes(packed_components),
        "row_int8_score_shared_embedding_css_bytes": len(
            row_score_packed_shared_css.encode()
        ),
        "row_int8_score_dot_function_bytes": sum(
            len(item.encode()) + 1 for item in row_score_dot_functions
        ),
        "row_int8_score_states": int(len(generated_hidden)),
        "row_int8_score_wrong_winners": int(
            np.sum(row_score_winners != score_pack_reference_winners)
        ),
        "row_int8_score_maximum_embedding_error": float(
            np.max(np.abs(row_score_embeddings - embeddings))
        ),
        "row_int8_score_mean_squared_embedding_error": float(
            np.mean((row_score_embeddings - embeddings) ** 2)
        ),
        "row_int10_score_shared_embedding_css_bytes": len(
            row10_score_packed_shared_css.encode()
        ),
        "row_int10_score_dot_function_bytes": sum(
            len(item.encode()) + 1 for item in row10_score_dot_functions
        ),
        "row_int10_score_states": int(len(generated_hidden)),
        "row_int10_score_wrong_winners": int(
            np.sum(row10_score_winners != score_pack_reference_winners)
        ),
        "row_int10_score_maximum_embedding_error": float(
            np.max(np.abs(row10_score_embeddings - embeddings))
        ),
        "row_int10_score_mean_squared_embedding_error": float(
            np.mean((row10_score_embeddings - embeddings) ** 2)
        ),
        "score_token_packed_shared_embedding_css_bytes": len(
            score_packed_shared_css.encode()
        ),
        "score_token_pack_base": TOKEN_SCORE_PACK_BASE,
        "score_token_cluster_base": TOKEN_SCORE_CLUSTER_BASE,
        "score_token_payload_base": TOKEN_SCORE_PAYLOAD_BASE,
        "score_token_pack_scale": TOKEN_SCORE_PACK_SCALE,
        "score_token_pack_offset": TOKEN_SCORE_PACK_OFFSET,
        "score_token_pack_states": int(len(generated_hidden)),
        "score_token_pack_wrong_winners": int(
            np.sum(score_pack_winners != score_pack_reference_winners)
        ),
        "score_token_pack_minimum_top_two_margin": float(
            score_pack_margins.min()
        ),
        "score_token_pack_maximum_absolute_code": int(
            np.max(np.abs(score_pack_codes))
        ),
        "score_token_pack_safe_integer": bool(
            np.max(np.abs(score_pack_codes)) < 2**53
        ),
        "score_token_packed_component_bytes": component_bytes(
            score_packed_components
        ),
        "score_token_packed_maximum_embedding_error": float(
            np.max(
                np.abs(score_packed_reconstructed_embeddings - embeddings)
            )
        ),
        "packed8x6_untyped_shared_embedding_css_bytes": len(
            wide_packed_shared_css.encode()
        ),
        "packed8x6_untyped_feedback_packs": int(wide_feedback_packs),
        "packed8x6_untyped_maximum_embedding_error": float(
            np.max(np.abs(wide_reconstructed_embeddings - embeddings))
        ),
        "packed6x4_shared_embedding_css_bytes": len(
            compact_packed_shared_css.encode()
        ),
        "packed6x4_feedback_packs": int(compact_feedback_packs),
        "packed6x4_maximum_embedding_error": float(
            np.max(np.abs(compact_reconstructed_embeddings - embeddings))
        ),
    }
    (OUT / "clustered-256.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
