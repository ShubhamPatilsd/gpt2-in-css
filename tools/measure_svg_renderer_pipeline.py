#!/usr/bin/env python3
# /// script
# dependencies = ["numpy==2.5.3", "pillow", "fonttools", "tokenizers==0.22.2"]
# ///
"""Execute every neural operation in Chromium with byte-exact diagnostic cuts.

NOT an autonomous runtime: Python copies browser pixels between filter stages.
No activation is recalculated, corrected, or replaced by a reference value.
This measures the actual SVG arithmetic, independent of connected-DAG cost.
"""

import argparse
import base64
import copy
import io
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

from evaluate_gpt2_quantization_quality import Model, load_model, metrics, metric_summary
from measure_svg_causal_chromium import C, ROOT, png_uri, trace_hidden
from profile_hybrid_twelve_block import browser, query

NS = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")


def sources(element):
    return [element.attrib[k] for k in ("in", "in2") if k in element.attrib] + [child.attrib["in"] for child in element if child.tag == NS + "feMergeNode"]


def compile_cuts(directory, batch=1):
    meta = json.loads((directory / "graph.json").read_text())
    count = meta["context"]
    html = (directory / "index.html").read_text()
    root = ET.fromstring(html[html.index("<svg"):])
    filters = {element.attrib["id"]: element for element in root.find(NS + "defs")}
    phases = []

    def emit(name, nodes, inputs, outputs, trace_name):
        if batch == 1:
            return make_page(directory, name, nodes, inputs, outputs, trace_name)
        expanded = {}
        for case in range(batch):
            prefix = f"c{case}-"
            for key, original in nodes.items():
                element = copy.deepcopy(original)
                for child in element.iter():
                    for attr in ("in", "in2", "result"):
                        if attr in child.attrib and child.attrib[attr] != "SourceGraphic":
                            child.attrib[attr] = prefix + child.attrib[attr]
                expanded[prefix + key] = element
        all_inputs = [f"c{case}-{key}" for case in range(batch) for key in inputs]
        all_outputs = [f"c{case}-{key}" for case in range(batch) for key in outputs]
        return make_page(directory, f"batch{batch}-{name}", expanded, all_inputs, all_outputs, trace_name)
    previous = [f"t{t}-input" for t in range(count)]
    for layer in range(12):
        p = f"b{layer}"
        nodes = {e.attrib["result"]: e for e in filters[p] if "result" in e.attrib}
        names = lambda suffix, p=p: [f"t{t}-{p}-{suffix}" for t in range(count)]
        # Results of the already-compiled SVG graph, no new numerical recipe.
        ln1, qkv = names("ln1-out"), names("qkv-common")
        context = [f"a{layer}t{t}-context" for t in range(count)]
        attention, residual = names("attn-common"), names("residual1-out")
        ln2, fc = names("ln2-out"), names("fc-common")
        gelu = names("gelu-pack-sum10")
        projection, output = names("proj-common"), names("residual2-out")
        for label, inputs, outputs, trace_name in (
            ("ln1", previous, ln1, p + ".ln1"),
            ("qkv", ln1, qkv, p + ".qkv"),
            ("attention", qkv, context, p + ".context"),
            ("cproj", context, attention, p + ".attention"),
            ("residual1", attention + previous, residual, p + ".residual1"),
            ("ln2", residual, ln2, p + ".ln2"),
            ("fc", ln2, fc, p + ".fc"),
            ("gelu", fc, gelu, p + ".gelu"),
            ("projection", gelu, projection, p + ".projection"),
            ("residual2", projection + residual, output, p + ".residual2"),
        ):
            phases.append(emit(f"cut-{p}-{label}", nodes, inputs, outputs, trace_name))
        previous = output
    nodes = {e.attrib["result"]: e for e in filters["final"] if "result" in e.attrib}
    phases.append(emit("cut-final", nodes, previous, [f"t{t}-final-ln-out" for t in range(count)], "final"))
    (directory / f"cuts-batch{batch}.json").write_text(json.dumps(phases))
    return meta, phases


