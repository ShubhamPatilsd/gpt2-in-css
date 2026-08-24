#!/usr/bin/env python3
"""Compile a real pretrained tiny GPT-2 checkpoint to HTML and CSS."""

from __future__ import annotations

import collections
import html
import json
import pickle
import re
import struct
import urllib.request
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_DIR = ROOT / "data" / "tiny-gpt2"
OUT = ROOT / "pretrained"
MODEL_ID = "sshleifer/tiny-gpt2"
MODEL_REVISION = "5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"
FILES = ["config.json", "vocab.json", "merges.txt", "pytorch_model.bin"]
PROMPTS = ["Hello", "The", "CSS"]
EPSILON = 1e-5
AUTOREGRESSIVE_STEPS = 4
MAX_INTERACTIVE_PROMPT_TOKENS = 4

CSS_FUNCTIONS = """@function --gelu(--x <number>) returns <number> {
  --cube: calc(var(--x) * var(--x) * var(--x));
  --tanh-input: calc(0.7978845608 * (var(--x) + 0.044715 * var(--cube)));
  --bounded: clamp(-10, var(--tanh-input), 10);
  --exponential: exp(calc(2 * var(--bounded)));
  --tanh-value: calc((var(--exponential) - 1) / (var(--exponential) + 1));
  result: calc(0.5 * var(--x) * (1 + var(--tanh-value)));
}

"""


def css_number(value: float) -> str:
    text = f"{float(value):.9f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def convex_hull_token_ids(embeddings: np.ndarray) -> list[int]:
    """Return every 2D tied-embedding row that can win a dot-product argmax."""
    points = sorted(
        (float(vector[0]), float(vector[1]), token)
        for token, vector in enumerate(embeddings)
    )

    def cross(
        origin: tuple[float, float, int],
        first: tuple[float, float, int],
        second: tuple[float, float, int],
    ) -> float:
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (
            first[1] - origin[1]
        ) * (second[0] - origin[0])

    lower: list[tuple[float, float, int]] = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float, int]] = []
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return sorted({point[2] for point in lower[:-1] + upper[:-1]})


def download_checkpoint() -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        destination = CHECKPOINT_DIR / filename
        if destination.exists():
            continue
        url = (
            f"https://huggingface.co/{MODEL_ID}/resolve/"
            f"{MODEL_REVISION}/{filename}"
        )
        print(f"downloading {filename}...")
        urllib.request.urlretrieve(url, destination)


class StorageReference:
    def __init__(self, key: object, size: int, storage_type: str) -> None:
        self.key = str(key)
        self.size = size
        self.storage_type = storage_type
        self.data: np.ndarray | None = None


class TensorReference:
    def __init__(
        self,
        storage: StorageReference,
        offset: int,
        size: tuple[int, ...],
        stride: tuple[int, ...],
    ) -> None:
        self.storage = storage
        self.offset = offset
        self.size = tuple(size)
        self.stride = tuple(stride)

    def array(self) -> np.ndarray:
        assert self.storage.data is not None
        base = self.storage.data
        return np.lib.stride_tricks.as_strided(
            base[self.offset :],
            shape=self.size,
            strides=tuple(value * base.itemsize for value in self.stride),
        ).copy()


def rebuild_tensor(
    storage: StorageReference,
    offset: int,
    size: tuple[int, ...],
    stride: tuple[int, ...],
    *_: object,
) -> TensorReference:
    return TensorReference(storage, offset, size, stride)


def rebuild_parameter(tensor: TensorReference, *_: object) -> TensorReference:
    return tensor


class TorchLegacyUnpickler(pickle.Unpickler):
    def __init__(self, file: object, storages: dict[str, StorageReference]) -> None:
        super().__init__(file)
        self.storages = storages

    def find_class(self, module: str, name: str) -> object:
        if module == "collections" and name == "OrderedDict":
            return collections.OrderedDict
        if module == "torch._utils" and name in {
            "_rebuild_tensor",
            "_rebuild_tensor_v2",
        }:
            return rebuild_tensor
        if (module, name) in {
            ("torch._utils", "_rebuild_parameter"),
            ("torch.nn.parameter", "Parameter"),
        }:
            return rebuild_parameter
        if module == "torch" and name.endswith("Storage"):
            return name
        return super().find_class(module, name)

    def persistent_load(self, persistent_id: object) -> StorageReference:
        if not isinstance(persistent_id, tuple) or persistent_id[0] != "storage":
            raise pickle.UnpicklingError(f"unsupported reference: {persistent_id!r}")
        _, storage_type, key, _location, size, *_rest = persistent_id
        storage_key = str(key)
        if storage_key not in self.storages:
            self.storages[storage_key] = StorageReference(
                storage_key, int(size), str(storage_type)
            )
        return self.storages[storage_key]


