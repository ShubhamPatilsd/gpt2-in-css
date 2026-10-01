"""R6P: offline check of the OpenType BPE tokenizer fonts (tinystories/gpt2-token-id-{0,1}-full.ttf) against the Python GPT-2
tokenizer: for each prompt and position k, shape with hb-shape --features=p00k and decode id = (adv0 - 1) + 32767*(adv1 - 1)
(the fonts store digit+1 so a zero digit differs from an erased token whose advance is 0). usage: hb_check.py <font-dir> [positions]"""
import re, subprocess, sys
from pathlib import Path
from build_pretrained_gpt2 import Gpt2Tokenizer
ROOT = Path("/Users/shubhampatil/Documents/programming/gpt2-css")
fdir = Path(sys.argv[1]); positions = int(sys.argv[2]) if len(sys.argv) > 2 else 4
fonts = [fdir / f"gpt2-token-id-{p}-full.ttf" for p in range(2)]
tok = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
def adv(font, feat, text):
    out = subprocess.run(["hb-shape", f"--features={feat}", str(font), text], check=True, capture_output=True, text=True).stdout
    return sum(int(x) for x in re.findall(r"\+(-?\d+)", out))
prompts = ["I", "Once upon a time", "The little girl", "Hello", "There is no evidence", "After the first round", "Once upon a time, there was",
           " Once upon a time", "it's", "don't", "abc123", "Hello, world!", "2023", "A.J.", "I love you", "The dog", "Why is the sky blue?",
           "Breaking news", "She said", "In 1999", "e.g. this", "x = y+1", "Hello\nworld", "  two spaces", "café", "naïve"]
ok = bad = 0
for p in prompts:
    try:
        ids = tok.encode(p)
    except Exception as e:
        print(f"{p!r}: python tokenizer failed: {e}"); continue
    got = []
    for k in range(positions):
        a0, a1 = adv(fonts[0], f"p{k:03d}", p), adv(fonts[1], f"p{k:03d}", p)
        got.append(None if (a0 == 0 and a1 == 0) else (a0 - 1) + 32767 * (a1 - 1))
    exp = [ids[k] if k < len(ids) else None for k in range(positions)]
    match = got == exp
    ok += match; bad += not match
    print(f"{'ok ' if match else 'BAD'} {p!r}: python {ids} font {got}" + ("" if match else f" expected {exp}"))
print(f"{ok} ok, {bad} mismatching of {ok+bad} prompts")