def make_page(directory, name, nodes, inputs, outputs, trace_name):
    needed = set()

    def visit(key):
        if key in inputs or key in needed:
            return
        if key not in nodes:
            raise ValueError(f"Unresolved SVG dependency {key} in {name}")
        needed.add(key)
        for source in sources(nodes[key]):
            visit(source)

    for output in outputs:
        visit(output)
    feed = []
    for i, key in enumerate(inputs):
        attrs = nodes[key].attrib if key in nodes else {"x": "0", "y": "255", "width": "768", "height": "1"}
        geometry = " ".join(f'{prop}="{attrs[prop]}"' for prop in ("x", "y", "width", "height"))
        feed.append(f'<feImage id="feed{i}" href="input.png" {geometry} preserveAspectRatio="none" result="{key}"/>')
    body = feed + [ET.tostring(node, encoding="unicode") for key, node in nodes.items() if key in needed]
    displays, geometries = [], []
    for i, key in enumerate(outputs):
        attrs = nodes[key].attrib
        x, y, w, h = [int(float(attrs[prop])) for prop in ("x", "y", "width", "height")]
        ox, oy = (i, 0) if w == 1 else (0, i)
        geometry = {"x": ox, "y": oy, "width": w, "height": h}
        geometries.append(geometry)
        body.append(f'<feOffset in="{key}" dx="{ox-x}" dy="{oy-y}" x="{ox}" y="{oy}" width="{w}" height="{h}" result="show{i}"/>')
        displays.append(f"show{i}")
    width = max(r["x"] + r["width"] for r in geometries)
    height = max(r["y"] + r["height"] for r in geometries)
    # An echo of every incoming pixel surface makes stale/partial input visible.
    echoes = []
    cursor = height + 1
    for i, key in enumerate(inputs):
        attrs = nodes[key].attrib if key in nodes else {"x": "0", "y": "255", "width": "768", "height": "1"}
        x, y, w, h = [int(float(attrs[prop])) for prop in ("x", "y", "width", "height")]
        # Place vertical input echoes side-by-side, horizontal ones in rows.
        ex, ey = (i, cursor) if w == 1 else (0, cursor + i)
        body.append(f'<feOffset in="{key}" dx="{ex-x}" dy="{ey-y}" x="{ex}" y="{ey}" width="{w}" height="{h}" result="echo{i}"/>')
        echoes.append({"x": ex, "y": ey, "width": w, "height": h})
        displays.append(f"echo{i}")
    full_width = max(width, max(r["x"] + r["width"] for r in echoes))
    full_height = max(height, max(r["y"] + r["height"] for r in echoes))
    body.append(f'<feMerge result="display" x="0" y="0" width="{full_width}" height="{full_height}">' + "".join(f'<feMergeNode in="{key}"/>' for key in displays) + '</feMerge>')
    html = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
            '<style>html,body{margin:0;background:magenta}svg{display:block;image-rendering:pixelated}</style>'
            f'<svg width="{full_width}" height="{full_height}" xmlns="http://www.w3.org/2000/svg"><defs>'
            f'<filter id="cut" x="0" y="0" width="{max(3072, full_width)}" height="{max(3072, full_height)}" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" color-interpolation-filters="sRGB">'
            + "".join(body) + '</filter></defs><rect width="3072" height="3072" fill="white" filter="url(#cut)"/></svg>')
    if "ns0:" in html or "<script" in html:
        raise AssertionError("Bad SVG namespace or script content")
    path = directory / f"{name}.html"
    path.write_text(html)
    return {"path": str(path), "inputs": inputs, "outputs": outputs,
            "rects": geometries, "echoes": echoes, "width": full_width, "height": full_height,
            "trace_name": trace_name, "primitives": len(body)}