def load_torch_legacy(path: Path) -> dict[str, np.ndarray]:
    storage_formats = {
        "FloatStorage": ("<f4", 4),
        "DoubleStorage": ("<f8", 8),
        "LongStorage": ("<i8", 8),
        "IntStorage": ("<i4", 4),
        "ShortStorage": ("<i2", 2),
        "ByteStorage": ("u1", 1),
        "CharStorage": ("i1", 1),
        "BoolStorage": ("?", 1),
    }
    storages: dict[str, StorageReference] = {}
    with path.open("rb") as file:
        pickle.load(file)  # magic number
        pickle.load(file)  # protocol version
        pickle.load(file)  # system metadata
        state = TorchLegacyUnpickler(file, storages).load()
        storage_keys = pickle.load(file)
        for key in storage_keys:
            count = struct.unpack("<Q", file.read(8))[0]
            storage = storages[str(key)]
            dtype, item_size = storage_formats[storage.storage_type]
            storage.data = np.frombuffer(file.read(count * item_size), dtype=dtype)
    return {name: tensor.array() for name, tensor in state.items()}


def bytes_to_unicode() -> dict[int, str]:
    byte_values = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    code_points = byte_values[:]
    extra = 0
    for byte in range(256):
        if byte not in byte_values:
            byte_values.append(byte)
            code_points.append(256 + extra)
            extra += 1
    return dict(zip(byte_values, [chr(code_point) for code_point in code_points]))


class Gpt2Tokenizer:
    def __init__(self, vocab_path: Path, merges_path: Path) -> None:
        self.vocab: dict[str, int] = json.loads(vocab_path.read_text())
        self.inverse_vocab = {value: key for key, value in self.vocab.items()}
        self.byte_encoder = bytes_to_unicode()
        self.byte_decoder = {value: key for key, value in self.byte_encoder.items()}
        merge_lines = merges_path.read_text().splitlines()[1:]
        self.merge_ranks = {
            tuple(line.split()): rank
            for rank, line in enumerate(merge_lines)
            if line.strip()
        }
        self.pattern = re.compile(
            r"'s|'t|'re|'ve|'m|'ll|'d| ?[A-Za-z]+| ?[0-9]+| ?[^\sA-Za-z0-9]+|\s+"
        )

    def bpe(self, token: str) -> list[str]:
        pieces = list(token)
        while len(pieces) > 1:
            candidates = [
                (self.merge_ranks.get((pieces[index], pieces[index + 1])), index)
                for index in range(len(pieces) - 1)
            ]
            valid = [(rank, index) for rank, index in candidates if rank is not None]
            if not valid:
                break
            _, best = min(valid)
            pieces = (
                pieces[:best]
                + [pieces[best] + pieces[best + 1]]
                + pieces[best + 2 :]
            )
        return pieces

    def encode(self, text: str) -> list[int]:
        result: list[int] = []
        for match in self.pattern.findall(text):
            encoded = "".join(self.byte_encoder[byte] for byte in match.encode("utf-8"))
            result.extend(self.vocab[piece] for piece in self.bpe(encoded))
        return result

    def decode_token(self, token_id: int) -> str:
        encoded = self.inverse_vocab[token_id]
        raw = bytes(self.byte_decoder[character] for character in encoded)
        return raw.decode("utf-8", errors="replace")


def layer_norm(
    vector: np.ndarray, gamma: np.ndarray, beta: np.ndarray
) -> np.ndarray:
    centered = vector - vector.mean()
    return centered / np.sqrt((centered**2).mean() + EPSILON) * gamma + beta


def gelu_new(vector: np.ndarray) -> np.ndarray:
    return 0.5 * vector * (
        1 + np.tanh(np.sqrt(2 / np.pi) * (vector + 0.044715 * vector**3))
    )


def forward(token_ids: list[int], state: dict[str, np.ndarray]) -> np.ndarray:
    length = len(token_ids)
    x = state["transformer.wte.weight"][token_ids]
    x = x + state["transformer.wpe.weight"][:length]
    for layer in range(2):
        prefix = f"transformer.h.{layer}"
        normalized = np.stack(
            [
                layer_norm(
                    row,
                    state[f"{prefix}.ln_1.weight"],
                    state[f"{prefix}.ln_1.bias"],
                )
                for row in x
            ]
        )
        qkv = (
            normalized @ state[f"{prefix}.attn.c_attn.weight"]
            + state[f"{prefix}.attn.c_attn.bias"]
        )
        q, k, v = np.split(qkv, 3, axis=1)
        attended = np.zeros_like(x)
        for position in range(length):
            for head in range(2):
                scores = q[position, head] * k[: position + 1, head]
                probabilities = np.exp(scores - scores.max())
                probabilities /= probabilities.sum()
                attended[position, head] = probabilities @ v[: position + 1, head]
        x = (
            x
            + attended @ state[f"{prefix}.attn.c_proj.weight"]
            + state[f"{prefix}.attn.c_proj.bias"]
        )
        normalized = np.stack(
            [
                layer_norm(
                    row,
                    state[f"{prefix}.ln_2.weight"],
                    state[f"{prefix}.ln_2.bias"],
                )
                for row in x
            ]
        )
        hidden = gelu_new(
            normalized @ state[f"{prefix}.mlp.c_fc.weight"]
            + state[f"{prefix}.mlp.c_fc.bias"]
        )
        x = (
            x
            + hidden @ state[f"{prefix}.mlp.c_proj.weight"]
            + state[f"{prefix}.mlp.c_proj.bias"]
        )
    last = layer_norm(
        x[-1], state["transformer.ln_f.weight"], state["transformer.ln_f.bias"]
    )
    return state["transformer.wte.weight"] @ last


