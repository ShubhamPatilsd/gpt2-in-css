#!/usr/bin/env python3
"""Build direct-CSS arithmetic controls for the HVAR GPT-2 block."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

from build_gpt2_block_css import (
    EPSILON,
    MLP_WIDTH,
    QUANT_BITS,
    WIDTH,
    gelu_new,
    layer_norm,
    model_data,
)
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows
from build_matrix_backend_prototypes import ROOT


OUT = ROOT / "experiments" / "direct-css-block"
TOKEN_ID = 15496
BLOCK_CSS_SHARDS = 16


def base36(value: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, digit = divmod(value, 36)
        result = digits[digit] + result
    return result


def prop(prefix: str, index: int) -> str:
    return f"--{prefix}{base36(index)}"


def registrations(groups: tuple[tuple[str, int], ...]) -> str:
    names = ["--m1", "--v1", "--m2", "--v2"]
    for prefix, count in groups:
        names.extend(prop(prefix, index) for index in range(count))
    return "".join(
        f'@property {name}{{syntax:"<number>";inherits:true;initial-value:0}}'
        for name in names
    )


def dot(codes: np.ndarray, source: str) -> str:
    terms = []
    for index, value in enumerate(codes):
        coefficient = int(value)
        if coefficient == 0:
            continue
        variable = f"var({prop(source, index)})"
        if coefficient == 1:
            terms.append(variable)
        elif coefficient == -1:
            terms.append(f"(-1)*{variable}")
        elif coefficient < 0:
            terms.append(f"({coefficient})*{variable}")
        else:
            terms.append(f"{coefficient}*{variable}")
    return " + ".join(terms) if terms else "0"


def build_limit_probe() -> None:
    """Emit a tiny control that identifies Chromium's flat calc() term limit."""
    counts = (1, 8, 16, 32, 64, 96, 128, 192, 256, 384, 512, 768)
    css = [base_styles()]
    html = [
        '<!doctype html><meta charset="utf-8"><title>CSS calc limit probe</title>',
        '<link rel="stylesheet" href="limit-probe.css">',
    ]
    for count in counts:
        prefix = f"p{count}"
        for index in range(count):
            css.append(
                f'@property --{prefix}-x{index}{{syntax:"<number>";'
                "inherits:true;initial-value:0}"
            )
        css.append(
            f'@property --{prefix}-out{{syntax:"<number>";'
            "inherits:true;initial-value:-999}"
        )
        values = ";".join(f"--{prefix}-x{index}:1" for index in range(count))
        terms = " + ".join(
            (
                f"var(--{prefix}-x{index})"
                if index % 3
                else f"(-2)*var(--{prefix}-x{index})"
            )
            for index in range(count)
        )
        css.append(f".{prefix}{{{values};--{prefix}-out:calc({terms})}}")
        html.append(f'<div class="{prefix}" data-count="{count}"></div>')
        for mode, mode_terms in (
            (
                "add",
                " + ".join(f"var(--{prefix}-x{index})" for index in range(count)),
            ),
            (
                "mul",
                " + ".join(f"2*var(--{prefix}-x{index})" for index in range(count)),
            ),
        ):
            name = f"{prefix}-{mode}"
            css.append(
                f'@property --{name}-out{{syntax:"<number>";'
                "inherits:true;initial-value:-999}"
            )
            css.append(f".{name}{{{values};--{name}-out:calc({mode_terms})}}")
            html.append(
                f'<div class="{name}" data-count="{count}" data-mode="{mode}"></div>'
            )
    (OUT / "limit-probe.css").write_text("".join(css))
    (OUT / "limit-probe.html").write_text("".join(html))


def norm_declarations(
    source: str,
    target: str,
    gamma: np.ndarray,
    beta: np.ndarray,
    mean_name: str,
    variance_name: str,
) -> list[str]:
    values = [f"var({prop(source, index)})" for index in range(WIDTH)]
    declarations = [
        f"--{mean_name}:calc(({' + '.join(values)})/{WIDTH})",
        f"--{variance_name}:calc(("
        + " + ".join(
            f"(var({prop(source, index)}) - var(--{mean_name}))*"
            f"(var({prop(source, index)}) - var(--{mean_name}))"
            for index in range(WIDTH)
        )
        + f")/{WIDTH})",
    ]
    for index in range(WIDTH):
        declarations.append(
            f"{prop(target, index)}:calc("
            f"(var({prop(source, index)}) - var(--{mean_name}))/"
            f"sqrt(var(--{variance_name}) + {EPSILON})*{css_number(gamma[index])} + "
            f"({css_number(beta[index])}))"
        )
    return declarations


