import sys, json; sys.path.insert(0, "tools")
import numpy as np, build_transformer as bt
m = bt.make_model(); bt.fit_language_head(m)
out = {}
for p in bt.PROMPTS:
    ids = [bt.VOCAB.index(c) for c in p]; steps = []
    for s in range(bt.GENERATION_STEPS):
        t, lg = bt.predict(ids, m); ids.append(t)
        srt = np.sort(lg)
        steps.append({"step": s, "token_id": t, "token": bt.DISPLAY_TOKENS[t], "logits": [round(float(x), 6) for x in lg], "margin_top1_top2": round(float(srt[-1]-srt[-2]), 6)})
    out[p] = steps
json.dump(out, open("reference.json", "w"), indent=1)
for p, st in out.items():
    print(repr(p), "->", "".join(s["token"] for s in st), "| step1 logits", st[0]["logits"], "| min margin", min(s["margin_top1_top2"] for s in st))