class CssCompiler:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.lines = [":root {"]

    @staticmethod
    def ref(name: str) -> str:
        return f"var(--{name})"

    def raw(self, name: str, expression: str) -> str:
        self.names.append(name)
        self.lines.append(f"  --{name}: {expression};")
        return self.ref(name)

    def value(self, name: str, expression: str) -> str:
        return self.raw(name, f"calc({expression})")

    def dot(
        self, name: str, inputs: list[str], weights: np.ndarray, bias: float = 0
    ) -> str:
        terms = [css_number(bias)]
        terms.extend(
            f"({input_value}) * {css_number(weight)}"
            for input_value, weight in zip(inputs, weights)
        )
        return self.value(name, " + ".join(terms))

    def normalize(
        self,
        prefix: str,
        vector: list[str],
        gamma: np.ndarray,
        beta: np.ndarray,
    ) -> list[str]:
        mean = self.value(f"{prefix}-mean", f"({vector[0]} + {vector[1]}) / 2")
        deltas = [
            self.value(f"{prefix}-delta-{index}", f"({value}) - ({mean})")
            for index, value in enumerate(vector)
        ]
        variance = self.value(
            f"{prefix}-variance",
            f"(({deltas[0]}) * ({deltas[0]}) + ({deltas[1]}) * ({deltas[1]})) / 2",
        )
        inverse = self.value(
            f"{prefix}-inverse-std", f"1 / sqrt(({variance}) + {EPSILON})"
        )
        return [
            self.value(
                f"{prefix}-value-{index}",
                f"({deltas[index]}) * ({inverse}) * {css_number(gamma[index])} + {css_number(beta[index])}",
            )
            for index in range(2)
        ]

    def reduce_tree(
        self, prefix: str, values: list[str], operation: str, chunk_size: int = 32
    ) -> str:
        level = values
        depth = 0
        while len(level) > 1:
            next_level = []
            for group_index, start in enumerate(range(0, len(level), chunk_size)):
                group = level[start : start + chunk_size]
                if len(group) == 1:
                    next_level.append(group[0])
                elif operation == "max":
                    next_level.append(
                        self.raw(
                            f"{prefix}-{depth}-{group_index}",
                            f"max({', '.join(group)})",
                        )
                    )
                else:
                    next_level.append(
                        self.value(
                            f"{prefix}-{depth}-{group_index}", " + ".join(group)
                        )
                    )
            level = next_level
            depth += 1
        return level[0]

