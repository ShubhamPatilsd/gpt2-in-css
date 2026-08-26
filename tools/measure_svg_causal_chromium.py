#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy==2.5.3", "pillow", "fonttools", "tokenizers==0.22.2"]
# ///
"""Real Chromium, connected causal SVG core; Python-only compiler and scorer.

All 12 transformer blocks, including QK, causal softmax, V, residuals and
nonlinearities execute as SVG filters. Python supplies token/position embeddings,
captures pixels and scores the final vector with the SAME FP32 vocabulary head
as the reference. This isolates core quality; it is not autonomous decoding or
a browser output-head/whole-pipeline latency claim. No intermediate injection.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

import build_svg_filter_full_block as svg
from build_signed_hvar_chain import quantize_float_rows
from evaluate_gpt2_quantization_quality import Model, load_model, metrics, metric_summary, sha256
from profile_hybrid_twelve_block import browser, query

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "experiments/svg-causal-chromium-quality"
C = 128 / 255


def trace_hidden(model, ids):
    trace = {}
    original = model.surface

    def observe(name, value, valid=None):
        trace[name] = value.copy()
        return original(name, value, valid)

    model.surface = observe
    try:
        hidden, _ = model.hidden([ids])
    finally:
        model.surface = original
    return hidden[0], trace


def train_calibration(model, manifest, samples=256):
    parts = defaultdict(list)
    per_window = max(1, samples // len(manifest["calibration"]))
    for row in manifest["calibration"]:
        _, trace = trace_hidden(model, row["tokens"][:-1])
        indices = np.linspace(0, len(row["tokens"]) - 2, per_window, dtype=int)
        for name, value in trace.items():
            if name.endswith(".scores"):
                # surface() receives B,T,T,H scores, before causal masking.
                length = value.shape[1]
                valid = np.tril(np.ones((length, length), bool))
                parts[name].append(np.abs(value[0][valid]).max(axis=0)[None])
            else:
                parts[name].append(value[0, indices])
    return {name: np.concatenate(values).astype(np.float64) for name, values in parts.items()}


def png_uri(pixels):
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def bounded_primitives(primitives):
    """Constrain each intermediate to its known pixel support.

    In particular an opaque-alpha color matrix must not expand a one-pixel
    scalar to the full 3072x3072 filter region before a merge or feTile.
    """
    bounds = {"SourceGraphic": (0, 0, 3072, 3072)}
    output = []
    for primitive in primitives:
        element = ET.fromstring(primitive)
        attrs = element.attrib
        sources = [attrs[key] for key in ("in", "in2") if key in attrs]
        sources += [child.attrib["in"] for child in element if child.tag == "feMergeNode"]
        rectangles = [bounds[name] for name in sources if name in bounds]
        if rectangles:
            left = min(r[0] for r in rectangles)
            top = min(r[1] for r in rectangles)
            right = max(r[0] + r[2] for r in rectangles)
            bottom = max(r[1] + r[3] for r in rectangles)
            inferred = (left, top, right - left, bottom - top)
        else:
            inferred = (0, 0, 3072, 3072)
        rectangle = tuple(float(attrs.get(key, inferred[i])) for i, key in enumerate(("x", "y", "width", "height")))
        for key, value in zip(("x", "y", "width", "height"), rectangle):
            attrs[key] = f"{value:g}"
        if "result" in attrs:
            bounds[attrs["result"]] = rectangle
        output.append(ET.tostring(element, encoding="unicode"))
    return output


class Compiler:
    def __init__(self, directory, calibration, checkpoint, context, blocks=12):
        self.directory = directory
        self.cal = calibration
        self.checkpoint = checkpoint
        self.context = context
        self.blocks = blocks
        self.p = []
        self.outputs = []
        self.stages = []
        directory.mkdir(parents=True, exist_ok=True)
        svg.OUT = directory
        os.environ["SVG_FILTER_PACKED_GELU"] = "1"
        os.environ["SVG_FILTER_GELU_BUCKETS"] = "32"
        os.environ["SVG_FILTER_BUCKET_HEADROOM"] = "1.1"
        self.h = {}
        svg.main(self.h)
        self.asset_hashes = {}

    def template(self, function, *args, **kwargs):
        begin = len(self.h["primitives"])
        value = self.h[function](*args, **kwargs)
        markup = self.h["primitives"][begin:]
        del self.h["primitives"][begin:]
        return markup, value

    def instantiate(self, template, prefix, inputs):
        markup, value = template
        names = {match for primitive in markup for match in re.findall(r'result="([^"]+)"', primitive)}
        mapping = {name: prefix + name for name in names}
        mapping.update(inputs)

        def rename(match):
            kind, name = match.groups()
            return f' {kind}="{mapping.get(name, name)}"'

        self.p.extend(re.sub(r' (in|in2|result)="([^"]+)"', rename, primitive) for primitive in markup)
        return mapping[value[0]]

    def matrix(self, name, input_cal, input_spec, weight, bias, orientation):
        quantized = quantize_float_rows(weight.T, bits=9).reconstructed
        return self.template("bucketed_matrix_stage", "IN", input_cal[0], input_cal,
                             input_spec, quantized, bias, orientation, name)

    def ln(self, name, values, spec, gamma, beta):
        return self.template("scaled_layernorm_stage", "IN", values[0], values,
                             spec, gamma, beta, "h", name)

    def add(self, name, left, left_spec, right, right_spec):
        return self.template("bucketed_add_stage", "IN", left[0], left, left_spec,
                             "SKIP", right[0], right, right_spec, "h", name)

    def image(self, name, values, x=0, y=0):
        path = self.directory / f"{name}.png"
        svg.save_gray(path, np.asarray(values))
        height, width = values.shape
        self.p.append(f'<feImage href="{path.name}" x="{x}" y="{y}" width="{width}" height="{height}" preserveAspectRatio="none" result="{name}"/>')
        return name

    def color(self, source, name, coefficients):
        self.p.append(f'<feColorMatrix in="{source}" values="{coefficients}" result="{name}"/>')
        return name

    def arithmetic(self, a, b, name, k1=0, k2=1, k3=1, k4=0, region=""):
        self.p.append(f'<feComposite in="{a}" in2="{b}" operator="arithmetic" k1="{k1}" k2="{k2}" k3="{k3}" k4="{k4}" {region} result="{name}"/>')
        return name

    def offset(self, source, name, dx=0, dy=0, x=0, y=0, width=1, height=1):
        self.p.append(f'<feOffset in="{source}" dx="{dx}" dy="{dy}" x="{x}" y="{y}" width="{width}" height="{height}" result="{name}"/>')
        return name

    def split(self, source, name):
        markup, value = self.template("split_signed", source, name)
        self.p.extend(markup)
        return value

    def table(self, source, name, values, width, height):
        table = " ".join(f"{v:.10g}" for v in values)
        self.p.append(f'<feComponentTransfer in="{source}" x="0" y="0" width="{width}" height="{height}" result="{name}">'
                      + "".join(f'<feFunc{channel} type="table" tableValues="{table}"/>' for channel in "RGB")
                      + '<feFuncA type="identity"/></feComponentTransfer>')
        return name

    def merge(self, sources, name):
        self.p.append(f'<feMerge result="{name}">' + "".join(f'<feMergeNode in="{s}"/>' for s in sources) + '</feMerge>')
        return name

    def stage(self, name, start, inputs, outputs, scales):
        primitives = [f'<feOffset in="SourceGraphic" dy="{255 - t}" x="0" y="255" width="768" height="1" result="{source}"/>' for t, source in enumerate(inputs)]
        primitives += self.p[start:]
        sources = []
        for t, source in enumerate(outputs):
            sources.append(f"{name}-display{t}")
            primitives.append(f'<feOffset in="{source}" dy="{t - 255}" x="0" y="{t}" width="768" height="1" result="{sources[-1]}"/>')
        primitives.append('<feMerge result="display">' + "".join(f'<feMergeNode in="{s}"/>' for s in sources) + '</feMerge>')
        self.stages.append({"name": name, "primitives": primitives, "scales": np.asarray(scales).tolist()})

    def attention(self, layer, qkv_sources, spec):
        """True causal QK/softmax/V, not fixed/reference attention weights."""
        scale = spec["scales"]
        context_sources = [[] for _ in range(self.context)]
        for head in range(12):
            prefix = f"a{layer}h{head}"
            tensors = {}
            for token, source in enumerate(qkv_sources):
                for part, base in (("q", 0), ("k", 768), ("v", 1536)):
                    name = f"{prefix}t{token}{part}"
                    crop = self.offset(source, name, dx=-255, dy=-(base + head * 64), height=64)
                    tensors[token, part] = self.split(crop, name)
            product_scales = scale[head * 64:(head + 1) * 64] * scale[768 + head * 64:768 + (head + 1) * 64] / 8
            unit = float(product_scales.max())
            weight_image = self.image(f"{prefix}-qk-scales", (product_scales / unit)[:, None])
            qkv = self.cal[f"b{layer}.qkv"]
            q = qkv[:, head * 64:(head + 1) * 64]
            k = qkv[:, 768 + head * 64:768 + (head + 1) * 64]
            signed = q @ k.T / 8
            absolute = np.abs(q) @ np.abs(k).T / 8
            magnitude = max(float(np.max((absolute + np.abs(signed)) / 2)) * 1.15, .01)
            score_range = max(float(self.cal[f"b{layer}.scores"][:, head].max()) * 1.15, .1)
            for target in range(self.context):
                scores = []
                for source in range(target + 1):
                    name = f"{prefix}t{target}s{source}"
                    query, key = tensors[target, "q"], tensors[source, "k"]
                    swapped = self.color(key, name + "-swap", self.h["swap_rg"])
                    same = self.arithmetic(query, key, name + "-same", k1=1, k2=0, k3=0)
                    cross = self.arithmetic(query, swapped, name + "-cross", k1=1, k2=0, k3=0)
                    pos = self.color(same, name + "-pos", self.h["positive_matrix"])
                    neg = self.color(cross, name + "-neg", self.h["negative_matrix"])
                    rg = self.arithmetic(pos, neg, name + "-rg")
                    scaled = self.arithmetic(rg, weight_image, name + "-scaled", k1=1, k2=0, k3=0)
                    total = name + "-sum"
                    self.p.append(f'<feConvolveMatrix in="{scaled}" order="1 64" kernelMatrix="{" ".join(["1"] * 64)}" divisor="{magnitude / unit}" targetX="0" targetY="63" edgeMode="none" preserveAlpha="true" x="0" y="63" width="1" height="1" result="{total}"/>')
                    coefficient = magnitude / (2 * score_range)
                    common = self.color(total, name + "-common", f"{coefficient} {-coefficient} 0 0 {C} " * 3 + "0 0 0 0 1")
                    scores.append(self.offset(common, name + "-score", dx=source, dy=-63, x=source))
                name = f"{prefix}t{target}"
                count = target + 1
                row = self.merge(scores, name + "-scores")
                maximum = name + "-max"
                self.p.append(f'<feMorphology in="{row}" operator="dilate" radius="{target} 0" x="0" y="0" width="{count}" height="1" result="{maximum}"/>')
                shifted = self.arithmetic(row, maximum, name + "-shifted", k3=-1, k4=1, region=f'x="0" y="0" width="{count}" height="1"')
                exponential = self.table(shifted, name + "-exp", np.exp((np.linspace(0, 1, 256) - 1) * 2 * score_range), count, 1)
                denominator = name + "-mean"
                self.p.append(f'<feConvolveMatrix in="{exponential}" order="{count} 1" kernelMatrix="{" ".join(["1"] * count)}" divisor="{count}" targetX="{target}" targetY="0" edgeMode="none" preserveAlpha="true" x="{target}" y="0" width="1" height="1" result="{denominator}"/>')
                denominator = self.offset(denominator, name + "-mean-origin", dx=-target)
                inverse = self.table(denominator, name + "-inverse", np.minimum(1, 1 / np.maximum(np.linspace(0, 1, 256) * count, 1e-8)), 1, 1)
                parts = []
                for source in range(count):
                    probability = self.offset(exponential, f"{name}s{source}-exp-origin", dx=-source)
                    probability = self.arithmetic(probability, inverse, f"{name}s{source}-probability", k1=1, k2=0, k3=0)
                    tiled = f"{name}s{source}-broadcast"
                    self.p.append(f'<feTile in="{probability}" x="0" y="0" width="1" height="64" result="{tiled}"/>')
                    parts.append(self.arithmetic(tensors[source, "v"], tiled, f"{name}s{source}-pv", k1=1, k2=0, k3=0))
                context = parts[0]
                for i, part in enumerate(parts[1:], 1):
                    context = self.arithmetic(context, part, name + f"-context{i}")
                common = self.color(context, name + "-context-common", self.h["signed_to_common"])
                context_sources[target].append(self.offset(common, name + "-context-placed", dx=255, dy=head * 64, x=255, y=head * 64, height=64))
        return [self.merge(parts, f"a{layer}t{t}-context") for t, parts in enumerate(context_sources)], {
            "scales": scale[1536:], "ids": spec["ids"][1536:], "group_scales": spec["group_scales"]
        }

    def build(self):
        cal = self.cal
        input_spec = self.h["bucket_spec"](cal["input"][0], cal["input"])
        svg.save_gray(self.directory / "input.png", C + cal["input"][:self.context] / (2 * input_spec["scales"]))
        self.p.append(f'<feImage id="live-input" href="input.png" x="0" y="0" width="768" height="{self.context}" preserveAspectRatio="none" result="input-atlas"/>')
        state = [self.offset("input-atlas", f"t{t}-input", dy=255 - t, x=0, y=255, width=768) for t in range(self.context)]
        spec = input_spec
        for layer, block in enumerate(self.checkpoint[2][:self.blocks]):
            begin = time.perf_counter()
            stage_start = len(self.p)
            stage_input = state[:]
            prefix = f"b{layer}"
            incoming = cal["input" if layer == 0 else f"b{layer - 1}.residual2"]
            template = self.ln(prefix + "-ln1", incoming, spec, block.ln1_gamma, block.ln1_beta)
            normalized = [self.instantiate(template, f"t{t}-", {"IN": state[t]}) for t in range(self.context)]
            ln_spec = template[1][-1]
            template = self.matrix(prefix + "-qkv", cal[prefix + ".ln1"], ln_spec, block.qkv_weight, block.qkv_bias, "h")
            qkv = [self.instantiate(template, f"t{t}-", {"IN": normalized[t]}) for t in range(self.context)]
            context, context_spec = self.attention(layer, qkv, template[1][-1])
            template = self.matrix(prefix + "-attn", cal[prefix + ".context"], context_spec, block.attention_projection_weight, block.attention_projection_bias, "v")
            learned = [self.instantiate(template, f"t{t}-", {"IN": context[t]}) for t in range(self.context)]
            template = self.add(prefix + "-residual1", cal[prefix + ".attention"], template[1][-1], incoming, spec)
            state = [self.instantiate(template, f"t{t}-", {"IN": learned[t], "SKIP": state[t]}) for t in range(self.context)]
            spec = template[1][-1]
            template = self.ln(prefix + "-ln2", cal[prefix + ".residual1"], spec, block.ln2_gamma, block.ln2_beta)
            normalized = [self.instantiate(template, f"t{t}-", {"IN": state[t]}) for t in range(self.context)]
            template = self.matrix(prefix + "-fc", cal[prefix + ".ln2"], template[1][-1], block.fc_weight, block.fc_bias, "h")
            pre = [self.instantiate(template, f"t{t}-", {"IN": normalized[t]}) for t in range(self.context)]
            template = self.template("bucketed_gelu_stage", "IN", cal[prefix + ".fc"][0], cal[prefix + ".fc"], template[1][-1], "v", prefix + "-gelu")
            hidden = [self.instantiate(template, f"t{t}-", {"IN": pre[t]}) for t in range(self.context)]
            template = self.matrix(prefix + "-proj", cal[prefix + ".gelu"], template[1][-1], block.mlp_projection_weight, block.mlp_projection_bias, "v")
            projected = [self.instantiate(template, f"t{t}-", {"IN": hidden[t]}) for t in range(self.context)]
            template = self.add(prefix + "-residual2", cal[prefix + ".projection"], template[1][-1], cal[prefix + ".residual1"], spec)
            state = [self.instantiate(template, f"t{t}-", {"IN": projected[t], "SKIP": state[t]}) for t in range(self.context)]
            spec = template[1][-1]
            self.outputs.append((prefix + ".residual2", state[:], spec["scales"].tolist()))
            self.stage(prefix, stage_start, stage_input, state, spec["scales"])
            print(f"Compiled causal SVG block {layer + 1}/{self.blocks}: {time.perf_counter() - begin:.2f}s", flush=True)
        final_cal = cal[f"b{self.blocks - 1}.residual2"]
        stage_start = len(self.p)
        template = self.ln("final-ln", final_cal, spec, self.checkpoint[3], self.checkpoint[4])
        final = [self.instantiate(template, f"t{t}-", {"IN": state[t]}) for t in range(self.context)]
        self.outputs.append(("final", final, template[1][-1]["scales"].tolist()))
        self.stage("final", stage_start, state, final, template[1][-1]["scales"])
        displays = []
        for group, (_, sources, _) in enumerate(self.outputs):
            for token, source in enumerate(sources):
                row = group * self.context + token
                displays.append(self.offset(source, f"output-{row}", dy=row - 255, x=0, y=row, width=768))
        echo_row = len(self.outputs) * self.context
        displays.append(self.offset("input-atlas", "input-echo", dy=echo_row, x=0, y=echo_row, width=768, height=self.context))
        self.merge(displays, "display")
        height = (len(self.outputs) + 1) * self.context
        html = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'; object-src \'none\'">'
                '<style>html,body{margin:0;background:magenta}svg{display:block;image-rendering:pixelated}</style>'
                f'<svg width="768" height="{height}" xmlns="http://www.w3.org/2000/svg"><defs>'
                '<filter id="core" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" x="0" y="0" width="3072" height="3072" color-interpolation-filters="sRGB">'
                + "".join(bounded_primitives(self.p)) + '</filter></defs><rect width="3072" height="3072" fill="white" filter="url(#core)"/></svg>')
        if "<script" in html or "javascript:" in html:
            raise AssertionError("Script-free source contract violated")
        # Keep the monolithic diagnostic reproducible, but use native nested
        # filters to bound Skia DAG depth and materialize each block internally.
        (self.directory / "monolithic.html").write_text(html)
        filters = []
        for stage in self.stages:
            filters.append(f'<filter id="{stage["name"]}" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" x="0" y="0" width="3072" height="3072" color-interpolation-filters="sRGB">' + "".join(bounded_primitives(stage["primitives"])) + '</filter>')
        content = f'<image id="live-input" href="input.png" width="768" height="{self.context}" preserveAspectRatio="none"/>'
        for stage in self.stages:
            content = f'<g filter="url(#{stage["name"]})">{content}</g>'
        html = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
                '<style>html,body{margin:0;background:magenta}svg{display:block;image-rendering:pixelated}</style>'
                f'<svg width="768" height="{2 * self.context}" xmlns="http://www.w3.org/2000/svg"><defs>' + "".join(filters) + '</defs>'
                + content + f'<use href="#live-input" y="{self.context}"/></svg>')
        (self.directory / "index.html").write_text(html)
        self.outputs = [self.outputs[-1]]
        height = 2 * self.context
        metadata = {"context": self.context, "blocks": self.blocks, "height": height,
                    "input_scales": input_spec["scales"].tolist(), "outputs": self.outputs,
                    "primitives": len(self.p), "html_bytes": len(html.encode()),
                    "calibration_only": True, "runtime_javascript": False}
        (self.directory / "graph.json").write_text(json.dumps(metadata))
        return metadata


def screenshot(cdp, height):
    result = cdp.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                         "clip": {"x": 0, "y": 0, "width": 768, "height": height, "scale": 1}})
    raw = base64.b64decode(result["data"])
    return np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")), raw


def attention_checks(directory, checkpoint):
    """Browser tests with uniform and nonuniform softmax, all 12 heads."""
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    count = 4
    for kind in ("uniform", "nonuniform"):
        qkv = np.zeros((count, 2304), dtype=np.float64)
        for token in range(count):
            qkv[token, 1536:] = np.linspace(-.55, .55, 768) + .08 * token
            if kind == "nonuniform":
                qkv[token, :768] = .3
                qkv[token, 768:1536] = (token - 1.5) * .3
        encoded = np.rint(128 + qkv * 255 / 2).clip(0, 255).astype(np.uint8)
        decoded = (encoded.astype(float) - 128) * 2 / 255
        q, k, v = [part.reshape(count, 12, 64).transpose(1, 0, 2) for part in np.split(decoded, 3, axis=1)]
        scores = q @ k.swapaxes(-1, -2) / 8
        scores = np.where(np.tril(np.ones((count, count), bool))[None], scores, -np.inf)
        probabilities = np.exp(scores - scores.max(axis=-1, keepdims=True))
        probabilities /= probabilities.sum(axis=-1, keepdims=True)
        expected = (probabilities @ v).transpose(1, 0, 2).reshape(count, 768)
        cal = {"b0.qkv": decoded, "b0.scores": np.full((1, 12), 4.)}
        compiler = Compiler(directory / kind, cal, checkpoint, count)
        spec = {"scales": np.ones(2304), "ids": np.zeros(2304, int), "group_scales": np.ones(1)}
        sources = [compiler.image(f"qkv{t}", encoded[t, :, None] / 255, x=255) for t in range(count)]
        context, _ = compiler.attention(0, sources, spec)
        displays = [compiler.offset(source, f"show{t}", dx=t - 255, x=t, height=768) for t, source in enumerate(context)]
        compiler.merge(displays, "display")
        html = ('<!doctype html><style>html,body{margin:0;background:magenta}svg{display:block}</style>'
                '<svg width="4" height="768" xmlns="http://www.w3.org/2000/svg"><defs>'
                '<filter id="core" x="0" y="0" width="3072" height="3072" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" color-interpolation-filters="sRGB">'
                + "".join(bounded_primitives(compiler.p)) + '</filter></defs><rect width="3072" height="3072" fill="white" filter="url(#core)"/></svg>')
        page = directory / kind / "index.html"
        page.write_text(html)
        with browser() as cdp:
            cdp.command("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 800, "deviceScaleFactor": 1, "mobile": False})
            cdp.command("Page.navigate", {"url": page.as_uri()})
            time.sleep(.3)
            previous = None
            for _ in range(20):
                pixels, raw = screenshot(cdp, 768)
                # A complete grayscale filter result, not the magenta background.
                gray = np.array_equal(pixels[:, :4, 0], pixels[:, :4, 2]) and np.array_equal(pixels[:, :4, 0], pixels[:, :4, 1])
                if gray and previous is not None and np.array_equal(pixels, previous):
                    break
                previous = pixels
                time.sleep(.1)
            actual = (pixels[:, :4, 0].T.astype(float) / 255 - C) * 2
            error = float(np.max(np.abs(actual - expected)))
            record = {"case": kind, "max_error": error, "rmse": float(np.sqrt(np.mean((actual - expected) ** 2))),
                      "passed": error < .06, "browser": cdp.command("Browser.getVersion")}
            records.append(record)
            (directory / kind / "capture.png").write_bytes(raw)
            np.savez_compressed(directory / kind / "values.npz", actual=actual, expected=expected, probabilities=probabilities)
            print(f"Chromium attention self-test: {record}", flush=True)
    (directory / "results.json").write_text(json.dumps(records, indent=2))
    if not all(record["passed"] for record in records):
        raise AssertionError("SVG attention control failed; no quality verdict allowed")


def stage_pages(directory, count):
    """Diagnostic cuts: every arithmetic operation stays in the SVG renderer.

    The harness copies only exact screenshot bytes between blocks. This is
    NOT the no-external-transfer runtime; it isolates quality when the connected
    graph cannot finish, and must never be reported as autonomous latency.
    """
    html = (directory / "index.html").read_text()
    root = ET.fromstring(html[html.index("<svg"):])
    ns = "{http://www.w3.org/2000/svg}"
    # HTML's SVG parser does not interpret an XML serializer's ns0:filter tag
    # as a filter element. Preserve the default SVG namespace, not a prefix.
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    pages = []
    for element in root.find(ns + "defs"):
        name = element.attrib["id"]
        content = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
                   '<style>html,body{margin:0;background:magenta}svg{display:block;image-rendering:pixelated}</style>'
                   f'<svg width="768" height="{2 * count}" xmlns="http://www.w3.org/2000/svg"><defs>' + ET.tostring(element, encoding="unicode")
                   + f'</defs><g filter="url(#{name})"><image id="live-input" href="input.png" width="768" height="{count}" preserveAspectRatio="none"/></g>'
                   + f'<use href="#live-input" y="{count}"/></svg>')
        path = directory / f"replay-{name}.html"
        path.write_text(content)
        pages.append(path)
    return pages


def load_input_node(cdp, path):
    cdp.command("Page.navigate", {"url": path.as_uri()})
    deadline = time.monotonic() + 60
    while True:
        try:
            cdp.root_node = None
            node = query(cdp, "#live-input")
            if node:
                return node
        except RuntimeError:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError("SVG document did not load")
        time.sleep(.05)


def capture_input(cdp, node, pixels):
    count = pixels.shape[0]
    cdp.command("DOM.setAttributeValue", {"nodeId": node, "name": "href", "value": png_uri(pixels)})
    previous = None
    for _ in range(12):
        capture, raw = screenshot(cdp, count * 2)
        echoed = np.array_equal(capture[-count:, :, 0], pixels[..., 0] if pixels.ndim == 3 else pixels)
        if echoed and previous is not None and np.array_equal(capture, previous):
            return capture, raw
        previous = capture
        time.sleep(.1)
    raise AssertionError("Input echo/stable paint verification failed")


def run(args, checkpoint, model, manifest):
    directory = args.out
    meta = json.loads((directory / "graph.json").read_text())
    count = meta["context"]
    if meta["blocks"] != 12:
        raise ValueError("Quality evaluation requires all 12 blocks")
    input_scale = np.asarray(meta["input_scales"])
    result = {"kind": "actual_chromium_causal_svg_core_with_common_fp32_scoring_head",
              "runtime_javascript": False, "harness_javascript": False,
              "intermediate_injection": False, "context": count,
              "model_sha256": sha256(ROOT / "data/gpt2/model.safetensors"), "cases": []}
    if args.replay:
        result.update(kind="actual_chromium_arithmetic_pixel_replay_diagnostic_common_fp32_head",
                      intermediate_injection="exact_browser_pixel_bytes_only_no_reference_activations",
                      autonomous_pipeline=False)
    pages = stage_pages(directory, count) if args.replay else []
    all_values = {key: [] for key in ("nll", "kl", "tv", "agreement")}
    reference_nll = []
    with browser() as cdp:
        result["browser"] = cdp.command("Browser.getVersion")
        cdp.command("Emulation.setDeviceMetricsOverride", {"width": 900, "height": max(meta["height"], 200), "deviceScaleFactor": 1, "mobile": False})
        cdp.command("Page.navigate", {"url": (pages[0] if pages else directory / "index.html").as_uri()})
        deadline = time.monotonic() + 60
        node = 0
        while not node:
            try:
                cdp.root_node = None
                node = query(cdp, "#live-input")
            except RuntimeError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError("SVG document did not load")
            time.sleep(.05)
        cases = []
        for window, sample in enumerate(manifest["evaluation"]):
            # Nonoverlapping short contexts, deterministic, same corpus as offline.
            for start in range(0, min(len(sample["tokens"]) - count, args.offsets * count), count):
                cases.append((window, start, sample["tokens"][start:start + count + 1]))
        cases = cases[:args.cases]
        for case_id, (window, start, ids) in enumerate(cases):
            embeddings = checkpoint[0][ids[:-1]] + checkpoint[1][:count]
            pixels = np.clip(np.rint(128 + embeddings / (2 * input_scale) * 255), 0, 255).astype(np.uint8)
            expected, trace = trace_hidden(model, ids[:-1])
            begin = time.perf_counter()
            stage_times = []
            if args.replay:
                incoming_pixels = pixels
                for stage, page in enumerate(pages):
                    stage_begin = time.perf_counter()
                    node = load_input_node(cdp, page)
                    capture, raw = capture_input(cdp, node, incoming_pixels)
                    if np.array_equal(capture[:count], capture[-count:]):
                        raise AssertionError("Filter was bypassed: output exactly equals input")
                    incoming_pixels = capture[:count].copy()
                    (directory / f"case-{case_id:03d}-stage-{stage:02d}.png").write_bytes(raw)
                    stage_times.append(time.perf_counter() - stage_begin)
                    print(f"Browser pixel-replay case {case_id}, stage {stage + 1}/{len(pages)}: {stage_times[-1]:.2f}s", flush=True)
            else:
                capture, raw = capture_input(cdp, node, pixels)
            elapsed = time.perf_counter() - begin
            vectors = {}
            errors = {}
            for group, (name, _, scales) in enumerate(meta["outputs"]):
                value = (capture[group * count:(group + 1) * count, :, 0].astype(float) / 255 - C) * 2 * np.asarray(scales)
                vectors[name] = value.astype(np.float32)
                reference = trace[name][0]
                errors[name] = {"rmse": float(np.sqrt(np.mean((value - reference) ** 2))),
                                "max_error": float(np.max(np.abs(value - reference)))}
            actual_logits = vectors["final"] @ checkpoint[0].T
            ref_logits = expected @ checkpoint[0].T
            measured = metrics(actual_logits, ref_logits, ids[1:])
            ref = metrics(ref_logits, ref_logits, ids[1:])
            for key, values in measured.items():
                all_values[key].extend(values.tolist())
            reference_nll.extend(ref["nll"].tolist())
            row = {"case": case_id, "article_id": manifest["evaluation"][window]["article_id"],
                   "source_window": window, "window_offset": start, "tokens": ids,
                   "capture_seconds_including_two_stability_reads": elapsed,
                   "stage_capture_seconds": stage_times,
                   "input_echo_verified": True, "layer_errors": errors,
                   "svg": metric_summary(measured), "fp32": metric_summary(ref),
                   "per_token": {key: value.tolist() for key, value in measured.items()},
                   "reference_nll": ref["nll"].tolist(),
                   "svg_winners": actual_logits.argmax(-1).tolist(), "fp32_winners": ref_logits.argmax(-1).tolist()}
            result["cases"].append(row)
            result["overall"] = metric_summary(all_values)
            result["fp32_perplexity"] = float(np.exp(np.mean(reference_nll)))
            result["perplexity_ratio"] = result["overall"]["perplexity"] / result["fp32_perplexity"]
            (directory / ("replay-results.json" if args.replay else "results.json")).write_text(json.dumps(result, indent=2))
            # Real raw browser pixels retained for every case, not only scores.
            (directory / f"capture-{case_id:03d}.png").write_bytes(raw)
            np.savez_compressed(directory / f"vectors-{case_id:03d}.npz", **vectors)
            print(f"Chromium case {case_id + 1}/{len(cases)}: PPL ratio={row['svg']['perplexity'] / row['fp32']['perplexity']:.3f}, total ratio={result['perplexity_ratio']:.3f}, capture={elapsed:.2f}s", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT)
    parser.add_argument("--context", type=int, default=4)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--cases", type=int, default=24)
    parser.add_argument("--offsets", type=int, default=1)
    parser.add_argument("--calibration-samples", type=int, default=256)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--measure-only", action="store_true")
    parser.add_argument("--attention-checks-only", action="store_true")
    parser.add_argument("--replay", action="store_true", help="Diagnostic raw browser-pixel transfer between blocks, not an autonomous runtime")
    args = parser.parse_args()
    args.out = args.out.resolve()
    checkpoint = load_model()
    if args.attention_checks_only:
        attention_checks(args.out / "attention-controls", checkpoint)
        return
    model = Model(checkpoint)
    manifest = json.loads((ROOT / "experiments/gpt2-quantization-quality/manifest.json").read_text())
    if not args.measure_only:
        calibration = train_calibration(model, manifest, args.calibration_samples)
        Compiler(args.out, calibration, checkpoint, args.context, args.blocks).build()
        (args.out / "provenance.json").write_text(json.dumps({"source_manifest_sha256": sha256(ROOT / "experiments/gpt2-quantization-quality/manifest.json"), "calibration_samples": args.calibration_samples, "test_calibration": False}, indent=2))
    if not args.build_only:
        run(args, checkpoint, model, manifest)


if __name__ == "__main__":
    main()
