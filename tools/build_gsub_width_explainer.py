#!/usr/bin/env python3
"""Build a portable explainer from the preserved experiment, not new timings."""
from __future__ import annotations

import base64
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-width-explainer"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-neuron", action="store_true", help="Re-extract the float reference slice from the local checkpoint (requires NumPy)")
    args = parser.parse_args()
    if args.refresh_neuron:
        import numpy as np
        sys.path.insert(0, str(ROOT / "tools"))
        from analyze_css_native_grouped_mlp import load_weights, exact_block0_batch
        from build_pretrained_gpt2 import Gpt2Tokenizer
        tokenizer = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
        tokens = tokenizer.encode("Hello")
        assert tokens == [15496]
        weights = load_weights()
        inputs, _, _ = exact_block0_batch(np.array([tokens]), weights)
        x = inputs[0].astype(np.float64)
        w = weights.fc_weight[:, 0].astype(np.float64)
        bias = float(weights.fc_bias[0])
        payload = x.astype("<f8").tobytes() + w.astype("<f8").tobytes() + np.array([bias], dtype="<f8").tobytes()
        neuron = {
            "tokenId": tokens[0], "prompt": "Hello", "block": 0,
            "stage": "output of ln_2 / input of block-0 MLP for single-token Hello",
            "outputNeuron": 0, "input": x.tolist(), "weights": w.tolist(), "bias": bias,
            "preactivationFloat64": float(x @ w + bias),
            "nonzeroWeights": int(np.count_nonzero(w)), "fcShape": list(weights.fc_weight.shape),
            "modelPath": "data/gpt2/model.safetensors",
            "referenceFunction": "tools/analyze_css_native_grouped_mlp.py:exact_block0_batch; float32 activations, float64 displayed dot product",
            "sliceSha256": hashlib.sha256(payload).hexdigest(),
            "sliceHashEncoding": "768 input float64 LE values, then 768 weight float64 LE values, then one bias float64 LE value",
        }
        (OUT / "real-neuron.json").write_text(json.dumps(neuron, indent=2) + "\n")
    font_path = ROOT / "experiments/gsub-arithmetic-depth-probe/depth16/depth16.woff2"
    font = font_path.read_bytes()
    references = [
        ROOT / "experiments/gsub-arithmetic-depth-probe/results.json",
        ROOT / "experiments/gsub-arithmetic-depth-probe/depth16/results.json",
    ]
    results = [json.loads(p.read_text()) for p in references]
    evidence = {
        "neuron": json.loads((OUT / "real-neuron.json").read_text()),
        "timings": [
            {k: row[k] for k in ("depth", "mode", "phase", "batch", "samples", "medianMilliseconds")}
            for result in results for row in result["timings"]
            if row["mode"] in ("gsub", "direct-css")
        ],
        "font": results[1]["reference"]["fonts"][0],
        "fontSha256": hashlib.sha256(font).hexdigest(),
        "browser": results[1]["browserVersion"],
    }
    assert evidence["fontSha256"] == "158b63dc872e96c535ee956fe397957e1ae0008affa99973422e43a7fd09bd46"
    assert len(evidence["neuron"]["input"]) == len(evidence["neuron"]["weights"]) == 768
    counters = "\n".join(
        "@counter-style gw-" + tag + "{system:fixed 0;symbols:"
        + " ".join('"\\%x"' % (start + i) for i in range(16)) + ";suffix:''}"
        for tag, start in (("x", 0xE000), ("y", 0xE010))
    )
    html = (OUT / "simple.template.html").read_text()
    html = html.replace("__FONT_BASE64__", base64.b64encode(font).decode())
    html = html.replace("__COUNTER_STYLES__", counters)
    html = html.replace("__EVIDENCE_JSON__", json.dumps(evidence, separators=(",", ":")).replace("<", "\\u003c"))
    assert "__FONT_BASE64__" not in html and "__EVIDENCE_JSON__" not in html
    (OUT / "index.html").write_text(html)
    manifest = {
        "artifact": "index.html",
        "bytes": len(html.encode()),
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
        "fontSha256": evidence["fontSha256"],
        "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [font_path, *references, OUT / "real-neuron.json", OUT / "simple.template.html"]},
        "note": "Interactive teaching page; embedded observations are preserved measurements, not new benchmarks.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"path": str(OUT / "index.html"), "bytes": manifest["bytes"]}))


if __name__ == "__main__":
    main()