def compile_css(
    state: dict[str, np.ndarray],
    prompt_ids: list[int],
    predicted_ids: list[int],
) -> None:
    compiler = CssCompiler()
    inputs = [compiler.raw(f"input-{dimension}", "0") for dimension in range(2)]
    x = inputs
    for layer in range(2):
        prefix = f"transformer.h.{layer}"
        normalized = compiler.normalize(
            f"layer-{layer}-ln1",
            x,
            state[f"{prefix}.ln_1.weight"],
            state[f"{prefix}.ln_1.bias"],
        )
        qkv = [
            compiler.dot(
                f"layer-{layer}-qkv-{output}",
                normalized,
                state[f"{prefix}.attn.c_attn.weight"][:, output],
                state[f"{prefix}.attn.c_attn.bias"][output],
            )
            for output in range(6)
        ]
        attended = qkv[4:6]  # one-position causal attention has probability 1
        projection = [
            compiler.dot(
                f"layer-{layer}-attn-proj-{output}",
                attended,
                state[f"{prefix}.attn.c_proj.weight"][:, output],
                state[f"{prefix}.attn.c_proj.bias"][output],
            )
            for output in range(2)
        ]
        residual = [
            compiler.value(
                f"layer-{layer}-residual1-{dimension}",
                f"({x[dimension]}) + ({projection[dimension]})",
            )
            for dimension in range(2)
        ]
        normalized_2 = compiler.normalize(
            f"layer-{layer}-ln2",
            residual,
            state[f"{prefix}.ln_2.weight"],
            state[f"{prefix}.ln_2.bias"],
        )
        feed_forward = [
            compiler.dot(
                f"layer-{layer}-fc-{unit}",
                normalized_2,
                state[f"{prefix}.mlp.c_fc.weight"][:, unit],
                state[f"{prefix}.mlp.c_fc.bias"][unit],
            )
            for unit in range(8)
        ]
        activated = [
            compiler.raw(f"layer-{layer}-gelu-{unit}", f"--gelu({value})")
            for unit, value in enumerate(feed_forward)
        ]
        down = [
            compiler.dot(
                f"layer-{layer}-mlp-proj-{output}",
                activated,
                state[f"{prefix}.mlp.c_proj.weight"][:, output],
                state[f"{prefix}.mlp.c_proj.bias"][output],
            )
            for output in range(2)
        ]
        x = [
            compiler.value(
                f"layer-{layer}-residual2-{dimension}",
                f"({residual[dimension]}) + ({down[dimension]})",
            )
            for dimension in range(2)
        ]

    final = compiler.normalize(
        "final-ln",
        x,
        state["transformer.ln_f.weight"],
        state["transformer.ln_f.bias"],
    )
    embeddings = state["transformer.wte.weight"]
    output_tokens = convex_hull_token_ids(embeddings)
    logits = {
        token: compiler.dot(f"logit-{token}", final, embeddings[token])
        for token in output_tokens
    }
    maximum = compiler.reduce_tree("max-logit", list(logits.values()), "max")
    # Convex-hull vertices are the only tied embeddings capable of winning a
    # dot-product argmax. This finite page only needs winner checks for tokens
    # that one of its selectable prompts can produce.
    candidate_indicators = {}
    for token in sorted(set(predicted_ids)):
        difference = compiler.value(
            f"token-difference-{token}",
            f"abs(({logits[token]}) - ({maximum}))",
        )
        candidate_indicators[token] = compiler.value(
            f"is-token-{token}",
            f"1 - max(0, sign(({difference}) - 0.000001))",
        )
    declarations = compiler.lines[1:]
    compiler.lines = []
    for start in range(0, len(declarations), 1000):
        compiler.lines.append(":root {")
        compiler.lines.extend(declarations[start : start + 1000])
        compiler.lines.append("}")

    embeddings_with_position = embeddings[prompt_ids] + state["transformer.wpe.weight"][0]
    for prompt_index, vector in enumerate(embeddings_with_position):
        compiler.lines.append(f":root:has(#prompt-{prompt_index}:checked) {{")
        for dimension, value in enumerate(vector):
            compiler.lines.append(f"  --input-{dimension}: {css_number(value)};")
        compiler.lines.append("}")
        compiler.lines.append(
            f':root:has(#prompt-{prompt_index}:checked) '
            f'.reference[data-prompt="{prompt_index}"] {{ display: flex; }}'
        )
    for token, indicator in candidate_indicators.items():
        compiler.lines.append(
            f'.prediction-option[data-token="{token}"] '
            f'{{ opacity: {indicator}; }}'
        )

    registrations = [
        "/* Generated from sshleifer/tiny-gpt2 by tools/build_pretrained_gpt2.py. */",
        CSS_FUNCTIONS,
    ]
    registrations.extend(
        f'@property --{name} {{ syntax: "<number>"; inherits: true; initial-value: 0; }}'
        for name in dict.fromkeys(compiler.names)
    )
    (OUT / "model.css").write_text(
        "\n".join(registrations + compiler.lines) + "\n"
    )


