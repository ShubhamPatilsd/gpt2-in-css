"""Flat rule index of a runtime.css: one line per style rule as (context, selector, decls).
Usage: python3 cssindex.py runtime.css out.jsonl ; then grep the jsonl."""
import sys, json
def rules(css):
    out=[]; ctx=[]; i=0; n=len(css); buf=[]
    depth=0
    while i<n:
        c=css[i]
        if c=='{':
            head=''.join(buf).strip(); buf=[]
            # is it a block containing nested rules? look ahead for the first of { or }
            j=i+1
            while j<n and css[j] not in '{}': j+=1
            if j<n and css[j]=='{' and head.startswith('@') and not head.startswith('@font-face') and not head.startswith('@property'):
                ctx.append(head); i+=1; continue
            # keyframes with nested from/to blocks
            if head.startswith('@keyframes'):
                # skip whole block
                d=1; k=i+1
                while k<n and d>0:
                    if css[k]=='{': d+=1
                    elif css[k]=='}': d-=1
                    k+=1
                out.append((tuple(ctx),head,css[i+1:k-1])); i=k; continue
            k=css.find('}',i)
            out.append((tuple(ctx),head,css[i+1:k])); i=k+1; continue
        if c=='}':
            if ctx: ctx.pop()
            buf=[]; i+=1; continue
        buf.append(c); i+=1
    return out
if __name__=='__main__':
    css=open(sys.argv[1]).read()
    with open(sys.argv[2],'w') as f:
        for ctx,sel,dec in rules(css):
            f.write(json.dumps({'ctx':list(ctx),'sel':sel,'dec':dec})+'\n')
    print('rules',sum(1 for _ in open(sys.argv[2])))
