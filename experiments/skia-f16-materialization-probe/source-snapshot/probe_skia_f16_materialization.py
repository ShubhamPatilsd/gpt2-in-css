#!/usr/bin/env python3
"""Test a custom-browser precision premise using real standalone Skia surfaces.

This is a CPU Skia experiment, not Chromium and not browser inference. Every
stage is drawn into a new raster surface and snapshotted before the next draw;
Python observes float pixels but does not feed calculated answers into the chain.
"""
from __future__ import annotations

import json
from pathlib import Path
import platform
import statistics
import time

import numpy as np
import skia

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "skia-f16-materialization-probe"
SAMPLES = 64
N = SAMPLES + 2  # One guard pixel at each edge; only interior samples are scored.
TYPES = {"RGBA8": skia.kRGBA_8888_ColorType,
         "RGBA16F": skia.kRGBA_F16_ColorType,
         "RGBA32F": skia.kRGBA_F32_ColorType}


def matrix(scale=1.0, offset=0.0):
    return skia.ImageFilters.ColorFilter(skia.ColorFilters.Matrix([
        scale,0,0,0,offset, 0,scale,0,0,offset, 0,0,scale,0,offset, 0,0,0,1,0]))


def render(source, image_filter, color_type):
    info = skia.ImageInfo.Make(N, 1, color_type, skia.kPremul_AlphaType)
    surface = skia.Surface.MakeRaster(info)
    if surface is None:
        raise RuntimeError(f"unsupported raster format {color_type}")
    paint = skia.Paint(ImageFilter=image_filter, AntiAlias=False)
    surface.getCanvas().drawImage(source, 0, 0, paint=paint)
    image = surface.makeImageSnapshot()
    return image, {"surfaceColorType": str(surface.imageInfo().colorType()),
                   "snapshotColorType": str(image.colorType()),
                   "minimumRowBytes": info.minRowBytes()}


def observed(image):
    return image.toarray(colorType=skia.kRGBA_F32_ColorType)[0,1:-1,0].astype(np.float64)