def compile_autoregressive_context(
    compiler: CssCompiler,
    state: dict[str, np.ndarray],
    inputs: list[list[str]],
    generation: int,
) -> list[str]:
    """Compile a causal transformer pass and return the last hidden vector."""
    x = inputs
    for layer in range(2):
        weight_prefix = f"transformer.h.{layer}"
        node_prefix = f"generation-{generation}-layer-{layer}"
        normalized = [
            compiler.normalize(
                f"{node_prefix}-ln1-{position}",
                vector,
                state[f"{weight_prefix}.ln_1.weight"],
                state[f"{weight_prefix}.ln_1.bias"],
            )
            for position, vector in enumerate(x)
        ]
        qkv = [
            [
                compiler.dot(
                    f"{node_prefix}-qkv-{position}-{output}",
                    vector,
                    state[f"{weight_prefix}.attn.c_attn.weight"][:, output],
                    state[f"{weight_prefix}.attn.c_attn.bias"][output],
                )
                for output in range(6)
            ]
            for position, vector in enumerate(normalized)
        ]
        queries = [vector[:2] for vector in qkv]
        keys = [vector[2:4] for vector in qkv]
        values = [vector[4:6] for vector in qkv]

        attended: list[list[str]] = []
        for position in range(len(x)):
            output = []
            for head in range(2):
                scores = [
                    compiler.value(
                        f"{node_prefix}-attention-score-{position}-{head}-{source}",
                        f"({queries[position][head]}) * ({keys[source][head]})",
                    )
                    for source in range(position + 1)
                ]
                maximum = compiler.reduce_tree(
                    f"{node_prefix}-attention-max-{position}-{head}",
                    scores,
                    "max",
                )
                exponentials = [
                    compiler.raw(
                        f"{node_prefix}-attention-exp-{position}-{head}-{source}",
                        f"exp(({score}) - ({maximum}))",
                    )
                    for source, score in enumerate(scores)
                ]
                denominator = compiler.value(
                    f"{node_prefix}-attention-denominator-{position}-{head}",
                    " + ".join(exponentials),
                )
                probabilities = [
                    compiler.value(
                        f"{node_prefix}-attention-probability-{position}-{head}-{source}",
                        f"({exponential}) / ({denominator})",
                    )
                    for source, exponential in enumerate(exponentials)
                ]
                output.append(
                    compiler.value(
                        f"{node_prefix}-attention-value-{position}-{head}",
                        " + ".join(
                            f"({probability}) * ({values[source][head]})"
                            for source, probability in enumerate(probabilities)
                        ),
                    )
                )
            attended.append(output)

        residual_1: list[list[str]] = []
        for position, vector in enumerate(x):
            projection = [
                compiler.dot(
                    f"{node_prefix}-attention-projection-{position}-{output}",
                    attended[position],
                    state[f"{weight_prefix}.attn.c_proj.weight"][:, output],
                    state[f"{weight_prefix}.attn.c_proj.bias"][output],
                )
                for output in range(2)
            ]
            residual_1.append(
                [
                    compiler.value(
                        f"{node_prefix}-residual1-{position}-{dimension}",
                        f"({vector[dimension]}) + ({projection[dimension]})",
                    )
                    for dimension in range(2)
                ]
            )

        normalized_2 = [
            compiler.normalize(
                f"{node_prefix}-ln2-{position}",
                vector,
                state[f"{weight_prefix}.ln_2.weight"],
                state[f"{weight_prefix}.ln_2.bias"],
            )
            for position, vector in enumerate(residual_1)
        ]
        next_x: list[list[str]] = []
        for position, vector in enumerate(normalized_2):
            feed_forward = [
                compiler.dot(
                    f"{node_prefix}-fc-{position}-{unit}",
                    vector,
                    state[f"{weight_prefix}.mlp.c_fc.weight"][:, unit],
                    state[f"{weight_prefix}.mlp.c_fc.bias"][unit],
                )
                for unit in range(8)
            ]
            activated = []
            for unit, value in enumerate(feed_forward):
                activation_prefix = f"{node_prefix}-gelu-{position}-{unit}"
                cube = compiler.value(
                    f"{activation_prefix}-cube",
                    f"({value}) * ({value}) * ({value})",
                )
                tanh_input = compiler.value(
                    f"{activation_prefix}-input",
                    f"0.7978845608 * (({value}) + 0.044715 * ({cube}))",
                )
                bounded = compiler.raw(
                    f"{activation_prefix}-bounded",
                    f"clamp(-10, {tanh_input}, 10)",
                )
                exponential = compiler.raw(
                    f"{activation_prefix}-exp",
                    f"exp(2 * ({bounded}))",
                )
                tanh_value = compiler.value(
                    f"{activation_prefix}-tanh",
                    f"(({exponential}) - 1) / (({exponential}) + 1)",
                )
                activated.append(
                    compiler.value(
                        activation_prefix,
                        f"0.5 * ({value}) * (1 + ({tanh_value}))",
                    )
                )
            projection = [
                compiler.dot(
                    f"{node_prefix}-mlp-projection-{position}-{output}",
                    activated,
                    state[f"{weight_prefix}.mlp.c_proj.weight"][:, output],
                    state[f"{weight_prefix}.mlp.c_proj.bias"][output],
                )
                for output in range(2)
            ]
            next_x.append(
                [
                    compiler.value(
                        f"{node_prefix}-residual2-{position}-{dimension}",
                        f"({residual_1[position][dimension]}) + ({projection[dimension]})",
                    )
                    for dimension in range(2)
                ]
            )
        x = next_x

    return compiler.normalize(
        f"generation-{generation}-final-ln",
        x[-1],
        state["transformer.ln_f.weight"],
        state["transformer.ln_f.bias"],
    )


