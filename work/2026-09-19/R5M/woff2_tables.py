# R5M: per-table decoded (origLength) sizes from WOFF2 table directories, no decompression.
import struct, sys, json, collections
KNOWN=['cmap','head','hhea','hmtx','maxp','name','OS/2','post','cvt ','fpgm','glyf','loca','prep','CFF ','VORG','EBDT','EBLC','gasp','hdmx','kern','LTSH','PCLT','VDMX','vhea','vmtx','BASE','GDEF','GPOS','GSUB','EBSC','JSTF','MATH','CBDT','CBLC','COLR','CPAL','SVG ','sbix','acnt','avar','bdat','bloc','bsln','cvar','fdsc','feat','fmtx','fvar','gvar','hsty','just','lcar','mort','morx','opbd','prop','trak','Zapf','Silf','Glat','Gloc','Feat','Sill']
def b128(b,i):
    v=0
    for _ in range(5):
        c=b[i]; i+=1; v=(v<<7)|(c&0x7f)
        if not c&0x80: return v,i
    raise ValueError
def tables(path):
    b=open(path,'rb').read(4096)
    assert b[:4]==b'wOF2', path
    n=struct.unpack('>H',b[12:14])[0]; i=48; out=[]
    for _ in range(n):
        fl=b[i]; i+=1; idx=fl&0x3f
        if idx==63: tag=b[i:i+4].decode('latin1'); i+=4
        else: tag=KNOWN[idx]
        orig,i=b128(b,i); tl=orig
        tr=(fl>>6)&3
        if (tag in('glyf','loca') and tr==0) or (tag not in('glyf','loca') and tr!=0): tl,i=b128(b,i)
        out.append((tag,orig))
    return out
rows=json.load(open('R5M/font_inventory.json'))
agg=collections.defaultdict(lambda:collections.Counter())
for r in rows:
    k=__import__('re').sub(r'\d+','N',r['family'])
    for tag,orig in tables(r['path']): agg[k][tag]+=orig
for k,c in sorted(agg.items(), key=lambda kv:-sum(kv[1].values())):
    tot=sum(c.values()); print(f'{k:16s} total {tot/1e6:8.1f} MB :', ', '.join(f'{t} {v/1e6:.1f}' for t,v in c.most_common(6)))
