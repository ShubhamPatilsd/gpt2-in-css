# R5F: per-table anatomy + HVAR VarStore structure of one face (fontTools, in memory).
import sys, io, collections
from fontTools.ttLib import TTFont
def anatomy(path):
    raw=open(path,'rb').read()
    f=TTFont(io.BytesIO(raw), recalcBBoxes=False, recalcTimestamp=False, lazy=True)
    print(f'== {path}  flavor={f.flavor} woff2_bytes={len(raw):,}')
    reader=f.reader
    tabs=sorted(((t,reader.tables[t].length) for t in reader.keys()), key=lambda x:-x[1])
    sfnt=sum(l for _,l in tabs)
    print(f'  sfnt(decoded) bytes ≈ {sfnt:,}  ratio sfnt/woff2 = {sfnt/len(raw):.2f}')
    print('  tables:', ', '.join(f'{t.strip()} {l:,}' for t,l in tabs))
    ng=f['maxp'].numGlyphs; print(f'  numGlyphs {ng}')
    fv=f['fvar']; print(f'  fvar axes {len(fv.axes)} (min/def/max of first: {fv.axes[0].minValue},{fv.axes[0].defaultValue},{fv.axes[0].maxValue}) instances {len(fv.instances)}')
    if 'cmap' in f:
        cm=f['cmap']; print('  cmap subtables', [(s.platformID,s.platEncID,s.format,len(s.cmap)) for s in cm.tables])
    if 'hmtx' in f:
        hm=f['hmtx'].metrics; adv=[v[0] for v in hm.values()]; print(f'  hmtx advances min {min(adv)} max {max(adv)} distinct {len(set(adv))}')
    if 'glyf' in f:
        gl=f['glyf']; n_nonempty=sum(1 for g in f.getGlyphOrder() if gl[g].numberOfContours!=0); print(f'  glyf non-empty glyphs {n_nonempty}/{ng}, loca fmt {f["head"].indexToLocFormat}')
    if 'HVAR' in f:
        h=f['HVAR'].table; vs=h.VarStore
        print(f'  HVAR AdvWidthMap={"yes" if h.AdvWidthMap else "None(implicit gid)"} Lsb={h.LsbMap is not None} Rsb={h.RsbMap is not None}')
        rl=vs.VarRegionList; print(f'  VarRegionList: {rl.RegionCount} regions × {rl.RegionAxisCount} axes')
        # region summary
        sup=collections.Counter()
        for r in rl.Region:
            nz=[(i,(a.StartCoord,a.PeakCoord,a.EndCoord)) for i,a in enumerate(r.VarRegionAxis) if a.PeakCoord!=0]
            sup[len(nz)]+=1
        print(f'   regions by #active axes: {dict(sup)}; first 3: ', [[(i,(a.StartCoord,a.PeakCoord,a.EndCoord)) for i,a in enumerate(r.VarRegionAxis) if a.PeakCoord!=0] for r in rl.Region[:3]])
        # duplicates
        keys=[tuple((a.StartCoord,a.PeakCoord,a.EndCoord) for a in r.VarRegionAxis) for r in rl.Region]
        print(f'   distinct regions {len(set(keys))} of {len(keys)}')
        print(f'  VarData count {vs.VarDataCount}')
        tot_items=0; tot_bytes=0
        for k,vd in enumerate(vs.VarData):
            n=vd.ItemCount; c=vd.VarRegionCount
            long_words = bool(vd.NumShorts & 0x8000); ns=vd.NumShorts & 0x7fff
            wide = 4 if long_words else 2; narrow = 2 if long_words else 1
            row_bytes = ns*wide + (c-ns)*narrow
            b= 6 + 2*c + n*row_bytes
            tot_items+=n; tot_bytes+=b
            # delta stats
            import itertools
            mx=0; cnt_small=0; total=0; hist=collections.Counter()
            for it in vd.Item:
                for d in it:
                    ad=abs(d); total+=1
                    if ad<128: cnt_small+=1
                    mx=max(mx,ad); hist[ad.bit_length()]+=1
            # columns that could be narrow
            colmax=[0]*c
            for it in vd.Item:
                for j,d in enumerate(it):
                    if abs(d)>colmax[j]: colmax[j]=abs(d)
            narrow_cols=sum(1 for m in colmax if m<128)
            zero_cols=sum(1 for m in colmax if m==0)
            print(f'   VarData[{k}]: items {n} × regions {c}, NumShorts {ns} LONG_WORDS={long_words} → row {row_bytes} B, subtable {b:,} B; max|δ| {mx}; |δ|<128: {cnt_small/total*100:.1f}%; cols with max<128: {narrow_cols}, all-zero cols {zero_cols}; |δ| bit-length hist {dict(sorted(hist.items()))}')
            print(f'     regionIndices first 8 {list(vd.VarRegionIndex[:8])} sorted? {list(vd.VarRegionIndex)==sorted(vd.VarRegionIndex)}')
        print(f'  VarStore total ≈ {tot_bytes:,} B for {tot_items} items')
    for t in ('name','post','STAT','GSUB','GPOS','GDEF','gvar','avar','OS/2','cvt ','fpgm','prep'):
        if t in reader.tables: pass
    if 'name' in f: print('  name records', len(f['name'].names))
    if 'post' in f: print('  post format', f['post'].formatType)
for p in sys.argv[1:]: anatomy(p)