def compile_autoregressive_css(
    state: dict[str, np.ndarray],
    prompt_ids: list[int],
    sequences: list[list[int]],
    *,
    full_vocabulary: bool = False,
    filename: str = "autoregressive.css",
    prompt_length: int = 1,
) -> None:
    compiler = CssCompiler()
    embeddings = state["transformer.wte.weight"]
    output_tokens = convex_hull_token_ids(embeddings)
    positions = state["transformer.wpe.weight"]
    if full_vocabulary:
        prompt_inputs = [
            [
                compiler.raw(
                    f"interactive-input-{position}-{dimension}", "0"
                )
                for dimension in range(2)
            ]
            for position in range(prompt_length)
        ]
    else:
        prompt_inputs = [
            [
                compiler.raw(f"autoregressive-input-{dimension}", "0")
                for dimension in range(2)
            ]
        ]
    selected_embeddings: list[list[str]] = []
    generation_indicators: list[dict[int, str]] = []

    for generation in range(AUTOREGRESSIVE_STEPS):
        inputs = [vector[:] for vector in prompt_inputs]
        for position, embedding in enumerate(
            selected_embeddings, start=prompt_length
        ):
            inputs.append(
                [
                    compiler.value(
                        f"generation-{generation}-input-{position}-{dimension}",
                        f"({embedding[dimension]}) + {css_number(positions[position, dimension])}",
                    )
                    for dimension in range(2)
                ]
            )

        final = compile_autoregressive_context(compiler, state, inputs, generation)
        logits = {
            token: compiler.dot(
                f"generation-{generation}-logit-{token}",
                final,
                embeddings[token],
            )
            for token in output_tokens
        }
        maximum = compiler.reduce_tree(
            f"generation-{generation}-max-logit", list(logits.values()), "max"
        )
        candidates = (
            output_tokens
            if full_vocabulary
            else sorted({sequence[generation] for sequence in sequences})
        )
        indicators = {}
        for token in candidates:
            difference = compiler.value(
                f"generation-{generation}-token-difference-{token}",
                f"abs(({logits[token]}) - ({maximum}))",
            )
            indicators[token] = compiler.value(
                f"generation-{generation}-is-token-{token}",
                f"1 - max(0, sign(({difference}) - 0.000001))",
            )
        generation_indicators.append(indicators)
        if full_vocabulary:
            winner_sum = compiler.value(
                f"generation-{generation}-winner-sum",
                " + ".join(
                    f"({indicator}) * {token}"
                    for token, indicator in indicators.items()
                ),
            )
            compiler.raw(f"generation-{generation}-winner-id", winner_sum)
        if generation + 1 < AUTOREGRESSIVE_STEPS:
            selected_embeddings.append(
                [
                    compiler.value(
                        f"generation-{generation}-selected-embedding-{dimension}",
                        " + ".join(
                            f"({indicator}) * {css_number(embeddings[token, dimension])}"
                            for token, indicator in indicators.items()
                        ),
                    )
                    for dimension in range(2)
                ]
            )

    declarations = compiler.lines[1:]
    compiler.lines = []
    for start in range(0, len(declarations), 1000):
        compiler.lines.append(":root {")
        compiler.lines.extend(declarations[start : start + 1000])
        compiler.lines.append("}")

    if not full_vocabulary:
        prompt_vectors = embeddings[prompt_ids] + positions[0]
        for prompt_index, vector in enumerate(prompt_vectors):
            compiler.lines.append(f":root:has(#prompt-{prompt_index}:checked) {{")
            for dimension, value in enumerate(vector):
                compiler.lines.append(
                    f"  --autoregressive-input-{dimension}: {css_number(value)};"
                )
            compiler.lines.append("}")
    if not full_vocabulary:
        for generation, indicators in enumerate(generation_indicators):
            for token, indicator in indicators.items():
                compiler.lines.append(
                    f'.generated-token[data-step="{generation}"] '
                    f'.token-option[data-token="{token}"] {{ opacity: {indicator}; }}'
                )

    registrations = [
        "/* Four-token causal chain generated from sshleifer/tiny-gpt2. */",
        CSS_FUNCTIONS,
    ]
    registrations.extend(
        f'@property --{name} {{ syntax: "<number>"; inherits: true; initial-value: 0; }}'
        for name in dict.fromkeys(compiler.names)
    )
    (OUT / filename).write_text(
        "\n".join(registrations + compiler.lines) + "\n"
    )


def write_html(
    tokenizer: Gpt2Tokenizer,
    prompt_ids: list[int],
    predicted_ids: list[int],
) -> None:
    controls = "\n".join(
        f'''        <input type="radio" name="prompt" id="prompt-{index}"{(" checked" if index == 0 else "")}>
        <label for="prompt-{index}">{html.escape(prompt)}</label>'''
        for index, prompt in enumerate(PROMPTS)
    )
    options = "".join(
        f'<span class="prediction-option" data-token="{token}">'
        f'<strong>{html.escape(tokenizer.decode_token(token))}</strong>'
        f'<small>token {token}</small></span>'
        for token in sorted(set(predicted_ids))
    )
    references = "\n".join(
        f'''        <span class="reference" data-prompt="{index}">
          <span>Python reference</span>
          <strong>token {predicted}: {html.escape(tokenizer.decode_token(predicted))!s}</strong>
        </span>'''
        for index, predicted in enumerate(predicted_ids)
    )
    document = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pretrained GPT-2, computed by CSS</title>
  <link rel="stylesheet" href="model.css">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main>
    <p class="eyebrow">Experiment 003 · pretrained checkpoint · zero scripts</p>
    <h1>Pretrained GPT-2, computed by CSS.</h1>
    <p class="lede">
      The genuine two-layer <code>sshleifer/tiny-gpt2</code> checkpoint, its
      50,257-token vocabulary, GELU blocks, layer norms, and complete language
      head—compiled into browser-evaluated CSS.
    </p>

    <section class="demo">
      <fieldset>
        <legend>Choose a single-token GPT-2 prompt</legend>
        <div class="prompt-options">
{controls}
        </div>
      </fieldset>

      <div class="prediction" aria-label="CSS-selected next token">{options}</div>
{references}
    </section>

    <p class="proof">
      Build-time Python only downloads and converts the pretrained weights.
      At runtime, CSS computes both transformer blocks and an exact language-head
      argmax. Because the tied embeddings are two-dimensional, only 16 points on
      their convex hull can ever win; the other 50,241 logits are mathematically
      dead. This document contains no
      <code>&lt;script&gt;</code> element.
    </p>
    <p class="back">
      <a href="../transformer/index.html">← Tiny autoregressive transformer</a>
      <a href="interactive.html">Type a prompt →</a>
      <a href="benchmark.html">Run autoregressive benchmark →</a>
    </p>
  </main>
