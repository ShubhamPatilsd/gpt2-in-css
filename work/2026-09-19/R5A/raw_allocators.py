#!/usr/bin/env python3
"""R5A: raw memory-infra allocator attributes per renderer dump (small traces). usage: raw_allocators.py trace.json.gz run.json out.json"""
import gzip,json,collections,sys
trace,runp,outp=sys.argv[1:4]
def events(path, chunk=1<<24):
    DEC=json.JSONDecoder(); f=gzip.open(path,"rt",encoding="utf-8",errors="replace"); buf=f.read(chunk); idx=buf.find("[")+1
    while True:
        while True:
            while idx<len(buf) and buf[idx] in " \r\n\t,": idx+=1
            if idx>=len(buf):
                more=f.read(chunk)
                if not more: return
                buf=buf[idx:]+more; idx=0; continue
            break
        if buf[idx]=="]": return
        try: obj,end=DEC.raw_decode(buf,idx)
        except json.JSONDecodeError:
            more=f.read(chunk)
            if not more: return
            buf=buf[idx:]+more; idx=0; continue
        idx=end
        if idx>len(buf)//2 and len(buf)>chunk:
            buf=buf[idx:]; idx=0; more=f.read(chunk)
            if more: buf+=more
        yield obj
run=json.load(open(runp)); tag={m["dumpGuid"]:m["tag"] for m in run.get("memdumps",[]) if m.get("dumpGuid")}
def hv(a):
    v=a.get("value") if isinstance(a,dict) else a
    if isinstance(v,str):
        try: return int(v,16)
        except ValueError: return None
    return v
D=collections.defaultdict(dict); pidname={}; ult=collections.Counter()
for e in events(trace):
    if e.get("ph")=="M" and e.get("name")=="process_name": pidname[e["pid"]]=e["args"]["name"]
    if e.get("name")=="UpdateLayoutTree": ult[e["pid"]]+=1
    if e.get("ph")!="v": continue
    d=e["args"]["dumps"]; k=(e["pid"],e["id"])
    D[k].setdefault("ts",e["ts"]); D[k].setdefault("level",d.get("level_of_detail"))
    for kk,v in (d.get("process_totals") or {}).items():
        x=hv(v); 
        if isinstance(x,int): D[k]["tot:"+kk]=x
    for name,ad in (d.get("allocators") or {}).items():
        for an,av in (ad.get("attrs") or {}).items():
            x=hv(av)
            if isinstance(x,int): D[k][name+"|"+an]=x
ren=ult.most_common(1)[0][0]
rows=sorted([(k,v) for k,v in D.items() if k[0]==ren], key=lambda kv: kv[1]["ts"])
MB=lambda x: f"{(x or 0)/2**20:,.0f}"
sel=["tot:resident_set_bytes","tot:private_footprint_bytes","tot:peak_resident_set_bytes","blink_gc/main/heap|size","blink_gc/main/allocated_objects|size","malloc|size","malloc/allocated_objects|size","partition_alloc/partitions/buffer|size","partition_alloc/allocated_objects|size","web_cache|size","skia|size","font_caches|size","discardable|size","v8|size","blink_objects|size"]
print("| dump | level | "+" | ".join(s.replace("|size","").replace("tot:","") for s in sel)+" |"); print("|---|---|"+"---:|"*len(sel))
for k,v in rows: print("| "+tag.get(k[1],"(chrome)")+" | "+v["level"]+" | "+" | ".join(MB(v.get(s)) for s in sel)+" |")
print("\n--- detailed (final) dump: nodes >= 1 MB or counts ---")
fin=[v for k,v in rows if v["level"]=="detailed"]
if fin:
    fin=fin[-1]
    for kk,vv in sorted(((kk,vv) for kk,vv in fin.items() if kk!="ts" and isinstance(vv,int)), key=lambda kv:-kv[1]):
        if (kk.endswith("|size") and vv>=2**20) or kk.endswith("|object_count") or kk.endswith("|count") or kk.startswith("tot:") or "resident" in kk or "allocated_objects_size" in kk:
            print(f"{kk:90s} {vv/2**20:10.1f} MB  ({vv:,})")
json.dump({"renderer_pid":ren,"rows":[(tag.get(k[1]),v) for k,v in rows]}, open(outp,"w"))
