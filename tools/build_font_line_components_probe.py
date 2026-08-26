#!/usr/bin/env python3
"""Test whether font metric overrides expose MVAR line components separately."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"experiments"/"font-line-components-probe"
INPUTS=8; UPEM=1000; SIZE=512; ASC=1000; DESC=-500; GAP=500
def tag(i): return f"X{i:03d}"
def shape():
 p=TTGlyphPen(None);p.moveTo((0,0));p.lineTo((1,0));p.lineTo((1,1));p.lineTo((0,1));p.closePath();return p.glyph()
def main():
 OUT.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(0x4C494E45)
 w=rng.integers(-20,21,size=(3,INPUTS),dtype=np.int16);x=rng.integers(-4,5,size=INPUTS).astype(float)/4
 fb=FontBuilder(UPEM,isTTF=True);glyphs=[".notdef","zero"]
 fb.setupGlyphOrder(glyphs);fb.setupCharacterMap({0x30:"zero"});s=shape();fb.setupGlyf({g:s for g in glyphs})
 fb.setupHorizontalMetrics({g:(500,0) for g in glyphs});fb.setupHorizontalHeader(ascent=ASC,descent=DESC,lineGap=GAP)
 fb.setupNameTable({"familyName":"LineParts","styleName":"Regular","fullName":"LineParts Regular","psName":"LineParts-Regular"})
 fb.setupOS2(version=4,sTypoAscender=ASC,sTypoDescender=DESC,sTypoLineGap=GAP,usWinAscent=ASC,usWinDescent=-DESC,fsSelection=0xC0)
 fb.setupPost();fb.setupMaxp();fb.setupHead(created=2082844800,modified=2082844800);fb.font.recalcTimestamp=False
 path=OUT/"line-parts.ttf";fb.save(path);f=TTFont(path,recalcTimestamp=False)
 tags=[tag(i) for i in range(INPUTS)];fv=newTable("fvar");fv.axes=[];fv.instances=[];stat=[]
 for i,t in enumerate(tags):
  a=Axis();a.axisTag=t;a.minValue=-1;a.defaultValue=0;a.maxValue=1;a.flags=0;a.axisNameID=f["name"].addName(t);fv.axes.append(a);stat.append({"tag":t,"name":a.axisNameID,"ordering":i})
 f["fvar"]=fv;buildStatTable(f,stat);supports=[]
 for t in tags:supports.extend(({t:(-1,-1,0)},{t:(0,1,1)}))
 regions=buildVarRegionList(supports,tags)
 enc=lambda row:[d for v in row.tolist() for d in(-int(v),int(v))]
 data=buildVarData(range(len(supports)),[enc(row) for row in w],optimize=True)
 m=newTable("MVAR");m.table=otTables.MVAR();m.table.Version=0x10000;m.table.Reserved=0;m.table.VarStore=buildVarStore(regions,[data]);m.table.ValueRecordSize=8;m.table.ValueRecordCount=3
 rec=[]
 for t,i in (("hasc",0),("hdsc",1),("hlgp",2)):
  r=otTables.MetricsValueRecord();r.ValueTag=t;r.VarIdx=i;rec.append(r)
 m.table.ValueRecord=sorted(rec,key=lambda r:r.ValueTag);f["MVAR"]=m;f.recalcTimestamp=False;f.save(path)
 settings=",".join(f'"{tag(i)}" {v:g}' for i,v in enumerate(x))
 html=f'''<!doctype html><meta charset="utf-8"><style>
@font-face{{font-family:Asc;src:url("line-parts.ttf");descent-override:0%;line-gap-override:0%}}
@font-face{{font-family:Desc;src:url("line-parts.ttf");ascent-override:0%;line-gap-override:0%}}
@font-face{{font-family:Gap;src:url("line-parts.ttf");ascent-override:0%;descent-override:0%}}
@property --asc{{syntax:"<number>";inherits:true;initial-value:-99999}}@property --desc{{syntax:"<number>";inherits:true;initial-value:-99999}}@property --gap{{syntax:"<number>";inherits:true;initial-value:-99999}}
.a{{font:{SIZE}px/normal Asc;font-variation-settings:{settings};--asc:calc(1lh / 1px * {UPEM} / {SIZE} - {ASC})}}
.d{{font:{SIZE}px/normal Desc;font-variation-settings:{settings};--desc:calc({-DESC} - 1lh / 1px * {UPEM} / {SIZE})}}
.g{{font:{SIZE}px/normal Gap;font-variation-settings:{settings};--gap:calc(1lh / 1px * {UPEM} / {SIZE} - {GAP})}}
#result{{font:14px monospace}}
</style><div class="a"><div class="d"><div class="g"><div id="result">ready</div></div></div></div>'''
 (OUT/"index.html").write_text(html);expected=w.astype(float)@x
 (OUT/"reference.json").write_text(json.dumps({"expected":expected.tolist(),"weights":w.tolist(),"inputs":x.tolist()},indent=2)+"\n")
 print({"expected":expected.tolist(),"font_bytes":path.stat().st_size})
if __name__=="__main__":main()