def sinks(prefix: str = "out") -> str:
    return "".join(
        f'<i class="sink" style="--sink:var({prop(prefix, index)})"></i>'
        for index in range(WIDTH)
    )


def page(title: str, stylesheet: str, prefix: str = "out") -> str:
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>{title}</title>'
        f'<link rel="stylesheet" href="{stylesheet}">'
        f'<h1>{title}</h1><div id="result" class="model">{sinks(prefix)}</div>'
    )


def sharded_page(title: str, stylesheets: list[str], prefix: str = "o") -> str:
    links = "".join(f'<link rel="stylesheet" href="{name}">' for name in stylesheets)
    return (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>{title}</title>'
        f"{links}<h1>{title}</h1><div id=\"result\" class=\"model\">"
        f"{sinks(prefix)}</div>"
    )


def byte_balanced_chunks(values: list[str], count: int) -> list[list[str]]:
    target = math.ceil(sum(len(value) + 1 for value in values) / count)
    chunks: list[list[str]] = [[]]
    size = 0
    for value in values:
        value_size = len(value) + 1
        if size and size + value_size > target and len(chunks) < count:
            chunks.append([])
            size = 0
        chunks[-1].append(value)
        size += value_size
    return chunks


def base_styles() -> str:
    return (
        "html{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}"
        "body{margin:2rem}.sink{position:fixed;inset:0 auto auto 0;display:block;"
        "width:calc((var(--sink) + 1000)*1px);height:1px;overflow:hidden}"
    )


def build_matrix(
    data: dict[str, np.ndarray],
    q_composed,
    composed_bias: np.ndarray,
    n1: np.ndarray,
) -> dict[str, object]:
    declarations = [
        f"{prop('i', index)}:{css_number(value)}"
        for index, value in enumerate(n1)
    ]
    expected = np.empty(WIDTH, dtype=np.float64)
    for output in range(WIDTH):
        scale = float(q_composed.scales[output])
        expression = dot(q_composed.codes[output], "i")
        declarations.append(
            f"{prop('o', output)}:calc(({expression})*{css_number(scale)} + "
            f"({css_number(composed_bias[output])}) + "
            f"({css_number(data['x'][output])}))"
        )
        expected[output] = (
            q_composed.reconstructed[output] @ n1
            + composed_bias[output]
            + data["x"][output]
        )
    css = (
        registrations((("o", WIDTH),))
        + base_styles()
        + f'.model{{{";".join(declarations)}}}'
    )
    css_path = OUT / "matrix.css"
    css_path.write_text(css)
    (OUT / "matrix.html").write_text(
        page("Direct CSS 768×768 GPT-2 matrix", "matrix.css", "o")
    )
    return {
        "matrix_css_bytes": css_path.stat().st_size,
        "matrix_expected": expected.tolist(),
        "matrix_terms": int(np.count_nonzero(q_composed.codes)),
    }


