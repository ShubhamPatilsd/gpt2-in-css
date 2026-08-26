#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Capability/accuracy gate: real q9 768 -> 32 -> 32 internal MLP tile."""
import json
import time
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.otlLib.builder import buildStatTable
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore
from benchmark_audit_followups import OUT, ROOT, snapshot, save
import build_avar2_hvar_real_gpt2_tile as tile
from browser_gpt2_core import layer_matrices
from build_gpt2_block_css import global_axis_tag
from build_matrix_backend_prototypes import build_direct_font_backend
from probe_native_value_latch import attribute, navigate
from profile_hybrid_twelve_block import browser, query, error
from benchmark_browser_gpt2_memory import MemorySampler

DEST=OUT/'fusion'
AXES=769;HIDDEN=32;OUTPUTS=32
INPUT_SCALE=16.;PRE_SCALE=16.;OUTPUT_SCALE=2048.;BASE=24000
KNOTS=np.linspace(-1,1,129)
TOKENS=(15496,7454,464,1212,11,318,257,995)

def main():
    snapshot('fusion',[__import__('pathlib').Path(__file__),__import__('pathlib').Path(tile.__file__)])
    started=time.perf_counter()
    tensors=tile.SafeTensors(tile.MODEL_PATH)
    data,matrices,biases=layer_matrices(tensors,0)
    fc=matrices[2].reconstructed[:HIDDEN,:]
    projection=matrices[3].reconstructed[:OUTPUTS,:HIDDEN]
    bias=biases[2][:HIDDEN]
    inputs=np.stack([tile.block_zero_mlp_input(t,tensors) for t in TOKENS])
    encoded=np.concatenate((inputs/INPUT_SCALE,np.ones((len(inputs),1))),axis=1)
    pre=inputs@fc.T+bias
    assert np.max(np.abs(encoded))<=1
    assert np.max(np.abs(pre/PRE_SCALE))<=1
    tags=[global_axis_tag(i) for i in range(AXES)]
    matrix=np.eye(AXES)
    matrix[:HIDDEN,:768]=fc*INPUT_SCALE/PRE_SCALE
    matrix[:HIDDEN,768]=bias/PRE_SCALE
    path=DEST/'fused-full-input.ttf'
    scaffold=DEST/'scaffold-256.ttf'
    build_direct_font_backend(np.zeros((OUTPUTS,256),dtype=np.int16),scaffold,signed_axes=True,base_advance=BASE,codepoint_start=0xE000,axis_tags=tags[:256])
    font=TTFont(scaffold,recalcTimestamp=False)
    for tag in tags[256:]:
        axis=Axis();axis.axisTag=tag;axis.minValue=-1;axis.defaultValue=0;axis.maxValue=1;axis.flags=0
        axis.axisNameID=font['name'].addName(tag)
        font['fvar'].axes.append(axis)
    buildStatTable(font,[{'tag':a.axisTag,'name':a.axisNameID,'ordering':i} for i,a in enumerate(font['fvar'].axes)])
    supports=[];indexed=[]
    for h,tag in enumerate(tags[:HIDDEN]):
        for k,knot in enumerate(KNOTS):
            if knot==0:continue
            supports.append({tag:(float(KNOTS[max(0,k-1)]),float(knot),float(KNOTS[min(len(KNOTS)-1,k+1)]))})
            indexed.append((h,float(knot)))
    rows=[[0]*len(supports)]
    for out in range(OUTPUTS):
        rows.append([round(float(projection[out,h]*tile.gelu(knot*PRE_SCALE)*OUTPUT_SCALE)) for h,knot in indexed])
    assert max(abs(x) for row in rows for x in row)<=32767
    regions=buildVarRegionList(supports,tags)
    font['HVAR'].table.VarStore=buildVarStore(regions,[buildVarData(range(len(supports)),rows,optimize=True)])
    tile.add_avar2(font,tags,matrix)
    font.save(path)
    # TTF avoids generating a redundant compressed bank for a one-font gate.
    represented=np.interp(pre,KNOTS*PRE_SCALE,tile.gelu(KNOTS*PRE_SCALE))@projection.T
    exact=tile.gelu(pre)@projection.T
    def settings(vector):return ','.join(f'"{tag}" {float(v):.12g}' for tag,v in zip(tags,vector,strict=True))
    html='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\'"><style>@font-face{font-family:Fused;src:url("'+path.as_uri()+'")}.outputs{font:1000px Fused;font-kerning:none;font-variation-settings:'+settings(encoded[0])+'}i{display:block;position:absolute;left:0;top:0;width:max-content;height:1px;font-style:normal}</style><body><div class="outputs">'+''.join(f'<i id="o{i}">&#x{0xE000+i:X};</i>' for i in range(OUTPUTS))+'</div></body>'
    (DEST/'index.html').write_text(html)
    report={'shape':[768,HIDDEN,OUTPUTS],'axes':AXES,'fixedInputScale':INPUT_SCALE,'fixedPreactivationScale':PRE_SCALE,
        'knots':len(KNOTS),'tokenIds':TOKENS,'sourceWeights':'existing reconstructed q9 L0 FC and projection slice',
        'projectionBiasIncluded':False,'scope':'capability and arithmetic gate for a partial hidden/output tile, not full MLP',
        'runtimeJavaScript':False,'harnessJavaScript':False,'inputMax':float(abs(inputs).max()),'preactivationMax':float(abs(pre).max()),
        'buildSeconds':time.perf_counter()-started,'fontBytes':path.stat().st_size,
        'gate':{'representedRmse':.005,'exactRmse':.005,'exactMaximum':.02},'samples':[],'passed':False}
    save(DEST/'results.json',report)
    try:
        with browser(['--js-flags=--heap-growing-percent=10']) as cdp,MemorySampler(cdp.browser_pid) as memory:
            report['browser']=cdp.command('Browser.getVersion')
            first=navigate(cdp,DEST/'index.html','#o0',limit=90)
            owner=query(cdp,'.outputs');nodes=[query(cdp,f'#o{i}') for i in range(OUTPUTS)]
            fonts=[]
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                fonts=cdp.command('CSS.getPlatformFontsForNode',{'nodeId':first})['fonts']
                if any(f['isCustomFont'] for f in fonts):break
                time.sleep(.05)
            report['fonts']=fonts
            if not any(f['isCustomFont'] for f in fonts):raise ValueError('Full-input fused font fell back')
            for index in [*range(len(TOKENS)),0]:
                start=time.perf_counter()
                attribute(cdp,owner,'style','font-variation-settings:'+settings(encoded[index]))
                actual=[]
                for node in nodes:
                    box=cdp.command('DOM.getBoxModel',{'nodeId':node})['model']['content']
                    actual.append(((box[2]-box[0])-BASE)/OUTPUT_SCALE)
                e=error(actual,exact[index]);r=error(actual,represented[index])
                row={'index':index,'milliseconds':(time.perf_counter()-start)*1000,'actual':actual,'exactError':e,'representedError':r,
                    'passed':e['rmse']<.005 and e['maximum']<.02 and r['rmse']<.005}
                report['samples'].append(row)
                save(DEST/'results.json',report)
                print(json.dumps({k:v for k,v in row.items() if k!='actual'}),flush=True)
            report['peakRendererRssMiB']=max(s['rendererRssMiB'] for s in memory.samples)
            report['passed']=all(s['passed'] for s in report['samples']) and len(report['samples'])==9
    except Exception as exc:report['exception']=f'{type(exc).__name__}: {exc}'
    save(DEST/'results.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)

if __name__=='__main__':main()