def capture(cdp, phase):
    payload = cdp.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                          "clip": {"x": 0, "y": 0, "width": phase["width"], "height": phase["height"], "scale": 1}})
    raw = base64.b64decode(payload["data"])
    return np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")), raw


def region(pixels, rect):
    return pixels[rect["y"]:rect["y"] + rect["height"], rect["x"]:rect["x"] + rect["width"]]


def open_phase(cdp, phase):
    url = Path(phase["path"]).as_uri()
    cdp.command("Page.navigate", {"url": url})
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            root = cdp.command("DOM.getDocument", {"depth": 1})["root"]
            if root.get("documentURL") != url:
                time.sleep(.05)
                continue
            cdp.root_node = root["nodeId"]
            if query(cdp, "#feed0") and query(cdp, "svg > rect"):
                time.sleep(.1)
                cdp.root_node = None
                return
        except RuntimeError:
            pass
        time.sleep(.05)
    raise TimeoutError("Requested SVG document did not commit")


def evaluate(directory, cases=4):
    meta, phases = compile_cuts(directory)
    checkpoint = load_model()
    model = Model(checkpoint)
    manifest = json.loads((ROOT / "experiments/gpt2-quantization-quality/manifest.json").read_text())
    count = meta["context"]
    output = {"kind": "actual_chromium_neural_arithmetic_with_byte_exact_diagnostic_cuts",
              "autonomous_runtime": False, "python_neural_arithmetic": "reference_and_common_FP32_scoring_head_only",
              "runtime_javascript": False, "harness_javascript": False,
              "input_echoes_checked_at_every_cut": True, "context": count, "cases": []}
    values = {key: [] for key in ("nll", "kl", "tv", "agreement")}
    reference_nll = []
    with browser() as cdp:
        output["browser"] = cdp.command("Browser.getVersion")
        cdp.connection.settimeout(60)
        cdp.command("Emulation.setDeviceMetricsOverride", {"width": 3200, "height": 3200, "deviceScaleFactor": 1, "mobile": False})
        for case_id, sample in enumerate(manifest["evaluation"][:cases]):
            ids = sample["tokens"][:count + 1]
            embedding = checkpoint[0][ids[:-1]] + checkpoint[1][:count]
            encoded = np.clip(np.rint(128 + embedding / (2 * np.asarray(meta["input_scales"])) * 255), 0, 255).astype(np.uint8)
            surfaces = {f"t{t}-input": np.repeat(encoded[t][None, :, None], 3, axis=2) for t in range(count)}
            times = []
            for index, phase in enumerate(phases):
                start = time.perf_counter()
                cdp.command("Page.navigate", {"url": Path(phase["path"]).as_uri()})
                node = 0
                for _ in range(30):
                    cdp.root_node = None
                    try:
                        node = query(cdp, "#feed0")
                    except RuntimeError:
                        pass
                    if node:
                        break
                    time.sleep(.05)
                if not node:
                    raise AssertionError("Filter input node absent")
                for feed_id, key in enumerate(phase["inputs"]):
                    node = query(cdp, f"#feed{feed_id}")
                    cdp.command("DOM.setAttributeValue", {"nodeId": node, "name": "href", "value": png_uri(surfaces[key])})
                previous = None
                for _ in range(10):
                    pixels, raw = capture(cdp, phase)
                    echoes_match = all(np.array_equal(region(pixels, rect), surfaces[key]) for rect, key in zip(phase["echoes"], phase["inputs"]))
                    if echoes_match and previous is not None and np.array_equal(pixels, previous):
                        break
                    previous = pixels
                    time.sleep(.08)
                else:
                    raise AssertionError(f"Exact input echo/stable paint check failed: {phase['trace_name']}")
                for key, rect in zip(phase["outputs"], phase["rects"]):
                    surfaces[key] = region(pixels, rect).copy()
                times.append(time.perf_counter() - start)
                if case_id == 0:
                    (directory / f"validated-cut-{index:03d}.png").write_bytes(raw)
                if index % 10 == 0 or index == len(phases) - 1:
                    print(f"Chromium arithmetic case {case_id + 1}, stage {index + 1}/{len(phases)} ({phase['trace_name']}): {times[-1]:.2f}s", flush=True)
            scales = np.asarray(meta["outputs"][-1][-1])
            actual = np.stack([(surfaces[key][..., 0].reshape(-1).astype(float) / 255 - C) * 2 * scales for key in phases[-1]["outputs"]]).astype(np.float32)
            expected, _ = trace_hidden(model, ids[:-1])
            logits, ref_logits = actual @ checkpoint[0].T, expected @ checkpoint[0].T
            measured, reference = metrics(logits, ref_logits, ids[1:]), metrics(ref_logits, ref_logits, ids[1:])
            for key, data in measured.items():
                values[key].extend(data.tolist())
            reference_nll.extend(reference["nll"].tolist())
            row = {"tokens": ids, "article_id": sample["article_id"], "svg": metric_summary(measured),
                   "fp32": metric_summary(reference), "stage_capture_seconds": times,
                   "per_token": {key: data.tolist() for key, data in measured.items()}, "reference_nll": reference["nll"].tolist(),
                   "final_rmse": float(np.sqrt(np.mean((actual - expected) ** 2)))}
            output["cases"].append(row)
            output["overall"] = metric_summary(values)
            output["fp32_perplexity"] = float(np.exp(np.mean(reference_nll)))
            output["perplexity_ratio"] = output["overall"]["perplexity"] / output["fp32_perplexity"]
            (directory / "cut-results.json").write_text(json.dumps(output, indent=2))
            np.savez_compressed(directory / f"validated-final-{case_id}.npz", actual=actual, expected=expected)
            print(f"ACTUAL CHROMIUM QUALITY case {case_id + 1}: total PPL ratio={output['perplexity_ratio']:.4f}", flush=True)
    return output


