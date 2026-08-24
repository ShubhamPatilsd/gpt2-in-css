#!/usr/bin/env python3
"""Compile a tiny GPT-2-style transformer and three generation steps to CSS."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "transformer"
VOCAB = " abcde."
DISPLAY_TOKENS = ["␠" if token == " " else token for token in VOCAB]
D_MODEL = 12
N_HEAD = 3
HEAD_DIM = D_MODEL // N_HEAD
D_FF = 24
MAX_CONTEXT = 6
EPSILON = 1e-5
PROMPTS = [" ab", "bcd", "de.", ". a"]
GENERATION_STEPS = 3


def css_number(value: float) -> str:
    text = f"{float(value):.8f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def layer_norm(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / np.sqrt(((x - x.mean()) ** 2).mean() + EPSILON)


def gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (
        1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3))
    )


def make_model(seed: int = 19) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    token_embedding = rng.normal(0, 0.08, size=(len(VOCAB), D_MODEL))
    token_embedding[:, : len(VOCAB)] += np.eye(len(VOCAB)) * 1.4
    return {
        "wte": token_embedding,
        "wpe": rng.normal(0, 0.04, size=(MAX_CONTEXT, D_MODEL)),
        "wq": rng.normal(0, 0.10, size=(D_MODEL, D_MODEL)),
        "wk": rng.normal(0, 0.10, size=(D_MODEL, D_MODEL)),
        "wv": rng.normal(0, 0.10, size=(D_MODEL, D_MODEL)),
        "wo": rng.normal(0, 0.10, size=(D_MODEL, D_MODEL)),
        "wfc": rng.normal(0, 0.10, size=(D_FF, D_MODEL)),
        "bfc": rng.normal(0, 0.01, size=D_FF),
        "wdown": rng.normal(0, 0.10, size=(D_MODEL, D_FF)),
        "bdown": rng.normal(0, 0.01, size=D_MODEL),
    }


def hidden_forward(token_ids: list[int], model: dict[str, np.ndarray]) -> np.ndarray:
    length = len(token_ids)
    x = model["wte"][token_ids] + model["wpe"][:length]
    normalized = np.stack([layer_norm(row) for row in x])
    q = normalized @ model["wq"].T
    k = normalized @ model["wk"].T
    v = normalized @ model["wv"].T
    attention = np.zeros_like(x)
    for position in range(length):
        for head in range(N_HEAD):
            section = slice(head * HEAD_DIM, (head + 1) * HEAD_DIM)
            scores = (
                k[: position + 1, section] @ q[position, section]
                / np.sqrt(HEAD_DIM)
            )
            probabilities = np.exp(scores - scores.max())
            probabilities /= probabilities.sum()
            attention[position, section] = probabilities @ v[: position + 1, section]
    x = x + attention @ model["wo"].T
    normalized_2 = np.stack([layer_norm(row) for row in x])
    hidden = gelu(normalized_2 @ model["wfc"].T + model["bfc"])
    x = x + hidden @ model["wdown"].T + model["bdown"]
    return layer_norm(x[-1])


def fit_language_head(model: dict[str, np.ndarray]) -> None:
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    cycle = list(range(len(VOCAB)))
    for start in range(len(VOCAB)):
        for length in range(1, MAX_CONTEXT):
            ids = [cycle[(start + offset) % len(cycle)] for offset in range(length)]
            target = cycle[(start + length) % len(cycle)]
            features.append(hidden_forward(ids, model))
            one_hot = np.full(len(VOCAB), -1.0)
            one_hot[target] = 5.0
            targets.append(one_hot)
    design = np.column_stack([np.stack(features), np.ones(len(features))])
    target_matrix = np.stack(targets)
    regularizer = np.eye(design.shape[1]) * 1e-4
    coefficients = np.linalg.solve(
        design.T @ design + regularizer, design.T @ target_matrix
    )
    model["lm_head"] = coefficients[:-1].T
    model["lm_bias"] = coefficients[-1]


def predict(token_ids: list[int], model: dict[str, np.ndarray]) -> tuple[int, np.ndarray]:
    hidden = hidden_forward(token_ids, model)
    logits = model["lm_head"] @ hidden + model["lm_bias"]
    return int(logits.argmax()), logits


class CssCompiler:
    def __init__(self, model: dict[str, np.ndarray]) -> None:
        self.model = model
        self.names: list[str] = []
        self.lines: list[str] = [":root {"]

    @staticmethod
    def ref(name: str) -> str:
        return f"var(--{name})"

    def value(self, name: str, expression: str) -> str:
        self.names.append(name)
        self.lines.append(f"  --{name}: calc({expression});")
        return self.ref(name)

    def raw(self, name: str, expression: str) -> str:
        self.names.append(name)
        self.lines.append(f"  --{name}: {expression};")
        return self.ref(name)

    def dot(self, name: str, inputs: list[str], weights: np.ndarray, bias: float = 0) -> str:
        terms = [css_number(bias)]
        terms.extend(
            f"({input_value}) * {css_number(weight)}"
            for input_value, weight in zip(inputs, weights)
        )
        return self.value(name, " + ".join(terms))

    def normalize(self, prefix: str, vector: list[str]) -> list[str]:
        mean = self.value(f"{prefix}-mean", f"({' + '.join(vector)}) / {D_MODEL}")
        deltas = [
            self.value(f"{prefix}-delta-{dimension}", f"({value}) - ({mean})")
            for dimension, value in enumerate(vector)
        ]
        variance = self.value(
            f"{prefix}-variance",
            f"({' + '.join(f'({delta}) * ({delta})' for delta in deltas)}) / {D_MODEL}",
        )
        inverse_std = self.value(
            f"{prefix}-inverse-std", f"1 / sqrt(({variance}) + {EPSILON})"
        )
        return [
            self.value(
                f"{prefix}-value-{dimension}", f"({delta}) * ({inverse_std})"
            )
            for dimension, delta in enumerate(deltas)
        ]

    def forward(
        self, prefix: str, inputs: list[list[str]]
    ) -> tuple[list[str], list[str]]:
        length = len(inputs)
        x: list[list[str]] = []
        for position, vector in enumerate(inputs):
            x.append(
                [
                    self.value(f"{prefix}-x-{position}-{dimension}", expression)
                    for dimension, expression in enumerate(vector)
                ]
            )

        normalized = [
            self.normalize(f"{prefix}-ln1-{position}", vector)
            for position, vector in enumerate(x)
        ]
        q: list[list[str]] = []
        k: list[list[str]] = []
        v: list[list[str]] = []
        for position in range(length):
            q.append(
                [
                    self.dot(
                        f"{prefix}-q-{position}-{dimension}",
                        normalized[position],
                        self.model["wq"][dimension],
                    )
                    for dimension in range(D_MODEL)
                ]
            )
            k.append(
                [
                    self.dot(
                        f"{prefix}-k-{position}-{dimension}",
                        normalized[position],
                        self.model["wk"][dimension],
                    )
                    for dimension in range(D_MODEL)
                ]
            )
            v.append(
                [
                    self.dot(
                        f"{prefix}-v-{position}-{dimension}",
                        normalized[position],
                        self.model["wv"][dimension],
                    )
                    for dimension in range(D_MODEL)
                ]
            )

        attended: list[list[str]] = []
        for position in range(length):
            output = [""] * D_MODEL
            for head in range(N_HEAD):
                start = head * HEAD_DIM
                scores = []
                for source in range(position + 1):
                    terms = [
                        f"({q[position][dimension]}) * ({k[source][dimension]})"
                        for dimension in range(start, start + HEAD_DIM)
                    ]
                    scores.append(
                        self.value(
                            f"{prefix}-attn-score-{position}-{head}-{source}",
                            f"({' + '.join(terms)}) / {np.sqrt(HEAD_DIM)}",
                        )
                    )
                maximum = self.raw(
                    f"{prefix}-attn-max-{position}-{head}",
                    f"max({', '.join(scores)})",
                )
                exponentials = [
                    self.raw(
                        f"{prefix}-attn-exp-{position}-{head}-{source}",
                        f"exp(({score}) - ({maximum}))",
                    )
                    for source, score in enumerate(scores)
                ]
                denominator = self.value(
                    f"{prefix}-attn-denom-{position}-{head}",
                    " + ".join(exponentials),
                )
                probabilities = [
                    self.value(
                        f"{prefix}-attn-prob-{position}-{head}-{source}",
                        f"({exponential}) / ({denominator})",
                    )
                    for source, exponential in enumerate(exponentials)
                ]
                for dimension in range(start, start + HEAD_DIM):
                    output[dimension] = self.value(
                        f"{prefix}-attn-value-{position}-{dimension}",
                        " + ".join(
                            f"({probabilities[source]}) * ({v[source][dimension]})"
                            for source in range(position + 1)
                        ),
                    )
            attended.append(output)

        residual_1: list[list[str]] = []
        for position in range(length):
            projection = [
                self.dot(
                    f"{prefix}-attn-proj-{position}-{dimension}",
                    attended[position],
                    self.model["wo"][dimension],
                )
                for dimension in range(D_MODEL)
            ]
            residual_1.append(
                [
                    self.value(
                        f"{prefix}-residual1-{position}-{dimension}",
                        f"({x[position][dimension]}) + ({projection[dimension]})",
                    )
                    for dimension in range(D_MODEL)
                ]
            )

        normalized_2 = [
            self.normalize(f"{prefix}-ln2-{position}", vector)
            for position, vector in enumerate(residual_1)
        ]
        final_vectors: list[list[str]] = []
        for position in range(length):
            feed_forward = [
                self.dot(
                    f"{prefix}-fc-{position}-{unit}",
                    normalized_2[position],
                    self.model["wfc"][unit],
                    self.model["bfc"][unit],
                )
                for unit in range(D_FF)
            ]
            activated = []
            for unit, value in enumerate(feed_forward):
                cube = self.value(
                    f"{prefix}-fc-cube-{position}-{unit}",
                    f"({value}) * ({value}) * ({value})",
                )
                tanh_input = self.value(
                    f"{prefix}-gelu-input-{position}-{unit}",
                    f"0.7978845608 * (({value}) + 0.044715 * ({cube}))",
                )
                bounded = self.raw(
                    f"{prefix}-gelu-bounded-{position}-{unit}",
                    f"clamp(-10, {tanh_input}, 10)",
                )
                exponential = self.raw(
                    f"{prefix}-gelu-exp-{position}-{unit}",
                    f"exp(2 * ({bounded}))",
                )
                tanh_value = self.value(
                    f"{prefix}-gelu-tanh-{position}-{unit}",
                    f"(({exponential}) - 1) / (({exponential}) + 1)",
                )
                activated.append(
                    self.value(
                        f"{prefix}-gelu-{position}-{unit}",
                        f"0.5 * ({value}) * (1 + ({tanh_value}))",
                    )
                )
            down = [
                self.dot(
                    f"{prefix}-mlp-proj-{position}-{dimension}",
                    activated,
                    self.model["wdown"][dimension],
                    self.model["bdown"][dimension],
                )
                for dimension in range(D_MODEL)
            ]
            final_vectors.append(
                [
                    self.value(
                        f"{prefix}-residual2-{position}-{dimension}",
                        f"({residual_1[position][dimension]}) + ({down[dimension]})",
                    )
                    for dimension in range(D_MODEL)
                ]
            )

        last = self.normalize(f"{prefix}-final-ln", final_vectors[-1])
        logits = [
            self.dot(
                f"{prefix}-logit-{token}",
                last,
                self.model["lm_head"][token],
                self.model["lm_bias"][token],
            )
            for token in range(len(VOCAB))
        ]
        maximum = self.raw(f"{prefix}-max-logit", f"max({', '.join(logits)})")
        indicators = [
            self.value(
                f"{prefix}-is-token-{token}",
                f"1 - abs(sign(({logit}) - ({maximum})))",
            )
            for token, logit in enumerate(logits)
        ]
        next_embedding = [
            self.value(
                f"{prefix}-next-embedding-{dimension}",
                " + ".join(
                    f"({indicators[token]}) * {css_number(self.model['wte'][token, dimension])}"
                    for token in range(len(VOCAB))
                ),
            )
            for dimension in range(D_MODEL)
        ]
        return indicators, next_embedding


def compile_css(model: dict[str, np.ndarray]) -> None:
    compiler = CssCompiler(model)
    prompt_inputs: list[list[str]] = []
    for position in range(len(PROMPTS[0])):
        vector = []
        for dimension in range(D_MODEL):
            name = f"prompt-{position}-{dimension}"
            compiler.raw(name, "0")
            vector.append(f"var(--{name})")
        prompt_inputs.append(vector)

    generated_embeddings: list[list[str]] = []
    generation_indicators: list[list[str]] = []
    for step in range(GENERATION_STEPS):
        inputs = [vector[:] for vector in prompt_inputs]
        for generated_position, embedding in enumerate(generated_embeddings):
            position = len(PROMPTS[0]) + generated_position
            inputs.append(
                [
                    f"({embedding[dimension]}) + {css_number(model['wpe'][position, dimension])}"
                    for dimension in range(D_MODEL)
                ]
            )
        indicators, next_embedding = compiler.forward(f"generation-{step}", inputs)
        generation_indicators.append(indicators)
        generated_embeddings.append(next_embedding)

    compiler.lines.append("}")
    for prompt_index, prompt in enumerate(PROMPTS):
        compiler.lines.append(f":root:has(#prompt-{prompt_index}:checked) {{")
        for position, character in enumerate(prompt):
            token = VOCAB.index(character)
            vector = model["wte"][token] + model["wpe"][position]
            for dimension, value in enumerate(vector):
                compiler.lines.append(
                    f"  --prompt-{position}-{dimension}: {css_number(value)};"
                )
        compiler.lines.append("}")
        compiler.lines.append(
            f':root:has(#prompt-{prompt_index}:checked) '
            f'.prompt-value[data-prompt="{prompt_index}"] {{ display: inline; }}'
        )
    for step, indicators in enumerate(generation_indicators):
        for token, indicator in enumerate(indicators):
            compiler.lines.append(
                f'.generated-token[data-step="{step}"] '
                f'.token-option[data-token="{token}"] {{ opacity: {indicator}; }}'
            )
    registrations = [
        "/* Generated by tools/build_transformer.py. No runtime JavaScript. */"
    ]
    registrations.extend(
        f'@property --{name} {{ syntax: "<number>"; inherits: true; initial-value: 0; }}'
        for name in dict.fromkeys(compiler.names)
    )
    (OUT / "model.css").write_text(
        "\n".join(registrations + compiler.lines) + "\n"
    )


def write_html(model: dict[str, np.ndarray]) -> None:
    prompt_controls = "\n".join(
        f'''        <input type="radio" name="prompt" id="prompt-{index}"{(" checked" if index == 0 else "")}>
        <label for="prompt-{index}"><code>{html.escape(prompt).replace(" ", "␠")}</code></label>'''
        for index, prompt in enumerate(PROMPTS)
    )
    prompt_values = "".join(
        f'<span class="prompt-value" data-prompt="{index}">{html.escape(prompt).replace(" ", "␠")}</span>'
        for index, prompt in enumerate(PROMPTS)
    )
    generated = []
    for step in range(GENERATION_STEPS):
        options = "".join(
            f'<span class="token-option" data-token="{token}">{html.escape(display)}</span>'
            for token, display in enumerate(DISPLAY_TOKENS)
        )
        generated.append(
            f'          <span class="generated-token" data-step="{step}">{options}</span>'
        )

    reference_rows = []
    for prompt in PROMPTS:
        ids = [VOCAB.index(character) for character in prompt]
        output = []
        for _ in range(GENERATION_STEPS):
            next_token, _ = predict(ids, model)
            ids.append(next_token)
            output.append(DISPLAY_TOKENS[next_token])
        reference_rows.append(
            f"{html.escape(prompt).replace(' ', '␠')} → {''.join(output)}"
        )

    document = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>A tiny transformer, computed by CSS</title>
  <link rel="stylesheet" href="model.css">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main>
    <p class="eyebrow">Experiment 002 · no runtime JavaScript</p>
    <h1>A transformer, computed by CSS.</h1>
    <p class="lede">
      One GPT-2-style block, three attention heads, a 12-dimensional embedding,
      causal softmax attention, GELU, residual paths, and three statically
      unrolled autoregressive steps.
    </p>

    <section class="demo">
      <fieldset class="prompt-picker">
        <legend>Choose a three-token prompt</legend>
        <div class="prompt-options">
{prompt_controls}
        </div>
      </fieldset>

      <div class="generation" aria-label="CSS-generated token sequence">
        <span class="prompt-stack">{prompt_values}</span>
{chr(10).join(generated)}
      </div>

      <div class="pipeline">
        <span>token + position</span><i>→</i><span>layer norm</span><i>→</i>
        <span>causal attention</span><i>→</i><span>residual</span><i>→</i>
        <span>GELU MLP</span><i>→</i><span>LM head</span>
      </div>

      <details>
        <summary>Python reference outputs</summary>
        <pre>{html.escape(chr(10).join(reference_rows))}</pre>
      </details>
    </section>

    <p class="proof">
      The Python build step fits the tiny language head and writes static CSS.
      At runtime, CSS performs the transformer arithmetic, computes each
      <code>max()</code>, derives one-hot token choices with
      <code>abs(sign())</code>, and feeds the chosen embedding into the next
      unrolled step. There is no <code>&lt;script&gt;</code> element.
    </p>
    <p class="back"><a href="../index.html">← MNIST MLP</a></p>
  </main>
</body>
</html>
'''
    (OUT / "index.html").write_text(document)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    model = make_model()
    fit_language_head(model)
    print("reference generations:")
    for prompt in PROMPTS:
        ids = [VOCAB.index(character) for character in prompt]
        generated = []
        for _ in range(GENERATION_STEPS):
            token, _ = predict(ids, model)
            ids.append(token)
            generated.append(DISPLAY_TOKENS[token])
        print(f"  {prompt!r} -> {''.join(generated)}")
    compile_css(model)
    write_html(model)
    print("wrote transformer/index.html and transformer/model.css")


if __name__ == "__main__":
    main()
