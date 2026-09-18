#!/usr/bin/env python3
"""Generate real TinyStories CSS output-head architecture benchmarks."""

from __future__ import annotations

import argparse
import html
import importlib.util
import io
import json
import math
import pickle
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tinystories-gpt2-3M"
OUT = ROOT / "output-head-benchmark" / "generated"
MODEL_URL = (
    "https://huggingface.co/calum/tinystories-gpt2-3M/resolve/main/"
    "pytorch_model.bin"
)
PROMPTS = ["Once upon a time", "The little girl", "One day"]
EPSILON = 1e-5
LAYOUT_SCALE = 4096


def load_builder_module() -> object:
    path = ROOT / "tools" / "build_pretrained_gpt2.py"
    spec = importlib.util.spec_from_file_location("tiny_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder_module()


def download_checkpoint() -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    destination = DATA / "pytorch_model.bin"
    if not destination.exists():
        print("downloading TinyStories checkpoint...")
        urllib.request.urlretrieve(MODEL_URL, destination)
    return destination


def load_torch_zip(path: Path) -> dict[str, np.ndarray]:
    formats = {
        "FloatStorage": "<f4",
        "DoubleStorage": "<f8",
        "LongStorage": "<i8",
        "IntStorage": "<i4",
        "ShortStorage": "<i2",
        "ByteStorage": "u1",
        "CharStorage": "i1",
        "BoolStorage": "?",
    }
    storages: dict[str, object] = {}
    with zipfile.ZipFile(path) as archive:
        prefix = archive.namelist()[0].split("/")[0]
        with archive.open(f"{prefix}/data.pkl") as payload:
            state = BUILDER.TorchLegacyUnpickler(payload, storages).load()
        for key, storage in storages.items():
            storage.data = np.frombuffer(
                archive.read(f"{prefix}/data/{key}"),
                dtype=formats[storage.storage_type],
            )
    return {name: tensor.array() for name, tensor in state.items()}


def layer_norm(vector: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    centered = vector - vector.mean(axis=-1, keepdims=True)
    variance = (centered * centered).mean(axis=-1, keepdims=True)
    return centered / np.sqrt(variance + EPSILON) * gamma + beta


def gelu_new(vector: np.ndarray) -> np.ndarray:
    return 0.5 * vector * (
        1 + np.tanh(np.sqrt(2 / np.pi) * (vector + 0.044715 * vector**3))
    )


def final_hidden(token_ids: list[int], state: dict[str, np.ndarray]) -> np.ndarray:
    embeddings = state["transformer.wte.weight"]
    length = len(token_ids)
    width = embeddings.shape[1]
    heads = 16
    head_width = width // heads
    x = embeddings[token_ids] + state["transformer.wpe.weight"][:length]
    for layer in range(8):
        prefix = f"transformer.h.{layer}"
        normalized = layer_norm(
            x,
            state[f"{prefix}.ln_1.weight"],
            state[f"{prefix}.ln_1.bias"],
        )
        qkv = (
            normalized @ state[f"{prefix}.attn.c_attn.weight"]
            + state[f"{prefix}.attn.c_attn.bias"]
        )
        query, key, value = [
            part.reshape(length, heads, head_width)
            for part in np.split(qkv, 3, axis=1)
        ]
        attended = np.zeros_like(query)
        for position in range(length):
            for head in range(heads):
                scores = (
                    key[: position + 1, head] @ query[position, head]
                    / math.sqrt(head_width)
                )
                probabilities = np.exp(scores - scores.max())
                probabilities /= probabilities.sum()
                attended[position, head] = (
                    probabilities @ value[: position + 1, head]
                )
        attended = attended.reshape(length, width)
        x = (
            x
            + attended @ state[f"{prefix}.attn.c_proj.weight"]
            + state[f"{prefix}.attn.c_proj.bias"]
        )
        normalized = layer_norm(
            x,
            state[f"{prefix}.ln_2.weight"],
            state[f"{prefix}.ln_2.bias"],
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
    return layer_norm(
        x[-1], state["transformer.ln_f.weight"], state["transformer.ln_f.bias"]
    )


def css_number(value: float) -> str:
    return BUILDER.css_number(float(value))


def property_registration(name: str) -> str:
    return (
        f'@property --{name}{{syntax:"<number>";inherits:false;initial-value:0}}'
    )


def reduce_properties(
    declarations: list[str], registrations: list[str], names: list[str], operation: str
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
            name = f"r{operation[0]}{depth}x{group_index}"
            registrations.append(property_registration(name))
            references = [f"var(--{item})" for item in group]
            expression = (
                f"max({','.join(references)})"
                if operation == "max"
                else f"calc({' + '.join(references)})"
            )
            declarations.append(f"--{name}:{expression};")
            next_level.append(name)
        level = next_level
        depth += 1
    return level[0]


def query_rules(hidden_vectors: np.ndarray) -> str:
    lines = []
    for query, vector in enumerate(hidden_vectors):
        declarations = ";".join(
            f"--h{dimension}:{css_number(value)}"
            for dimension, value in enumerate(vector)
        )
        lines.append(f"body:has(#q{query}:checked) .model{{{declarations}}}")
    return "\n".join(lines)


def benchmark_script(
    variant: str,
    scale: int,
    winners: list[int],
    maximums: list[float],
    winner_embeddings: list[list[float]],
    benchmark_h0: float,
    floor: float,
) -> str:
    rounds = 40 if scale <= 256 else 12 if scale <= 4096 else 4
    expected_rows = json.dumps(winners)
    expected_maximums = json.dumps(maximums)
    if variant.startswith("property"):
        read_result = """
        const styles = getComputedStyle(model);
        const maximum = Number.parseFloat(styles.getPropertyValue('--maximum'));
        const winnerId = Number.parseFloat(styles.getPropertyValue('--winner-id'));
        const embedding = feedback
          ? Array.from({length: 64}, (_, dimension) =>
              Number.parseFloat(styles.getPropertyValue(`--next-${dimension}`)))
          : [];
        """
        correctness = """
        const winnerCorrect = feedback ? winnerId === expectedWinners[index] : true;
        const embeddingError = feedback
          ? Math.max(...embedding.map((value, dimension) =>
              Math.abs(value - expectedEmbeddings[index][dimension])))
          : 0;
        return { elapsed: performance.now() - started, maximum, winnerCorrect, embeddingError };
        """
    else:
        read_result = f"""
        const width = stage.getBoundingClientRect().width;
        const maximum = width / {LAYOUT_SCALE} + layoutFloor;
        const expectedWidth = expectedElements[index].getBoundingClientRect().width;
        """
        correctness = """
        return {
          elapsed: performance.now() - started,
          maximum,
          winnerCorrect: Math.abs(width - expectedWidth) < 0.000001,
          embeddingError: 0,
        };
        """
    return f"""
  <script>
    const scriptStartMilliseconds = performance.now();
    const variant = {json.dumps(variant)};
    const feedback = variant === 'property-feedback';
    const rounds = {rounds};
    const expectedWinners = {expected_rows};
    const expectedMaximums = {expected_maximums};
    const expectedEmbeddings = {json.dumps(winner_embeddings)};
    const benchmarkH0 = {benchmark_h0!r};
    const layoutFloor = {floor!r};
    const inputs = [...document.querySelectorAll('input[name="query"]')];
    const model = document.querySelector('.model');
    const stage = document.querySelector('.stage');
    const expectedElements = stage
      ? expectedWinners.map(token => stage.querySelector(`[data-token="${{token}}"]`))
      : [];

    function infer(index, perturbation = null) {{
      const started = performance.now();
      inputs[index].checked = true;
      if (perturbation === null) {{
        model.style.removeProperty('--h0');
      }} else {{
        model.style.setProperty('--h0', String(benchmarkH0 + perturbation));
      }}
{read_result}
{correctness}
    }}

    requestAnimationFrame(() => requestAnimationFrame(() => {{
      let maximumError = 0;
      let wrongWinners = 0;
      let embeddingError = 0;
      for (let query = 0; query < inputs.length; query += 1) {{
        const result = infer(query);
        maximumError = Math.max(
          maximumError,
          Math.abs(result.maximum - expectedMaximums[query]),
        );
        wrongWinners += result.winnerCorrect ? 0 : 1;
        embeddingError = Math.max(embeddingError, result.embeddingError);
      }}
      infer(0, 0.000001);
      infer(0, 0.000002);
      const samples = [];
      for (let iteration = 0; iteration < rounds; iteration += 1) {{
        const result = infer(0, (iteration + 10) * 0.000001);
        samples.push(result.elapsed);
      }}
      samples.sort((a, b) => a - b);
      const navigation = performance.getEntriesByType('navigation')[0]?.toJSON();
      const result = {{
        variant,
        scale: {scale},
        rounds,
        meanMilliseconds: samples.reduce((sum, value) => sum + value, 0) / rounds,
        medianMilliseconds: samples[Math.floor(samples.length / 2)],
        p95Milliseconds: samples[Math.floor(samples.length * 0.95)],
        maximumError,
        wrongWinners,
        embeddingError,
        scriptStartMilliseconds,
        navigation,
      }};
      document.querySelector('#results').textContent = JSON.stringify(result, null, 2);
      document.documentElement.dataset.benchmarkComplete = 'true';
    }}));
  </script>"""


def page_shell(
    variant: str,
    scale: int,
    body: str,
    script: str,
    stylesheet: str,
) -> str:
    controls = "".join(
        f'<input type="radio" name="query" id="q{index}"'
        f'{" checked" if index == 0 else ""}>'
        for index in range(len(PROMPTS))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(variant)} · {scale:,} TinyStories rows</title>
  <link rel="stylesheet" href="{stylesheet}?v=output-head-3">
</head>
<body>
  {controls}
  {body}
  <pre id="results">running...</pre>
{script}
</body>
</html>
"""


def build_property_variant(
    embeddings: np.ndarray,
    hidden_vectors: np.ndarray,
    winners: list[int],
    maximums: list[float],
    scale: int,
    feedback: bool,
) -> None:
    variant = "property-feedback" if feedback else "property"
    registrations: list[str] = []
    declarations: list[str] = []
    logit_names = []
    for token, embedding in enumerate(embeddings):
        name = f"l{token}"
        logit_names.append(name)
        registrations.append(property_registration(name))
        terms = [
            f"var(--h{dimension})*{css_number(weight)}"
            for dimension, weight in enumerate(embedding)
        ]
        declarations.append(f"--{name}:calc({' + '.join(terms)});")
    maximum_name = reduce_properties(
        declarations, registrations, logit_names, "max"
    )
    registrations.append(property_registration("maximum"))
    declarations.append(f"--maximum:var(--{maximum_name});")

    if feedback:
        indicator_names = []
        for token in range(scale):
            difference = f"d{token}"
            indicator = f"i{token}"
            registrations.append(property_registration(difference))
            registrations.append(property_registration(indicator))
            declarations.append(
                f"--{difference}:calc(abs(var(--l{token}) - var(--maximum)));"
            )
            declarations.append(
                f"--{indicator}:calc(1 - max(0,sign(var(--{difference}) - .000001)));"
            )
            indicator_names.append(indicator)
        registrations.append(property_registration("winner-id"))
        winner_terms = []
        for token, indicator in enumerate(indicator_names):
            term = f"t{token}"
            registrations.append(property_registration(term))
            declarations.append(f"--{term}:calc(var(--{indicator})*{token});")
            winner_terms.append(term)
        winner_sum = reduce_properties(
            declarations, registrations, winner_terms, "sum"
        )
        declarations.append(f"--winner-id:var(--{winner_sum});")
        for dimension in range(embeddings.shape[1]):
            registrations.append(property_registration(f"next-{dimension}"))
            terms = [
                f"var(--i{token})*{css_number(embeddings[token, dimension])}"
                for token in range(scale)
            ]
            declarations.append(
                f"--next-{dimension}:calc({' + '.join(terms)});"
            )
    else:
        registrations.append(property_registration("winner-id"))
        declarations.append("--winner-id:0;")

    rules = [query_rules(hidden_vectors)]
    for start in range(0, len(declarations), 1000):
        rules.append(".model{" + "".join(declarations[start : start + 1000]) + "}")
    filename = f"{variant}-{scale}"
    css = "\n".join(registrations + rules) + "\n"
    (OUT / f"{filename}.css").write_text(css)
    winner_embeddings = [embeddings[token].astype(float).tolist() for token in winners]
    script = benchmark_script(
        variant,
        scale,
        winners,
        maximums,
        winner_embeddings,
        float(hidden_vectors[0, 0]),
        0,
    )
    page = page_shell(
        variant,
        scale,
        '<main class="model"></main>',
        script,
        f"{filename}.css",
    )
    (OUT / f"{filename}.html").write_text(page)


def build_dom_variant(
    embeddings: np.ndarray,
    hidden_vectors: np.ndarray,
    winners: list[int],
    maximums: list[float],
    minimum: float,
    scale: int,
) -> None:
    variant = "dom-layout"
    floor = math.floor(minimum) - 1
    attributes = []
    for token, embedding in enumerate(embeddings):
        weights = " ".join(
            f"a{dimension}={css_number(weight)}"
            for dimension, weight in enumerate(embedding)
        )
        attributes.append(
            f'<i class="candidate" data-token="{token}" {weights}></i>'
        )
    dot_terms = [
        f"var(--h{dimension})*attr(a{dimension} type(<number>))"
        for dimension in range(embeddings.shape[1])
    ]
    css = "\n".join(
        [
            property_registration("score"),
            query_rules(hidden_vectors),
            "body{margin:0}",
            ".model{position:absolute;inset:0}",
            ".stage{display:inline-grid;position:absolute;inline-size:max-content}",
            ".candidate{grid-area:1/1;display:block;block-size:0;overflow:hidden;"
            f"--score:calc({' + '.join(dot_terms)});"
            f"inline-size:max(0px,calc((var(--score) - {floor}) * {LAYOUT_SCALE}px))}}",
        ]
    )
    filename = f"{variant}-{scale}"
    (OUT / f"{filename}.css").write_text(css + "\n")
    body = '<main class="model"><div class="stage">' + "".join(attributes) + "</div></main>"
    winner_embeddings = [embeddings[token].astype(float).tolist() for token in winners]
    script = benchmark_script(
        variant,
        scale,
        winners,
        maximums,
        winner_embeddings,
        float(hidden_vectors[0, 0]),
        floor,
    )
    page = page_shell(
        variant,
        scale,
        body,
        script,
        f"{filename}.css",
    )
    (OUT / f"{filename}.html").write_text(page)


def build_if_laziness_page(
    hidden_vectors: np.ndarray,
    maximums: list[float],
    scale: int,
) -> None:
    h0 = float(hidden_vectors[0, 0])
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CSS if() laziness · {scale:,} rows</title>
  <link rel="stylesheet" href="property-{scale}.css?v=output-head-3">
  <style>
    @property --mode {{ syntax: "<integer>"; inherits: false; initial-value: 0; }}
    @property --selected {{ syntax: "<number>"; inherits: false; initial-value: 0; }}
    .model {{
      --mode: 0;
      --selected: if(style(--mode: 0): 1; else: var(--maximum));
    }}
  </style>
</head>
<body>
  <input type="radio" name="query" id="q0" checked>
  <input type="radio" name="query" id="q1">
  <input type="radio" name="query" id="q2">
  <main class="model"></main>
  <pre id="results">running...</pre>
  <script>
    const model = document.querySelector('.model');
    const h0 = {h0!r};
    const expectedMaximum = {maximums[0]!r};

    function infer(mode, iteration) {{
      const started = performance.now();
      model.style.setProperty('--mode', String(mode));
      model.style.setProperty('--h0', String(h0 + iteration * 0.000001));
      const value = Number.parseFloat(
        getComputedStyle(model).getPropertyValue('--selected')
      );
      return {{ elapsed: performance.now() - started, value }};
    }}

    requestAnimationFrame(() => requestAnimationFrame(() => {{
      infer(0, 1);
      infer(1, 2);
      const cheap = [];
      const expensive = [];
      for (let iteration = 10; iteration < 14; iteration += 1) {{
        cheap.push(infer(0, iteration).elapsed);
        expensive.push(infer(1, iteration + 10).elapsed);
      }}
      const result = {{
        scale: {scale},
        cheapMilliseconds: cheap,
        expensiveMilliseconds: expensive,
        cheapMedian: cheap.sort((a, b) => a - b)[2],
        expensiveMedian: expensive.sort((a, b) => a - b)[2],
        cheapValue: infer(0, 30).value,
        expensiveValue: infer(1, 31).value,
        referenceMaximum: expectedMaximum,
      }};
      document.querySelector('#results').textContent = JSON.stringify(result, null, 2);
      document.documentElement.dataset.benchmarkComplete = 'true';
    }}));
  </script>
</body>
</html>
"""
    (OUT / f"if-lazy-{scale}.html").write_text(document)


def build_function_laziness_page(
    embeddings: np.ndarray,
    hidden_vectors: np.ndarray,
    maximums: list[float],
    scale: int,
) -> None:
    declarations = []
    level = []
    for token, embedding in enumerate(embeddings):
        name = f"l{token}"
        level.append(name)
        terms = [
            f"var(--x{dimension})*{css_number(weight)}"
            for dimension, weight in enumerate(embedding)
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
    arguments = ",".join(
        f"--x{dimension} <number>" for dimension in range(embeddings.shape[1])
    )
    invocation = ",".join(
        f"var(--h{dimension})" for dimension in range(embeddings.shape[1])
    )
    css = "\n".join(
        [
            f"@function --head({arguments}) returns <number>{{",
            *declarations,
            f"result:var(--{level[0]});",
            "}",
            '@property --mode{syntax:"<integer>";inherits:false;initial-value:0}',
            '@property --selected{syntax:"<number>";inherits:false;initial-value:0}',
            query_rules(hidden_vectors),
            ".model{--mode:0;"
            f"--selected:if(style(--mode:0):1;else:--head({invocation}))}}",
        ]
    )
    filename = f"function-if-lazy-{scale}"
    (OUT / f"{filename}.css").write_text(css + "\n")
    h0 = float(hidden_vectors[0, 0])
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CSS function if() laziness · {scale:,} rows</title>
  <link rel="stylesheet" href="{filename}.css?v=output-head-function-1">
</head>
<body>
  <input type="radio" name="query" id="q0" checked>
  <input type="radio" name="query" id="q1">
  <input type="radio" name="query" id="q2">
  <main class="model"></main>
  <pre id="results">running...</pre>
  <script>
    const model = document.querySelector('.model');
    const h0 = {h0!r};
    const referenceMaximum = {maximums[0]!r};
    function infer(mode, iteration) {{
      const started = performance.now();
      model.style.setProperty('--mode', String(mode));
      model.style.setProperty('--h0', String(h0 + iteration * 0.000001));
      const value = Number.parseFloat(
        getComputedStyle(model).getPropertyValue('--selected')
      );
      return {{ elapsed: performance.now() - started, value }};
    }}
    requestAnimationFrame(() => requestAnimationFrame(() => {{
      infer(0, 1);
      infer(1, 2);
      const cheap = [];
      const expensive = [];
      for (let iteration = 10; iteration < 14; iteration += 1) {{
        cheap.push(infer(0, iteration).elapsed);
        expensive.push(infer(1, iteration + 10).elapsed);
      }}
      cheap.sort((a, b) => a - b);
      expensive.sort((a, b) => a - b);
      const result = {{
        scale: {scale},
        cheapMilliseconds: cheap,
        expensiveMilliseconds: expensive,
        cheapMedian: cheap[2],
        expensiveMedian: expensive[2],
        cheapValue: infer(0, 30).value,
        expensiveValue: infer(1, 31).value,
        referenceMaximum,
      }};
      document.querySelector('#results').textContent = JSON.stringify(result, null, 2);
      document.documentElement.dataset.benchmarkComplete = 'true';
    }}));
  </script>
</body>
</html>
"""
    (OUT / f"{filename}.html").write_text(document)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scales", nargs="+", type=int, default=[256, 4096, 50257]
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=["property", "property-feedback", "dom-layout"],
        default=["property", "property-feedback", "dom-layout"],
    )
    arguments = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    state = load_torch_zip(download_checkpoint())
    tokenizer = BUILDER.Gpt2Tokenizer(
        ROOT / "data" / "tiny-gpt2" / "vocab.json",
        ROOT / "data" / "tiny-gpt2" / "merges.txt",
    )
    hidden_vectors = np.stack(
        [final_hidden(tokenizer.encode(prompt), state) for prompt in PROMPTS]
    )
    all_embeddings = state["transformer.wte.weight"]
    metadata = {"prompts": PROMPTS, "benchmarks": []}
    for scale in arguments.scales:
        if not 1 <= scale <= len(all_embeddings):
            raise ValueError(f"invalid scale {scale}")
        embeddings = all_embeddings[:scale]
        logits = hidden_vectors @ embeddings.T
        winners = logits.argmax(axis=1).astype(int).tolist()
        maximums = logits.max(axis=1).astype(float).tolist()
        minimum = float(logits.min())
        print(f"scale {scale:,}: winners {winners}")
        for variant in arguments.variants:
            print(f"  building {variant}...")
            if variant == "property":
                build_property_variant(
                    embeddings,
                    hidden_vectors,
                    winners,
                    maximums,
                    scale,
                    False,
                )
                build_if_laziness_page(hidden_vectors, maximums, scale)
                build_function_laziness_page(
                    embeddings, hidden_vectors, maximums, scale
                )
            elif variant == "property-feedback":
                build_property_variant(
                    embeddings,
                    hidden_vectors,
                    winners,
                    maximums,
                    scale,
                    True,
                )
            else:
                build_dom_variant(
                    embeddings,
                    hidden_vectors,
                    winners,
                    maximums,
                    minimum,
                    scale,
                )
            stem = f"{variant}-{scale}"
            metadata["benchmarks"].append(
                {
                    "variant": variant,
                    "scale": scale,
                    "html": f"{stem}.html",
                    "css": f"{stem}.css",
                    "winners": winners,
                    "maximums": maximums,
                }
            )
    (OUT / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"wrote benchmarks to {OUT}")


if __name__ == "__main__":
    main()