def evaluate_batch(directory, cases=24, reuse=False, start_case=0):
    """Amortize browser setup across independent test windows, never across tokens."""
    if reuse:
        meta = json.loads((directory / "graph.json").read_text())
        phases = json.loads((directory / f"cuts-batch{cases}.json").read_text())
    else:
        meta, phases = compile_cuts(directory, batch=cases)
    checkpoint = load_model()
    model = Model(checkpoint)
    manifest = json.loads((ROOT / "experiments/gpt2-quantization-quality/manifest.json").read_text())
    selected = manifest["evaluation"][start_case:start_case + cases]
    if cases < 2 or len(selected) != cases:
        raise ValueError("Batch must contain 2..24 saved test windows")
    count = meta["context"]
    surfaces = {}
    for case, sample in enumerate(selected):
        ids = sample["tokens"][:count]
        embedding = checkpoint[0][ids] + checkpoint[1][:count]
        encoded = np.clip(np.rint(128 + embedding / (2 * np.asarray(meta["input_scales"])) * 255), 0, 255).astype(np.uint8)
        for token in range(count):
            surfaces[f"c{case}-t{token}-input"] = np.repeat(encoded[token][None, :, None], 3, axis=2)
    times = []
    with browser() as cdp:
        version = cdp.command("Browser.getVersion")
        cdp.connection.settimeout(60)
        cdp.command("Emulation.setDeviceMetricsOverride", {"width": 3200, "height": 3200, "deviceScaleFactor": 1, "mobile": False})
        for index, phase in enumerate(phases):
            begin = time.perf_counter()
            open_phase(cdp, phase)
            for i, key in enumerate(phase["inputs"]):
                cdp.root_node = None
                feed = query(cdp, f"#feed{i}")
                if not feed:
                    raise AssertionError(f"Missing feed {i} in {phase['trace_name']}")
                cdp.command("DOM.setAttributeValue", {"nodeId": feed, "name": "href", "value": png_uri(surfaces[key])})
            previous = None
            for _ in range(10):
                pixels, raw = capture(cdp, phase)
                matches = all(np.array_equal(region(pixels, rect), surfaces[key]) for rect, key in zip(phase["echoes"], phase["inputs"]))
                if matches and previous is not None and np.array_equal(pixels, previous):
                    break
                previous = pixels
                time.sleep(.08)
            else:
                (directory / f"INVALID-batch{cases}-{phase['trace_name']}.png").write_bytes(raw)
                failed = [i for i, (rect, key) in enumerate(zip(phase["echoes"], phase["inputs"])) if not np.array_equal(region(pixels, rect), surfaces[key])]
                print({"failed_echo_indices": failed, "shape": list(pixels.shape), "pixel_min": int(pixels.min()), "pixel_max": int(pixels.max())}, flush=True)
                raise AssertionError(f"Batch input echo mismatch at {phase['trace_name']}")
            for key, rect in zip(phase["outputs"], phase["rects"]):
                surfaces[key] = region(pixels, rect).copy()
            times.append(time.perf_counter() - begin)
            (directory / f"batch{cases}-validated-cut-{index:03d}.png").write_bytes(raw)
            if index % 10 == 0 or index == len(phases) - 1:
                print(f"Actual Chromium batch={cases}, stage {index + 1}/121 {phase['trace_name']}: {times[-1]:.2f}s", flush=True)
    result = {"kind": "actual_chromium_neural_arithmetic_with_byte_exact_diagnostic_cuts",
              "autonomous_runtime": False, "runtime_javascript": False, "harness_javascript": False,
              "input_echoes_checked_at_every_cut": True, "context": count, "batch": cases, "start_case": start_case,
              "browser": version, "stage_capture_seconds": times, "cases": []}
    all_values = {key: [] for key in ("nll", "kl", "tv", "agreement")}
    reference_nll = []
    scales = np.asarray(meta["outputs"][-1][-1])
    for case, sample in enumerate(selected):
        ids = sample["tokens"][:count + 1]
        actual = np.stack([(surfaces[f"c{case}-t{t}-final-ln-out"][..., 0].reshape(-1).astype(float) / 255 - C) * 2 * scales for t in range(count)]).astype(np.float32)
        expected, _ = trace_hidden(model, ids[:-1])
        logits, ref_logits = actual @ checkpoint[0].T, expected @ checkpoint[0].T
        measured, reference = metrics(logits, ref_logits, ids[1:]), metrics(ref_logits, ref_logits, ids[1:])
        for key, data in measured.items():
            all_values[key].extend(data.tolist())
        reference_nll.extend(reference["nll"].tolist())
        result["cases"].append({"tokens": ids, "article_id": sample["article_id"], "svg": metric_summary(measured), "fp32": metric_summary(reference),
                                "per_token": {key: data.tolist() for key, data in measured.items()}, "reference_nll": reference["nll"].tolist(),
                                "final_rmse": float(np.sqrt(np.mean((actual - expected) ** 2)))})
        np.savez_compressed(directory / f"batch{cases}-start{start_case}-validated-final-{case}.npz", actual=actual, expected=expected)
    result["overall"] = metric_summary(all_values)
    result["fp32_perplexity"] = float(np.exp(np.mean(reference_nll)))
    result["perplexity_ratio"] = result["overall"]["perplexity"] / result["fp32_perplexity"]
    (directory / f"batch{cases}-start{start_case}-cut-results.json").write_text(json.dumps(result, indent=2))
    print({key: result[key] for key in ("overall", "fp32_perplexity", "perplexity_ratio")}, flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cases", type=int, default=4)
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--reuse-pages", action="store_true")
    parser.add_argument("--start-case", type=int, default=0)
    args = parser.parse_args()
    if args.batch:
        evaluate_batch(args.directory.resolve(), args.cases, args.reuse_pages, args.start_case)
    else:
        evaluate(args.directory.resolve(), args.cases)