def build_full_block(
    data: dict[str, np.ndarray],
    q_composed,
    composed_bias: np.ndarray,
    q_fc,
    q_mlp,
) -> dict[str, object]:
    declarations = [
        f"{prop('x', index)}:{css_number(value)}"
        for index, value in enumerate(data["x"])
    ]
    declarations += norm_declarations(
        "x", "a", data["ln1_gamma"], data["ln1_beta"], "m1", "v1"
    )
    for output in range(WIDTH):
        expression = dot(q_composed.codes[output], "a")
        declarations.append(
            f"{prop('b', output)}:calc(var({prop('x', output)}) + "
            f"({expression})*{css_number(q_composed.scales[output])} + "
            f"({css_number(composed_bias[output])}))"
        )
    declarations += norm_declarations(
        "b", "c", data["ln2_gamma"], data["ln2_beta"], "m2", "v2"
    )
    for output in range(MLP_WIDTH):
        expression = dot(q_fc.codes[output], "c")
        declarations.append(
            f"{prop('d', output)}:calc(({expression})*"
            f"{css_number(q_fc.scales[output])} + "
            f"({css_number(data['fc_bias'][output])}))"
        )
        z = f"var({prop('d', output)})"
        t = (
            f"({css_number(math.sqrt(2 / math.pi))}*"
            f"({z} + 0.044715*{z}*{z}*{z}))"
        )
        declarations.append(
            f"{prop('e', output)}:calc(0.5*{z}*"
            f"(1 + (exp(2*{t}) - 1)/(exp(2*{t}) + 1)))"
        )
    for output in range(WIDTH):
        expression = dot(q_mlp.codes[output], "e")
        declarations.append(
            f"{prop('o', output)}:calc(var({prop('b', output)}) + "
            f"({expression})*{css_number(q_mlp.scales[output])} + "
            f"({css_number(data['mlp_proj_bias'][output])}))"
        )
    registry = registrations(
        (
            ("a", WIDTH),
            ("b", WIDTH),
            ("c", WIDTH),
            ("d", MLP_WIDTH),
            ("e", MLP_WIDTH),
            ("o", WIDTH),
        )
    )
    css = registry + base_styles() + f'.model{{{";".join(declarations)}}}'
    css_path = OUT / "block.css"
    css_path.write_text(css)
    (OUT / "block.html").write_text(
        page("Direct CSS one-token GPT-2 block", "block.css", "o")
    )
    base_name = "block-sharded-base.css"
    (OUT / base_name).write_text(registry + base_styles())
    shard_names = []
    shard_sizes = []
    for index, chunk in enumerate(
        byte_balanced_chunks(declarations, BLOCK_CSS_SHARDS)
    ):
        name = f"block-shard-{index:02d}.css"
        path = OUT / name
        path.write_text(f'.model{{{";".join(chunk)}}}')
        shard_names.append(name)
        shard_sizes.append(path.stat().st_size)
    (OUT / "block-sharded.html").write_text(
        sharded_page(
            "Sharded direct CSS one-token GPT-2 block",
            [base_name, *shard_names],
        )
    )
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    r1 = data["x"] + q_composed.reconstructed @ n1 + composed_bias
    n2 = layer_norm(r1, data["ln2_gamma"], data["ln2_beta"])
    hidden = gelu_new(q_fc.reconstructed @ n2 + data["fc_bias"])
    expected = r1 + q_mlp.reconstructed @ hidden + data["mlp_proj_bias"]
    return {
        "block_css_bytes": css_path.stat().st_size,
        "block_expected": expected.tolist(),
        "block_terms": int(
            np.count_nonzero(q_composed.codes)
            + np.count_nonzero(q_fc.codes)
            + np.count_nonzero(q_mlp.codes)
        ),
        "block_css_shards": len(shard_names),
        "block_largest_shard_bytes": max(shard_sizes),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    build_limit_probe()
    started = time.perf_counter()
    data = model_data()
    composed_weight = data["attn_proj_weight"] @ data["v_weight"]
    composed_bias = (
        data["attn_proj_weight"] @ data["v_bias"] + data["attn_proj_bias"]
    )
    q_composed = quantize_float_rows(composed_weight, bits=QUANT_BITS)
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    metadata = {
        "token_id": TOKEN_ID,
        "width": WIDTH,
        "quant_bits": QUANT_BITS,
        **build_matrix(data, q_composed, composed_bias, n1),
    }
    if args.full:
        q_fc = quantize_float_rows(data["fc_weight"], bits=QUANT_BITS)
        q_mlp = quantize_float_rows(data["mlp_proj_weight"], bits=QUANT_BITS)
        metadata.update(
            build_full_block(data, q_composed, composed_bias, q_fc, q_mlp)
        )
    metadata["build_seconds"] = time.perf_counter() - started
    (OUT / "reference.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print({key: value for key, value in metadata.items() if key.endswith(("bytes", "terms", "seconds"))})


if __name__ == "__main__":
    main()
