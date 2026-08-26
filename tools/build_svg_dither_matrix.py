#!/usr/bin/env python3
"""Build a no-JS RGB-dithered two-matrix GPT-2 transport probe."""

from __future__ import annotations

import json
import itertools
from pathlib import Path

import numpy as np
from PIL import Image

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-dither-matrix"
CENTER = 128 / 255
WIDTH = 64
DITHER_NORMALIZED = np.asarray([-1 / 3, 0, 1 / 3]) / 255
PERMUTATIONS = np.asarray(list(itertools.permutations(DITHER_NORMALIZED)))
CYCLIC_PERMUTATIONS = np.asarray([0, 3, 4])


def save_rgb(path: Path, values: np.ndarray) -> None:
    rgba = np.zeros((*values.shape[:2], 4), dtype=np.uint8)
    rgba[..., :3] = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def save_mask(path: Path, values: np.ndarray) -> None:
    rgba = np.zeros((1, len(values), 4), dtype=np.uint8)
    rgba[..., :3] = np.where(values[None, :, None], 255, 0).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def redither_matrix(offsets: np.ndarray) -> str:
    rows: list[float] = []
    for offset in offsets:
        rows.extend((1 / 3, 1 / 3, 1 / 3, 0, float(offset)))
    rows.extend((0, 0, 0, 1, 0))
    return " ".join(f"{value:.12g}" for value in rows)


def matrix_stage(
    source: str,
    weights: np.ndarray,
    bias: np.ndarray,
    input_range: float,
    output_range: float,
    prefix: str,
    offsets: np.ndarray,
    output_permutations: np.ndarray | None = None,
) -> tuple[list[str], str]:
    primitives = [
        f'<feTile in="{source}" x="0" y="0" width="{WIDTH}" height="1" '
        f'result="{prefix}-input"/>'
    ]
    outputs = []
    ratio = input_range / output_range
    for output, row in enumerate(weights):
        kernel = row[::-1] * ratio
        kernel_text = " ".join(f"{value:.12g}" for value in kernel)
        intercept = (
            CENTER
            - CENTER * ratio * float(np.sum(row))
            + float(bias[output]) / (2 * output_range)
        )
        reduced = f"{prefix}-reduced-{output}"
        placed = f"{prefix}-placed-{output}"
        primitives.extend(
            (
                f'<feConvolveMatrix in="{prefix}-input" order="{WIDTH} 1" '
                f'kernelMatrix="{kernel_text}" divisor="1" bias="{intercept:.12g}" '
                f'targetX="{WIDTH - 1}" targetY="0" edgeMode="none" '
                f'preserveAlpha="true" x="{WIDTH - 1}" y="0" width="1" '
                f'height="1" result="{reduced}"/>',
                f'<feOffset in="{reduced}" dx="{output - (WIDTH - 1)}" '
                f'x="{output}" y="0" width="1" height="1" result="{placed}"/>',
            )
        )
        outputs.append(placed)
    merged = f"{prefix}-merged"
    primitives.append(
        f'<feMerge result="{merged}">'
        + "".join(f'<feMergeNode in="{output}"/>' for output in outputs)
        + "</feMerge>"
    )
    result = f"{prefix}-out"
    if output_permutations is None:
        primitives.append(
            f'<feColorMatrix in="{merged}" values="{redither_matrix(offsets)}" '
            f'result="{result}"/>'
        )
    else:
        parts = []
        for permutation_index, permutation in enumerate(PERMUTATIONS):
            mask = output_permutations == permutation_index
            if not np.any(mask):
                continue
            mask_name = f"{prefix}-permutation-{permutation_index}.png"
            save_mask(OUT / mask_name, mask)
            mapped = f"{prefix}-permutation-{permutation_index}-mapped"
            part = f"{prefix}-permutation-{permutation_index}-part"
            primitives.extend(
                (
                    f'<feColorMatrix in="{merged}" '
                    f'values="{redither_matrix(permutation)}" result="{mapped}"/>',
                    f'<feImage href="{mask_name}" x="0" y="0" width="{WIDTH}" '
                    f'height="1" result="{prefix}-permutation-{permutation_index}-mask"/>',
                    f'<feComposite in="{mapped}" '
                    f'in2="{prefix}-permutation-{permutation_index}-mask" '
                    f'operator="arithmetic" k1="1" k2="0" k3="0" k4="0" '
                    f'result="{part}"/>',
                )
            )
            parts.append(part)
        combined = parts[0]
        for index, part in enumerate(parts[1:], 1):
            group_sum = result if index == len(parts) - 1 else f"{prefix}-group-sum-{index}"
            primitives.append(
                f'<feComposite in="{combined}" in2="{part}" '
                f'operator="arithmetic" k1="0" k2="1" k3="1" k4="0" '
                f'result="{group_sum}"/>'
            )
            combined = group_sum
    return primitives, result


