# Independent MNIST reference: parse weights + sample-0 pixels out of the shipped model.css and evaluate in NumPy.
import re, json, numpy as np
css = open("../../../model.css").read()
root = css[:css.index("}")]
vals = dict(re.findall(r"--([\w-]+): (-?[\d.]+);", root))
H = len([k for k in vals if k.startswith("hidden-bias-")])
W1 = np.array([[float(vals[f"hidden-w-{h:02d}-{p:03d}"]) for p in range(784)] for h in range(H)])
b1 = np.array([float(vals[f"hidden-bias-{h:02d}"]) for h in range(H)])
W2 = np.array([[float(vals[f"output-w-{c}-{h:02d}"]) for h in range(H)] for c in range(10)])
b2 = np.array([float(vals[f"output-bias-{c}"]) for c in range(10)])
out = {"hidden_units": H}
for s in range(10):
    blk = re.search(r":root:has\(#sample-%d:checked\) \{(.*?)\}" % s, css, re.S).group(1)
    x = np.zeros(784)
    for k, v in re.findall(r"--x-(\d+): (-?[\d.]+);", blk): x[int(k)] = float(v)
    sc = W2 @ np.maximum(0, W1 @ x + b1) + b2
    out[f"sample-{s}"] = {"pred": int(sc.argmax()), "scores": [round(float(v), 4) for v in sc]}
json.dump(out, open("mnist_reference.json", "w"), indent=1)
print("hidden units", H); [print(k, v["pred"], v["scores"]) for k, v in out.items() if k.startswith("sample")]