</body>
</html>
'''
    (OUT / "index.html").write_text(document)


def write_benchmark_html(
    tokenizer: Gpt2Tokenizer,
    sequences: list[list[int]],
) -> None:
    controls = "\n".join(
        f'<input type="radio" name="prompt" id="prompt-{index}"'
        f'{(" checked" if index == 0 else "")}>'
        for index, _prompt in enumerate(PROMPTS)
    )
    generated = []
    for generation in range(AUTOREGRESSIVE_STEPS):
        candidates = sorted({sequence[generation] for sequence in sequences})
        options = "".join(
            f'<span class="token-option" data-token="{token}">'
            f'{html.escape(tokenizer.decode_token(token))}</span>'
            for token in candidates
        )
        generated.append(
            f'<span class="generated-token" data-step="{generation}">{options}</span>'
        )
    expected = json.dumps(
        {prompt: sequence for prompt, sequence in zip(PROMPTS, sequences)}
    )
    prompts = json.dumps(PROMPTS)
    document = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CSS GPT-2 throughput benchmark</title>
  <link rel="stylesheet" href="autoregressive.css">
  <link rel="stylesheet" href="benchmark.css">
</head>
<body>
  <div class="model-state" aria-hidden="true">
{controls}
    {"".join(generated)}
  </div>
  <pre id="stream">warming up…</pre>
  <p class="controls">
    <button type="button" id="stop">pause</button>
    <button type="button" id="start" disabled>resume</button>
    <span id="metrics">loading CSS graph…</span>
  </p>
  <p class="note">four-token causal chains · 561 KB tiny-gpt2 graph · full GPT-2 small projection: 3.16 GB per token · <a href="interactive.html">typed prompt</a></p>

  <script type="module">
    const prompts = {prompts};
    const expected = {expected};
    const inputs = [...document.querySelectorAll('input[name="prompt"]')];
    const generations = [...document.querySelectorAll('.generated-token')];
    const stream = document.querySelector('#stream');
    const startButton = document.querySelector('#start');
    const stopButton = document.querySelector('#stop');
    const metrics = document.querySelector('#metrics');
    const tokensPerChain = {AUTOREGRESSIVE_STEPS};
    let running = false;
    let promptIndex = 0;
    let sampleCount = 0;
    let computeMilliseconds = 0;
    let wallStarted = 0;
    let lines = [];

    function inferOnce() {{
      promptIndex = (promptIndex + 1) % prompts.length;
      const started = performance.now();
      inputs[promptIndex].checked = true;
      const terminalGeneration = generations[generations.length - 1];
      [...terminalGeneration.querySelectorAll('.token-option')].find(
        candidate => Number.parseFloat(getComputedStyle(candidate).opacity) > 0.5
      );
      const elapsed = performance.now() - started;
      const selected = generations.map(generation => {{
        const option = [...generation.querySelectorAll('.token-option')].find(
          candidate => Number.parseFloat(getComputedStyle(candidate).opacity) > 0.5
        );
        return option;
      }});
      const winners = selected.map(option => option ? Number(option.dataset.token) : -1);
      if (winners.some((token, index) => token !== expected[prompts[promptIndex]][index])) {{
        throw new Error(`CSS prediction mismatch for ${{prompts[promptIndex]}}`);
      }}
      return {{ elapsed, text: prompts[promptIndex] + selected.map(option => option.textContent).join('') }};
    }}

    function updateResults() {{
      const wallMilliseconds = performance.now() - wallStarted;
      const tokenCount = sampleCount * tokensPerChain;
      const computeRate = tokenCount * 1000 / computeMilliseconds;
      const wallRate = tokenCount * 1000 / wallMilliseconds;
      const latency = computeMilliseconds / tokenCount;
      metrics.textContent = `${{computeRate.toFixed(2)}} tok/s · ${{latency.toFixed(2)}} ms/token · ${{wallRate.toFixed(2)}} tok/s including display`;
    }}

    function runBatch() {{
      if (!running) return;
      try {{
        const result = inferOnce();
        computeMilliseconds += result.elapsed;
        sampleCount += 1;
        lines.push(result.text);
        if (lines.length > 200) lines = lines.slice(-200);
        stream.textContent = `${{lines.join('\\n')}}\\n`;
        stream.scrollTop = stream.scrollHeight;
        updateResults();
        setTimeout(runBatch, 2000);
      }} catch (error) {{
        running = false;
        metrics.textContent = error.message;
        startButton.disabled = false;
        stopButton.disabled = true;
      }}
    }}

    function begin() {{
      if (running) return;
      stream.textContent = 'warming up…';
      for (let index = 0; index < prompts.length; index += 1) inferOnce();
      sampleCount = 0;
      computeMilliseconds = 0;
      lines = [];
      wallStarted = performance.now();
      running = true;
      startButton.disabled = true;
      stopButton.disabled = false;
      metrics.textContent = 'running…';
      setTimeout(runBatch, 2000);
    }}

    startButton.addEventListener('click', begin);

    stopButton.addEventListener('click', () => {{
      running = false;
      startButton.disabled = false;
      stopButton.disabled = true;
      metrics.textContent += ` · paused after ${{sampleCount.toLocaleString()}} chains`;
    }});

    setTimeout(begin, 0);
  </script>
</body>
</html>
'''
    (OUT / "benchmark.html").write_text(document)