def chain(name, base, barrier=None, collect=True, spatial="ramp"):
    order=np.arange(N,dtype=np.float64)
    if spatial=="permuted":
        order=np.random.default_rng(20260917).permutation(order)
    encoded = base + order/65535.0
    # Source only encodes a uniform ramp. The small values are computed by Skia.
    array = np.ones((1,N,4),dtype=np.float32)
    array[0,:,:3] = (order.astype(np.float32)/(N-1))[:,None]
    current = skia.Image.fromarray(array, colorType=skia.kRGBA_F32_ColorType)
    ct = TYPES[name]
    stages=[]
    exact = encoded.copy()

    def apply(label, filter_value, expected, override=None):
        nonlocal current
        current, info = render(current, filter_value, override or ct)
        if collect:
            values = observed(current)
            expected=expected[1:-1]
            stages.append({"stage":label, **info, "distinctValues":len(np.unique(values)),
                           "expectedDistinctValues":len(np.unique(expected)),
                           "nondecreasing":bool(np.all(np.diff(values)>=0)),
                           "maxAbsoluteError":float(np.max(np.abs(values-expected))),
                           "rmse":float(np.sqrt(np.mean((values-expected)**2))),
                           "values":values.tolist(), "expected":expected.tolist()})

    apply("encode", matrix((N-1)/65535.0,base),exact)
    original = current
    if barrier == "byte-table":
        table=list(range(256))
        transfer=skia.ImageFilters.ColorFilter(skia.TableColorFilter.MakeARGB(table,table,table,table))
        apply("identity-byte-table",transfer,exact)
    elif barrier == "one-rgba8-surface":
        apply("one-rgba8-surface",matrix(),exact,TYPES["RGBA8"])
    exact=exact*0.5
    apply("multiply",matrix(0.5),exact)
    exact=(np.pad(exact,(1,1),mode="edge")[:-2]+np.pad(exact,(1,1),mode="edge")[1:-1]
           +np.pad(exact,(1,1),mode="edge")[2:])/3
    reduction=skia.ImageFilters.MatrixConvolution(skia.ISize(3,1),[1,1,1],1/3,0,
                skia.IPoint(1,0),skia.TileMode.kClamp,False)
    apply("neighbor-reduction",reduction,exact)
    exact=exact+exact**2
    # skia-python clones embedded images/filters. The first embedded-image attempt
    # lost float precision. A source-relative
    # identity filter supplies the required non-null background without an image.
    current_filter=skia.ImageFilters.Offset(0,0)
    apply("nonlinear-x-plus-square",skia.ImageFilters.Arithmetic(1,1,0,0,True,current_filter),exact)
    exact=exact+encoded*0.125
    # Pack both actual snapshots into a two-row source using Skia draws. This
    # retains a residual branch without serializing an embedded-image filter.
    packed=skia.Surface.MakeRaster(skia.ImageInfo.Make(N,2,ct,skia.kPremul_AlphaType))
    packed.getCanvas().drawImage(current,0,0)
    packed.getCanvas().drawImage(original,0,1)
    current=packed.makeImageSnapshot()
    saved=skia.ImageFilters.Offset(0,-1)
    apply("residual-add",skia.ImageFilters.Arithmetic(0,1,0.125,0,True,saved),exact)
    origin=(0.5*base)+(0.5*base)**2+0.125*base
    exact=np.clip((exact-origin)*512+0.05,0,1)
    apply("amplify-for-display",matrix(512,0.05-origin*512),exact)
    return stages


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    configurations=[(base,"ramp",name,barrier) for base in (0.0,0.5)
        for name,barrier in [(x,None) for x in TYPES]+[("RGBA16F","byte-table"),("RGBA16F","one-rgba8-surface")]]
    configurations += [(base,"permuted",name,None) for base in (0.0,0.5) for name in TYPES]
    for base,spatial,name,barrier in configurations:
        stages=chain(name,base,barrier,spatial=spatial)
        warm=[]
        for i in range(65):
            t=time.perf_counter()
            chain(name,base,barrier,collect=False,spatial=spatial)
            elapsed=(time.perf_counter()-t)*1000
            if i>=5: warm.append(elapsed)
        results.append({"format":name,"base":base,"spatialInput":spatial,"barrier":barrier,"stages":stages,
                        "warmCpuChainMedianMs":statistics.median(warm),"timingSamples":len(warm)})
    report={"skiaPythonVersion":skia.__version__,"platform":platform.platform(),
            "backend":"standalone Skia CPU raster; no Chromium integration or GPU test",
            "sampleCount":SAMPLES,"sourceWidthIncludingGuards":N,"separation":1/65535,"cases":results,
            "materialization":"Each stage uses a distinct explicit raster surface; actual surface and snapshot formats recorded.",
            "inferenceLocation":"Skia filters; NumPy only creates input samples and computes reference/readback errors",
            "timingScope":"Diagnostic CPU time includes NumPy fixture/oracle arithmetic, Python dispatch and surface allocation; not isolated Skia time."}
    float_control = [c for c in results if c["format"]=="RGBA32F" and c["barrier"] is None]
    report["floatControlPassed"] = all(s["maxAbsoluteError"] < 0.0002 for c in float_control for s in c["stages"])
    if not report["floatControlPassed"]:
        raise AssertionError("float32 control disagrees with the oracle; do not interpret precision results")
    (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    rows=[]
    for case in results:
        stages=case["stages"]
        levels=" → ".join(str(x["distinctValues"]) for x in stages)
        rows.append(f"| {case['base']} | {case['spatialInput']} | {case['format']} | {case['barrier'] or 'none'} | {levels} | {case['warmCpuChainMedianMs']:.3f} |")
    (OUT/"RESULTS.md").write_text(
        "# Standalone Skia materialization precision probe\n\n"
        "This tests a prerequisite for the custom-Chromium idea using skia-python's real CPU renderer. "
        "It does not patch Chromium, exercise Blink, demonstrate SVG GPU precision, or measure token speed. "
        "The normal browser/model was not modified.\n\n"
        "64 interior uniformly separated numbers (step 1/65535), plus two guard pixels, are computed from a ramp by Skia, then passed through "
        "multiply → three-neighbor reduction → x+x² → residual addition → display amplification. Each stage "
        "is rendered into a fresh surface and snapshotted. Actual surface/snapshot types are recorded. "
        "Readback does not feed results into subsequent computation. A saved encoded branch feeds residual addition. "
        "Only the 64 interior samples are scored, avoiding the renderer's padded-source edge behavior in convolution. "
        "The float32 control must match the analytical oracle within 0.0002 at every stage. "
        "Permuted-input cases independently test nontrivial spatial reduction: unlike the ramp, their interior "
        "values change under neighborhood averaging. Their mathematically expected distinct-value counts "
        "can be below 64 after averaging and are included in JSON; uniqueness alone is not their accuracy gate. "
        "The RGBA32F path is an accuracy control; it is not proposed as available in stock SVG.\n\n"
        "| Input base | Spatial input | Format | Extra barrier after encoding | Distinct levels at successive stages | Diagnostic CPU ms |\n"
        "|---|---|---|---|---|---|\n"+"\n".join(rows)+"\n\n"
        "These timings include NumPy fixture/oracle arithmetic, Python dispatch and allocation of explicit tiny surfaces; they are diagnostic "
        "and cannot predict browser or full-matrix performance. Sixty samples follow five warmups. "
        "A later residual branch can restore levels lost in the main branch, so the pass condition must inspect "
        "every stage rather than only the final pixel count. Numerical errors and all values are in results.json.\n\n"
        "F16 has limited relative precision; densely spaced numbers around 0.5 are a deliberately hard case. "
        "Even if near-zero samples survive, this does not guarantee GPT-2 accuracy. A single byte table or "
        "RGBA8 allocation is independently tested, because changing only a destination format cannot fix those. "
        "A real Chromium experiment would require equivalent format instrumentation in the SVG filter path and "
        "full-model numerical checks.\n\n"
        "Two construction corrections are important. The initial embedded-image filter children lost precision "
        "when passed through skia-python's cloning bindings; source-relative filters plus a two-row residual source "
        "avoid that extra serialization path. The initial convolution error metric also included source edges, "
        "where Skia's padded filter input differs from the analytical edge-clamp assumption. Guard pixels and the "
        "float32 numerical assertion correct that test-fixture error. Earlier artifacts are retained under "
        "binding-image-clone-attempt-* and unguarded-attempt-*; they are not evidence that arithmetic itself "
        "cannot preserve float values. The binding uses CloneImage/CloneFlattenable in its "
        "[source](https://raw.githubusercontent.com/kyamagu/skia-python/main/src/skia/ImageFilter.cpp).\n\n"
        "Reproduce:\n\n```sh\npython3 tools/run_unconventional_isolated.py --label skia-f16 -- "
        "uv run --python 3.12 --with skia-python==144.0.post2 --with numpy "
        "python tools/probe_skia_f16_materialization.py\n```\n")
    print(json.dumps({"cases":len(results),"skia":skia.__version__,"rows":rows},indent=2))


if __name__=="__main__":
    main()
