import sys, re, collections
from html.parser import HTMLParser
path = sys.argv[1]
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.stack=[]; s.n=0; s.want={}; s.found={}; s.depth_hist=collections.Counter(); s.classdepth=collections.defaultdict(collections.Counter)
    def handle_starttag(s, tag, attrs):
        a=dict(attrs); cls=a.get('class',''); st=a.get('style','')
        key=(tag, cls.split(' ')[0] if cls else '', )
        s.stack.append((tag,cls,st[:60])); s.n+=1
        d=len(s.stack)
        c0 = cls.split(' ')[0] if cls else '('+tag+')'
        s.classdepth[c0][d]+=1
        for pat in s.want:
            if pat not in s.found and re.search(pat, cls+' '+st):
                s.found[pat]=[(i,t,c[:40],x) for i,(t,c,x) in enumerate(s.stack)]
        if tag in ('i','span','br','img','input','set','path','use','rect','g'):  # void-ish? no: i/span close normally; only treat true voids
            pass
        if tag in ('br','img','input','link','meta','path','use','rect'):
            s.stack.pop()
    def handle_endtag(s, tag):
        # pop to matching
        for i in range(len(s.stack)-1,-1,-1):
            if s.stack[i][0]==tag:
                del s.stack[i:]; break
p=P()
p.want={r'view-timeline:--shared-fc-t1155':None, r'view-timeline:--shared-proj-t82':None, r'view-timeline:--shared-qkv-t2230':None, r'view-timeline:--shared-attn-t7 ':None, r'view-timeline:--cache-bridge-t0':None, r'shared-fc-c47':None, r'fvs-score-3-2':None, r'view-timeline:--b11-bridge-t0':None, r'view-timeline:--embed-t0':None}
p.feed(open(path,encoding='utf-8',errors='replace').read())
print('elements',p.n)
for k,v in p.found.items():
    print('\n==',k,'depth',len(v))
    for i,t,c,x in v: print(f'  {i:3d} <{t} class="{c}" style="{x}">')
print('\nclass depth summary (selected):')
for c in ['metric','shared-fc','shared-fc-c0','shared-fc-c47','shared-proj','shared-qkv','shared-attn','scroller','track','fvs-value-row','fvs-score-reader','fvs-bank','head-row','core-controller']:
    if c in p.classdepth: print(' ',c, dict(sorted(p.classdepth[c].items())) if len(p.classdepth[c])<6 else (sum(p.classdepth[c].values()), 'depths', min(p.classdepth[c]), max(p.classdepth[c])))