def write_prompt_data(
    tokenizer: Gpt2Tokenizer,
    state: dict[str, np.ndarray],
) -> None:
    embeddings = state["transformer.wte.weight"]
    positions = state["transformer.wpe.weight"][:MAX_INTERACTIVE_PROMPT_TOKENS]
    by_id = []
    for token in range(len(embeddings)):
        decoded = tokenizer.decode_token(token)
        by_id.append(decoded)
    merges = [
        list(pair)
        for pair, _rank in sorted(
            tokenizer.merge_ranks.items(), key=lambda item: item[1]
        )
    ]
    payload = {
        "vocab": tokenizer.vocab,
        "merges": merges,
        "byId": by_id,
        "embeddings": [
            [float(css_number(value)) for value in vector]
            for vector in embeddings
        ],
        "positions": [
            [float(css_number(value)) for value in vector]
            for vector in positions
        ],
    }
    (OUT / "prompt-data.json").write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    )


def write_interactive_html() -> None:
    document = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Type a prompt for CSS GPT-2</title>
  <link id="model-css" rel="stylesheet">
  <link rel="stylesheet" href="benchmark.css">
</head>
<body>
  <form id="prompt-form">
    <input id="prompt" value="Once upon a time" autocomplete="off" spellcheck="false" aria-label="GPT-2 prompt">
    <button type="submit">start</button>
  </form>
  <pre id="stream">loading tokenizer…</pre>
  <p id="metrics">Enter a prompt containing 1–4 GPT-2 tokens.</p>
  <p class="note">four greedy CSS-generated tokens · JavaScript only tokenizes, wires inputs, and times the CSS result · <a href="benchmark.html">benchmark</a></p>
  <script type="module" src="interactive.js"></script>
</body>
</html>
'''
    (OUT / "interactive.html").write_text(document)


def main() -> None:
    download_checkpoint()
    OUT.mkdir(exist_ok=True)
    state = load_torch_legacy(CHECKPOINT_DIR / "pytorch_model.bin")
    tokenizer = Gpt2Tokenizer(
        CHECKPOINT_DIR / "vocab.json", CHECKPOINT_DIR / "merges.txt"
    )
    encoded = [tokenizer.encode(prompt) for prompt in PROMPTS]
    if any(len(tokens) != 1 for tokens in encoded):
        raise ValueError(f"prompts must encode to one token: {encoded}")
    prompt_ids = [tokens[0] for tokens in encoded]
    predicted_ids = [
        int(forward([token_id], state).argmax()) for token_id in prompt_ids
    ]
    sequences: list[list[int]] = []
    for prompt_id in prompt_ids:
        context = [prompt_id]
        sequence = []
        for _ in range(AUTOREGRESSIVE_STEPS):
            predicted = int(forward(context, state).argmax())
            context.append(predicted)
            sequence.append(predicted)
        sequences.append(sequence)
    print("reference predictions:")
    for prompt, prompt_id, predicted in zip(PROMPTS, prompt_ids, predicted_ids):
        print(
            f"  {prompt!r} ({prompt_id}) -> {predicted} "
            f"{tokenizer.decode_token(predicted)!r}"
        )
    compile_css(state, prompt_ids, predicted_ids)
    print("reference autoregressive chains:")
    for prompt, sequence in zip(PROMPTS, sequences):
        decoded = "".join(tokenizer.decode_token(token) for token in sequence)
        print(f"  {prompt!r} -> {sequence} {decoded!r}")
    compile_autoregressive_css(state, prompt_ids, sequences)
    write_html(tokenizer, prompt_ids, predicted_ids)
    write_benchmark_html(tokenizer, sequences)
    for prompt_length in range(1, MAX_INTERACTIVE_PROMPT_TOKENS + 1):
        print(f"compiling exact {prompt_length}-token interactive graph...")
        compile_autoregressive_css(
            state,
            prompt_ids,
            sequences,
            full_vocabulary=True,
            filename=f"interactive-{prompt_length}.css",
            prompt_length=prompt_length,
        )
    write_prompt_data(tokenizer, state)
    write_interactive_html()
    print("wrote pretrained pages and CSS models")


if __name__ == "__main__":
    main()