def page(
    title: str,
    input_name: str,
    weights: tuple[np.ndarray, np.ndarray],
    biases: tuple[np.ndarray, np.ndarray],
    ranges: tuple[float, float, float],
    offsets: np.ndarray,
    output_permutations: tuple[np.ndarray | None, np.ndarray | None] = (None, None),
) -> str:
    stage1, source1 = matrix_stage(
        "input", weights[0], biases[0], ranges[0], ranges[1], "m1", offsets,
        output_permutations[0],
    )
    stage2, source2 = matrix_stage(
        source1, weights[1], biases[1], ranges[1], ranges[2], "m2", offsets,
        output_permutations[1],
    )
    return f'''<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>html,body{{margin:0;background:#000}}svg{{display:block;image-rendering:pixelated}}</style>
<svg width="{WIDTH}" height="1" viewBox="0 0 {WIDTH} 1" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="probe" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
 x="0" y="0" width="{WIDTH}" height="1" color-interpolation-filters="sRGB">
<feImage href="{input_name}" x="0" y="0" width="{WIDTH}" height="1" result="input"/>
{''.join(stage1)}{''.join(stage2)}
<feOffset in="{source2}" x="0" y="0" width="{WIDTH}" height="1"/>
</filter></defs><rect width="{WIDTH}" height="1" fill="white" filter="url(#probe)"/></svg>'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads(
        (
            ROOT
            / "experiments/gpt2-block-css/view-timeline-attention-2token-reference.json"
        ).read_text()
    )
    tensors = SafeTensors(MODEL_PATH)
    vector = np.asarray(reference["context"], dtype=np.float64)[1, :WIDTH]
    matrices = []
    biases = []
    for block in (0, 1):
        matrices.append(
            np.asarray(
                tensors.tensor(f"h.{block}.attn.c_proj.weight"), dtype=np.float64
            )[:WIDTH, :WIDTH].T
        )
        biases.append(
            np.asarray(
                tensors.tensor(f"h.{block}.attn.c_proj.bias"), dtype=np.float64
            )[:WIDTH]
        )
    expected1 = matrices[0] @ vector + biases[0]
    expected2 = matrices[1] @ expected1 + biases[1]
    ranges = (
        max(float(np.max(np.abs(vector))) * 1.08, 1e-9),
        max(float(np.max(np.abs(expected1))) * 1.08, 1e-9),
        max(float(np.max(np.abs(expected2))) * 1.08, 1e-9),
    )
    rng = np.random.default_rng(20260912)

    def choose_permutations(weights: np.ndarray, ratio: float) -> np.ndarray:
        target_span = 2 / (3 * 255)
        best_score = -np.inf
        best = None
        for _ in range(4096):
            ids = rng.choice(CYCLIC_PERMUTATIONS, WIDTH)
            deviations = ratio * weights @ PERMUTATIONS[ids]
            spans = np.ptp(deviations, axis=1)
            relative = np.maximum(spans / target_span, 1e-9)
            score = -float(np.mean(np.log(relative) ** 2))
            if score > best_score:
                best_score = score
                best = ids
        assert best is not None
        return best

    input_permutations = choose_permutations(matrices[0], ranges[0] / ranges[1])
    intermediate_permutations = choose_permutations(
        matrices[1], ranges[1] / ranges[2]
    )
    final_permutations = rng.choice(CYCLIC_PERMUTATIONS, WIDTH)
    common = CENTER + vector / (2 * ranges[0])
    ordinary = np.repeat(common[:, None], 3, axis=1)
    dithered = common[:, None] + DITHER_NORMALIZED[None, :]
    distributed = common[:, None] + PERMUTATIONS[input_permutations]
    save_rgb(OUT / "ordinary.png", ordinary.reshape(1, WIDTH, 3))
    save_rgb(OUT / "dithered.png", dithered.reshape(1, WIDTH, 3))
    save_rgb(OUT / "distributed.png", distributed.reshape(1, WIDTH, 3))

    ordinary_html = page(
        "Ordinary two-matrix transport",
        "ordinary.png",
        tuple(matrices),
        tuple(biases),
        ranges,
        np.zeros(3),
    )
    dithered_html = page(
        "RGB-dithered two-matrix transport",
        "dithered.png",
        tuple(matrices),
        tuple(biases),
        ranges,
        DITHER_NORMALIZED,
    )
    distributed_html = page(
        "Distributed RGB-dithered two-matrix transport",
        "distributed.png",
        tuple(matrices),
        tuple(biases),
        ranges,
        DITHER_NORMALIZED,
        (intermediate_permutations, None),
    )
    (OUT / "ordinary.html").write_text(ordinary_html)
    (OUT / "dithered.html").write_text(dithered_html)
    (OUT / "distributed.html").write_text(distributed_html)
    (OUT / "distributed-stage1.html").write_text(
        distributed_html.replace(
            '<feOffset in="m2-out" x="0" y="0" width="64" height="1"/>',
            '<feOffset in="m1-out" x="0" y="0" width="64" height="1"/>',
        )
    )
    (OUT / "distributed-stage2-merged.html").write_text(
        distributed_html.replace(
            '<feOffset in="m2-out" x="0" y="0" width="64" height="1"/>',
            '<feOffset in="m2-merged" x="0" y="0" width="64" height="1"/>',
        )
    )
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "center": CENTER,
                "width": WIDTH,
                "ranges": ranges,
                "expected1": expected1.tolist(),
                "expected2": expected2.tolist(),
                "ordinary_html_bytes": len(ordinary_html.encode()),
                "dithered_html_bytes": len(dithered_html.encode()),
                "distributed_html_bytes": len(distributed_html.encode()),
                "input_permutations": input_permutations.tolist(),
                "intermediate_permutations": intermediate_permutations.tolist(),
                "final_permutations": final_permutations.tolist(),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "output": str(OUT),
            "ordinary_html_bytes": len(ordinary_html.encode()),
            "dithered_html_bytes": len(dithered_html.encode()),
            "distributed_html_bytes": len(distributed_html.encode()),
        }
    )


if __name__ == "__main__":
    main()
