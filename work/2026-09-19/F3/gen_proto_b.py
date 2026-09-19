#!/usr/bin/env python3
"""Prototype B: one real GPT-2 layer-0 MLP (768 -> 3072 -> 768) with the repo's HVAR font shards.

Two no-JS pages with identical fonts, inputs and decode arithmetic:
  b-chain     fc rows are anchors -> 12 x 128-deep fixed size-container chains (GELU decode per
              container child) -> per-shard proj glyph columns -> 3 x (1+128)-deep chains whose
              container widths SUM the 12 shard glyph anchors -> --out-* on #out0..2.
  b-timeline  the emitter's own matvec() (view-timeline readback, gated=False) for fc and proj.
The mutation is `html.class = go-k`, k in 0..15, selecting one of 16 real LN2(wte+wpe) inputs.
Expected outputs (NumPy, emitter witness path = quantized reconstructed weights) go to the sidecar.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))

import numpy as np  # noqa: E402

import build_gpt2_block_css as b  # noqa: E402
import build_hybrid_twelve_block as h  # noqa: E402
from analyze_full_gpt2 import MODEL_PATH, SafeTensors  # noqa: E402
from build_pretrained_gpt2 import css_number as num  # noqa: E402
from build_signed_hvar_chain import quantize_float_rows  # noqa: E402

W, M = 768, 3072
GELU = (
    "@function --gelu(--z <number>) returns <number>{--t:clamp(-20,calc(.7978845608028654 * "
    "(var(--z) + .044715 * pow(var(--z),3))),20);result:calc(.5 * var(--z) * "
    "(1 + (exp(2 * var(--t)) - 1) / (exp(2 * var(--t)) + 1)))}"
)
TOKENS = [15496, 995, 11, 314, 1101, 257, 3303, 2746, 13, 770, 318, 1332, 286, 262, 7926, 475]


def inputs(data, tensors):
    wte = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    wpe = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    rows = []
    for t in TOKENS:
        x = wte[t] + wpe[0]
        rows.append(b.layer_norm(x, data["ln2_gamma"], data["ln2_beta"]))
    return np.stack(rows)


def font_css(stem, directory, group):
    return h.b.font_faces(stem, group).replace('url("', f'url("{directory.as_uri()}/')


def chain_page(layer, qfc, bfc, qproj, bproj, gfc, gproj, n2s, out):
    dfc, Gfc = gfc
    dproj, Gproj = gproj
    upm, fs = b.UNITS_PER_EM, b.FONT_SIZE
    fc_bases = np.sum(np.stack(Gfc.row_bases), axis=0)
    proj_bases = np.sum(np.stack(Gproj.row_bases), axis=0)
    n2 = h.names("n2", W)
    hid = h.names("hidden", M)
    outn = h.names("out", W)
    css = [
        "html,body{margin:0;padding:0}",
        h.regs(n2 + hid + outn + ["--range-fc", "--range-proj"]),
        GELU,
        font_css(f"b{layer}-fc", dfc, Gfc),
        font_css(f"b{layer}-proj", dproj, Gproj),
        ".stage{position:fixed;left:0;top:-60000px;visibility:hidden;font-kerning:none;white-space:pre;line-height:1}",
        ".row{display:block;height:1px;width:max-content;font-style:normal}",
        ".c{position:fixed;left:0;top:0;container-type:size}",
        ".r{display:block;height:1px;width:1px}",
        ".hm{display:block;height:1px}",
    ]
    for k in range(16):
        css.append(f"html.go-{k} #in{{{';'.join(f'{p}:{num(v)}' for p, v in zip(n2, n2s[k]))}}}")
    css.append(
        f"#in{{--range-fc:calc(max(.000001,{','.join(f'abs(var({p}))' for p in n2)}) * 1.001)}}"
    )
    fam = f"b{layer}fc"
    settings = b.pack_font_settings(n2, 1, 0).replace(" / 1)", " / var(--range-fc))")
    css.append(
        f".fc{{font:normal {fs}px {fam}S0;font-family:{','.join(f'{fam}S{s}' for s in range(len(Gfc.names)))};"
        f"font-variation-settings:{settings}}}"
    )
    fc_rows = "".join(
        f'<i class="row" style="anchor-name:--f{i}">'
        + "".join(f"&#x{Gfc.codepoint_starts[s] + i:X};" for s in range(len(Gfc.names)))
        + "</i>"
        for i in range(M)
    )
    html = [f'<div id="in"><div class="stage fc">{fc_rows}</div>']
    # 12 fc gather chains, each hosting its proj shard column at the bottom
    shards = len(Gproj.names)
    # Empirical Chromium rule (order-probe): a fixed reader nested inside an anchored OOF subtree only sees
    # anchors that were laid out before its OOF root, i.e. in-flow content or OOF roots EARLIER in tree order,
    # plus its own subtree. So: per-shard proj range is LOCAL (no cross-chain read), and the out chains (later
    # roots) first read the 12 shard ranges as numbers, then sum the shard glyph widths scaled by them.
    css.append(h.regs([f"--r{j}" for j in range(shards)]))
    for j in range(shards):
        parts = []
        for k in range(128):
            i0, i1 = 256 * j + 2 * k, 256 * j + 2 * k + 1
            css.append(f"#fc{j}c{k}{{width:anchor-size(--f{i0} width);height:anchor-size(--f{i1} width)}}")
            decls = []
            for i, unit in ((i0, "cqw"), (i1, "cqh")):
                raw = f"(100{unit} / 1px * {upm} / {fs} - {int(fc_bases[i])})"
                decls.append(
                    f"{hid[i]}:--gelu(calc({raw} * {num(qfc.scales[i])} * var(--range-fc) + ({num(bfc[i])})))"
                )
            css.append(f"#fc{j}r{k}{{{';'.join(decls)}}}")
            parts.append(f'<div class="c" id="fc{j}c{k}"><div class="r" id="fc{j}r{k}">')
        local = hid[256 * j : 256 * j + 256]
        css.append(f"#pr{j}{{--range-proj:calc(max(.000001,{','.join(f'abs(var({p}))' for p in local)}) * 1.001)}}")
        css.append(f"#hm{j}{{width:calc(var(--range-proj) * 1024px)}}")
        pfam = f"b{layer}projS{j}"
        axes = ",".join(
            f'"{b.packed_axis_tag(j % b.PACK_SHARDS, l)}" calc(var({local[l]}) / var(--range-proj))'
            for l in range(256)
        )
        css.append(f"#ps{j}{{font:normal {fs}px {pfam};font-variation-settings:{axes}}}")
        prow = "".join(
            f'<i class="row" style="anchor-name:--p{j}_{i}">&#x{Gproj.codepoint_starts[j] + i:X};</i>'
            for i in range(W)
        )
        parts.append(
            f'<div id="pr{j}"><i class="hm" id="hm{j}" style="anchor-name:--hm{j}"></i>'
            f'<div class="stage" id="ps{j}">{prow}</div></div>'
        )
        parts.append("</div></div>" * 128)
        html.append("".join(parts))
    # 3 out chains (768 outputs), AFTER every fc chain in tree order: 6 range containers, then 128 value containers
    for m in range(3):
        parts = []
        for t in range(shards // 2):
            css.append(f"#o{m}g{t}{{width:anchor-size(--hm{2 * t} width);height:anchor-size(--hm{2 * t + 1} width)}}")
            css.append(f"#o{m}h{t}{{--r{2 * t}:calc(100cqw / 1px / 1024);--r{2 * t + 1}:calc(100cqh / 1px / 1024)}}")
            parts.append(f'<div class="c" id="o{m}g{t}"><div class="r" id="o{m}h{t}">')
        for k in range(128):
            i0, i1 = 256 * m + 2 * k, 256 * m + 2 * k + 1
            wsum = " + ".join(f"anchor-size(--p{j}_{i0} width) * var(--r{j})" for j in range(shards))
            hsum = " + ".join(f"anchor-size(--p{j}_{i1} width) * var(--r{j})" for j in range(shards))
            css.append(f"#o{m}c{k}{{width:calc({wsum});height:calc({hsum})}}")
            decls = []
            for i, unit in ((i0, "cqw"), (i1, "cqh")):
                bases = " + ".join(f"{int(Gproj.row_bases[j][i])} * var(--r{j})" for j in range(shards))
                raw = f"(100{unit} / 1px * {upm} / {fs} - ({bases}))"
                decls.append(f"{outn[i]}:calc({raw} * {num(qproj.scales[i])} + ({num(bproj[i])}))")
            css.append(f"#o{m}r{k}{{{';'.join(decls)}}}")
            parts.append(f'<div class="c" id="o{m}c{k}"><div class="r" id="o{m}r{k}">')
        parts.append(f'<div id="out{m}"></div>')
        parts.append("</div></div>" * (128 + shards // 2))
        html.append("".join(parts))
    html.append("</div>")
    page = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        f"<title>proto B chain</title><style>{''.join(css)}</style></head><body>{''.join(html)}</body></html>"
    )
    verify = [{"selector": f"#out{m}", "props": outn[256 * m : 256 * m + 256]} for m in range(3)]
    return page, verify


def timeline_page(layer, qfc, bfc, qproj, bproj, n2s, out):
    n2 = h.names("n2", W)
    hid = h.names("hidden", M)
    outn = h.names("out", W)
    css = ["html,body{margin:0;font:12px monospace}", h.regs(n2 + hid + outn + h.names("r", W))]
    for kind, count in (("fc", M), ("proj", W)):
        prog = h.names(kind + "p", count)
        css.append(h.regs(prog))
        css.append("".join(f"@keyframes {kind}k{i}{{from{{--{kind}p-{i:03d}:0}}to{{--{kind}p-{i:03d}:1}}}}" for i in range(count)))
    css.append(
        ".scroller{position:fixed;left:0;top:-60000px;height:1px;overflow-x:scroll;overflow-y:hidden;contain:strict;visibility:hidden}"
        ".track{position:relative;height:1px}"
        ".metric{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:hidden;white-space:pre}.metric i{font-style:normal}"
    )
    css.append(GELU)
    for k in range(16):
        css.append(f"html.go-{k} #in{{{';'.join(f'{p}:{num(v)}' for p, v in zip(n2, n2s[k]))}}}")
    fc_html, fc_css = h.matvec(layer, "fc", qfc, bfc, n2, hid, 1, 512, dynamic_range=True)
    pj_html, pj_css = h.matvec(layer, "proj", qproj, bproj, hid, outn, 1, 512, dynamic_range=True)
    css.append(fc_css)
    css.append(pj_css)
    html = '<div id="in">' + fc_html.replace("{child}", pj_html.replace("{child}", '<div id="out0"></div>')) + "</div>"
    page = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">'
        f"<title>proto B timeline</title><style>{''.join(css)}</style></head><body>{html}</body></html>"
    )
    return page, [{"selector": "#out0", "props": outn}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", type=int, default=0)
    ap.add_argument("--out", default=str(HERE / "pages"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    data = b.model_data(a.layer)
    qfc = quantize_float_rows(data["fc_weight"], bits=b.QUANT_BITS)
    qproj = quantize_float_rows(data["mlp_proj_weight"], bits=b.QUANT_BITS)
    bfc, bproj = data["fc_bias"], data["mlp_proj_bias"]
    # fonts must already exist (never rebuild into the repo from here)
    gfc = h.font_group(a.layer, "fc", qfc)
    gproj = h.font_group(a.layer, "proj", qproj)
    for d, g in (gfc, gproj):
        for n in g.names:
            assert (d / f"{n}.woff2").exists(), f"missing {d / n}.woff2"
    n2s = inputs(data, tensors)
    pre = n2s @ qfc.reconstructed.T + bfc
    hidden = b.gelu_new(pre)
    outq = hidden @ qproj.reconstructed.T + bproj
    outf = b.gelu_new(n2s @ data["fc_weight"].T + bfc) @ data["mlp_proj_weight"].T + bproj
    for variant in ("chain", "timeline"):
        if variant == "chain":
            page, verify = chain_page(a.layer, qfc, bfc, qproj, bproj, gfc, gproj, n2s, out)
        else:
            page, verify = timeline_page(a.layer, qfc, bfc, qproj, bproj, n2s, out)
        pid = f"b-{variant}-L{a.layer}"
        (out / f"{pid}.html").write_text(page)
        meta = {
            "id": pid,
            "file": f"{pid}.html",
            "variant": variant,
            "bytes": len(page),
            "verify": verify,
            "expected": outq.tolist(),
            "expected_float": outf.tolist(),
            "hidden_absmax": [float(np.max(np.abs(r))) for r in hidden],
            "fonts": {"fc": [str(gfc[0] / n) for n in gfc[1].names], "proj": [str(gproj[0] / n) for n in gproj[1].names]},
        }
        (out / f"{pid}.json").write_text(json.dumps(meta))
        print(pid, len(page), "bytes;", "quantised-vs-float witness RMSE", float(np.sqrt(np.mean((outq - outf) ** 2))))


if __name__ == "__main__":
    main()
