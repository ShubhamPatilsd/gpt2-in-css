#!/usr/bin/env python3
"""Standalone Skia CPU precision test with real GPT-2 weight slices.

This is not Chromium, SVG inference, or a token-speed measurement. All live
matrix arithmetic runs in Skia filters; Python prepares constants, static draw
schedules and an independent oracle. ReLU is a structural substitute for GELU.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time

import numpy as np
import skia

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


OUT = Path(__file__).resolve().parents[1] / "experiments/skia-f16-real-matvec"
TYPES = {"RGBA8": skia.kRGBA_8888_ColorType,
         "RGBA16F": skia.kRGBA_F16_ColorType,
         "RGBA32F": skia.kRGBA_F32_ColorType}


def normalized(x, weight, bias):
    return (x - np.mean(x)) / np.sqrt(np.mean((x - np.mean(x)) ** 2) + 1e-5) * weight + bias


def real_inputs(tensors, token):
    """Actual block-0 LN2 vector for a single-token GPT-2 prompt, oracle only."""
    x = np.asarray(tensors.tensor("wte.weight")[token], dtype=np.float64) + tensors.tensor("wpe.weight")[0]
    n = normalized(x, tensors.tensor("h.0.ln_1.weight"), tensors.tensor("h.0.ln_1.bias"))
    qkv = n @ tensors.tensor("h.0.attn.c_attn.weight") + tensors.tensor("h.0.attn.c_attn.bias")
    # For one token the softmax is exactly one in every head, so attention is V.
    x = x + qkv[1536:] @ tensors.tensor("h.0.attn.c_proj.weight") + tensors.tensor("h.0.attn.c_proj.bias")
    return normalized(x, tensors.tensor("h.0.ln_2.weight"), tensors.tensor("h.0.ln_2.bias"))


def image_from_values(values):
    values = np.asarray(values, dtype=np.float32)
    array = np.ones((*values.shape, 4), dtype=np.float32)
    array[..., :3] = values[..., None]
    return skia.Image.fromarray(array, colorType=skia.kRGBA_F32_ColorType)


def matrix(scale=1.0, bias=0.0):
    return skia.ImageFilters.ColorFilter(skia.ColorFilters.Matrix([
        scale, 0, 0, 0, bias, 0, scale, 0, 0, bias,
        0, 0, scale, 0, bias, 0, 0, 0, 1, 0]))


def values(image):
    return image.toarray(colorType=skia.kRGBA_F32_ColorType)[..., 0].astype(np.float64)


def error(actual, expected):
    delta = np.asarray(actual) - np.asarray(expected)
    return {"rmse": float(np.sqrt(np.mean(delta ** 2))),
            "maxAbsoluteError": float(np.max(np.abs(delta))),
            "expectedRms": float(np.sqrt(np.mean(np.asarray(expected) ** 2)))}


class Renderer:
    def __init__(self, color_type):
        self.color_type = color_type
        self.allocations = []
        self.draw_count = 0

    def surface(self, width, height, label):
        info = skia.ImageInfo.Make(width, height, self.color_type, skia.kPremul_AlphaType)
        surface = skia.Surface.MakeRaster(info)
        if surface is None:
            raise RuntimeError(f"Cannot allocate {label}")
        self.allocations.append({"stage": label, "width": width, "height": height,
                                 "colorType": str(surface.imageInfo().colorType()),
                                 "minimumBytes": int(info.minRowBytes() * height)})
        surface.getCanvas().clear(skia.ColorTRANSPARENT)
        return surface

    def draw(self, surface, image, x=0, y=0, image_filter=None):
        paint = skia.Paint(ImageFilter=image_filter, AntiAlias=False) if image_filter else None
        if paint:
            surface.getCanvas().drawImage(image, x, y, paint=paint)
        else:
            surface.getCanvas().drawImage(image, x, y)
        self.draw_count += 1

    def materialize(self, image, image_filter, width, height, label):
        surface = self.surface(width, height, label)
        self.draw(surface, image, image_filter=image_filter)
        result = surface.makeImageSnapshot()
        self.allocations[-1]["snapshotColorType"] = str(result.colorType())
        return result


def dense(renderer, source, weight_values, bias_values, input_scale, output_scale,
          label, unsigned=False, column_input=False, collect=False):
    """Multiply encoded live pixels by real weights, then reduce and add bias."""
    n = len(weight_values)
    weight_scale = float(np.max(np.abs(weight_values)))
    weight_image = image_from_values(0.5 + weight_values / (2 * weight_scale))
    packed = renderer.surface(n, n * 2, f"{label}:packed-input-and-weights")
    canvas = packed.getCanvas()
    for row in range(n):
        if column_input:
            canvas.save()
            canvas.translate(0, row + 1)
            canvas.rotate(-90)
            renderer.draw(packed, source)
            canvas.restore()
        else:
            renderer.draw(packed, source, y=row)
    renderer.draw(packed, weight_image, y=n)
    packed_image = packed.makeImageSnapshot()
    # No ImageFilters.Image child: offsets consume the actual packed source.
    background = skia.ImageFilters.Offset(0, -n)
    if unsigned:
        product_filter = skia.ImageFilters.Arithmetic(1, -0.5, 0, 0.5, True, background)
    else:
        product_filter = skia.ImageFilters.Arithmetic(2, -1, -1, 1, True, background)
    product = renderer.materialize(packed_image, product_filter, n, n, f"{label}:signed-products")
    reduction = skia.ImageFilters.MatrixConvolution(
        skia.ISize(n, 1), [1.0] * n, 1 / n, 0,
        skia.IPoint(n // 2, 0), skia.TileMode.kClamp, False)
    summed = renderer.materialize(product, reduction, n, n, f"{label}:mean-products")
    column_surface = renderer.surface(1, n, f"{label}:extract-complete-reduction-column")
    renderer.draw(column_surface, summed, x=-(n // 2))
    column = column_surface.makeImageSnapshot()
    bias_image = image_from_values((0.5 + bias_values / (2 * output_scale))[:, None])
    bias_pack = renderer.surface(1, n * 2, f"{label}:packed-reduction-and-bias")
    renderer.draw(bias_pack, column)
    renderer.draw(bias_pack, bias_image, y=n)
    factor = n * input_scale * weight_scale / output_scale
    bias_filter = skia.ImageFilters.Arithmetic(0, factor, 1, -factor / 2, True,
                                               skia.ImageFilters.Offset(0, -n))
    output = renderer.materialize(bias_pack.makeImageSnapshot(), bias_filter, 1, n, f"{label}:biased-result")
    observations = {}
    if collect:
        packed_values = values(packed_image)
        observed_input = packed_values[0, :]
        observed_input = observed_input * input_scale if unsigned else (observed_input - 0.5) * 2 * input_scale
        observed_weights = (packed_values[n:, :] - 0.5) * 2 * weight_scale
        observations = {
            "input": observed_input.tolist(), "weights": observed_weights.tolist(),
            "productValues": values(product).tolist(),
            "meanProducts": values(column)[:, 0].tolist(),
            "outputValues": ((values(output)[:, 0] - 0.5) * 2 * output_scale).tolist(),
            "weightScale": weight_scale, "inputScale": input_scale, "outputScale": output_scale,
            "snapshotFormats": {"packed": str(packed_image.colorType()), "products": str(product.colorType()),
                                "reduced": str(column.colorType()), "biased": str(output.colorType())}}
    return output, observations


def run_chain(config, format_name, collect):
    renderer = Renderer(TYPES[format_name])
    source = image_from_values((0.5 + config["x"] / (2 * config["xScale"]))[None, :])
    first, first_obs = dense(renderer, source, config["w1"], config["b1"], config["xScale"],
                             config["yScale"], "fc", collect=collect)
    activated = renderer.materialize(first, matrix(2, -1), 1, len(config["x"]), "relu")
    second, second_obs = dense(renderer, activated, config["w2"], config["b2"], config["yScale"],
                               config["zScale"], "projection", unsigned=True,
                               column_input=True, collect=collect)
    # Final transfer is included even in timing trials; it is never fed back.
    result = (values(second)[:, 0] - 0.5) * 2 * config["zScale"]
    report = {"format": format_name, "surfaceAllocations": renderer.allocations,
              "totalMinimumAllocatedSurfaceBytes": sum(x["minimumBytes"] for x in renderer.allocations),
              "staticDrawCalls": renderer.draw_count, "finalError": error(result, config["z"]),
              "finalValues": result.tolist()}
    if collect:
        relu = values(activated)[:, 0] * config["yScale"]
        first_obs["inputError"] = error(first_obs["input"], config["x"])
        first_obs["weightError"] = error(first_obs["weights"], config["w1"])
        first_obs["outputError"] = error(first_obs["outputValues"], config["y"])
        quantized_input_oracle = np.asarray(first_obs["weights"]) @ np.asarray(first_obs["input"]) + config["b1"]
        first_obs["errorVersusMeasuredInputWeightOracle"] = error(first_obs["outputValues"], quantized_input_oracle)
        first_obs["idealProducts"] = (0.5 + config["w1"] * config["x"][None, :] /
                                      (2 * config["xScale"] * first_obs["weightScale"])).tolist()
        first_obs["productError"] = error(first_obs["productValues"], first_obs["idealProducts"])
        second_obs["weightError"] = error(second_obs["weights"], config["w2"])
        second_obs["inputTransportErrorVersusActualRelu"] = error(second_obs["input"], relu)
        second_obs["outputError"] = error(second_obs["outputValues"], config["z"])
        report.update({"firstMatvec": first_obs, "relu": {"values": relu.tolist(), "error": error(relu, config["relu"])},
                       "secondMatvec": second_obs})
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--sizes", default="16")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use a simple immutable label")
    sizes = [int(x) for x in args.sizes.split(",")]
    if any(x not in (8, 16, 32, 64) for x in sizes):
        parser.error("Sizes are bounded to 8,16,32,64")
    directory = OUT / args.label
    directory.mkdir(parents=True, exist_ok=False)
    tensors = SafeTensors(MODEL_PATH)
    tokens = (15496, 464)
    actual_inputs = [real_inputs(tensors, token) for token in tokens]
    source = Path(__file__).read_bytes()
    (directory / Path(__file__).name).write_bytes(source)
    report = {"scope": "Standalone Skia CPU; no Chromium, GPU, SVG page, or token generation", "skiaVersion": skia.__version__,
              "platform": platform.platform(), "sourceSha256": hashlib.sha256(source).hexdigest(),
              "command": __import__("sys").argv, "checkpoint": str(MODEL_PATH),
              "inputProvenance": "Real block-0 LN2 vectors for one-token prompts 15496 and 464, computed offline from checkpoint",
              "weights": "Top-left slices of h.0.mlp.c_fc.weight and h.0.mlp.c_proj.weight, with matching original biases",
              "activation": "ReLU structural stand-in, not GPT-2 GELU; truncated dimensions do not represent a GPT-2 block",
              "timingScope": "Precomputed NumPy fixtures and oracle excluded. Includes initial float image construction, static draw scheduling, filter creation, all surface allocations/copies, and final float readback. Diagnostic CPU wall time, not browser or pure matmul latency.",
              "cases": [], "floatControlPassed": True}
    try:
        for size in sizes:
            w1 = np.asarray(tensors.tensor("h.0.mlp.c_fc.weight")[:size, :size], dtype=np.float64).T
            w2 = np.asarray(tensors.tensor("h.0.mlp.c_proj.weight")[:size, :size], dtype=np.float64).T
            b1 = np.asarray(tensors.tensor("h.0.mlp.c_fc.bias")[:size], dtype=np.float64)
            b2 = np.asarray(tensors.tensor("h.0.mlp.c_proj.bias")[:size], dtype=np.float64)
            x_scale = max(8.0, float(np.ceil(max(np.max(np.abs(x[:size])) for x in actual_inputs))))
            y_scale = float(np.max(np.sum(np.abs(w1), axis=1) * x_scale + np.abs(b1))) + 0.001
            z_scale = float(np.max(np.sum(np.abs(w2), axis=1) * y_scale + np.abs(b2))) + 0.001
            for token, actual in zip(tokens, actual_inputs, strict=True):
                x = actual[:size]
                y = w1 @ x + b1
                activated = np.maximum(y, 0)
                z = w2 @ activated + b2
                config = {"x": x, "w1": w1, "w2": w2, "b1": b1, "b2": b2,
                          "xScale": x_scale, "yScale": y_scale, "zScale": z_scale,
                          "y": y, "relu": activated, "z": z}
                for name in TYPES:
                    case = run_chain(config, name, True)
                    case.update({"size": size, "token": token, "oracle": {"input": x.tolist(), "firstMatvec": y.tolist(), "relu": activated.tolist(), "final": z.tolist()},
                                 "ranges": {"input": x_scale, "firstResult": y_scale, "final": z_scale}})
                    timings = []
                    for repeat in range(args.rounds + 1):
                        started = time.perf_counter()
                        run_chain(config, name, False)
                        elapsed = (time.perf_counter() - started) * 1000
                        if repeat:
                            timings.append(elapsed)
                    case["diagnosticCpuMilliseconds"] = timings
                    case["medianDiagnosticCpuMilliseconds"] = statistics.median(timings)
                    report["cases"].append(case)
                    passed = max(case["firstMatvec"]["outputError"]["maxAbsoluteError"],
                                 case["relu"]["error"]["maxAbsoluteError"],
                                 case["finalError"]["maxAbsoluteError"]) < 0.0002
                    if name == "RGBA32F" and not passed:
                        report["floatControlPassed"] = False
                    print(json.dumps({"size": size, "token": token, "format": name,
                                      "finalError": case["finalError"], "floatControlAcceptable": passed,
                                      "ms": case["medianDiagnosticCpuMilliseconds"]}), flush=True)
            if not report["floatControlPassed"]:
                raise AssertionError("Float32 oracle failed; preserve failure and do not scale further")
    except Exception as exc:
        report["error"] = repr(exc)
        raise
    finally:
        (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
