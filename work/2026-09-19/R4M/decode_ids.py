"""R4M: decode a list of GPT-2 ids (JSON list or a reference_ids JSON with freeRunningReference) to text with the tools tokenizer.
usage: PYTHONPATH=tools python3 decode_ids.py <json-file-or-ids> [prompt-token]"""
import json, sys, pathlib
from build_pretrained_gpt2 import Gpt2Tokenizer
ROOT = pathlib.Path("/Users/shubhampatil/Documents/programming/gpt2-css")
codec = Gpt2Tokenizer(ROOT / "data/gpt2/vocab.json", ROOT / "data/gpt2/merges.txt")
arg = sys.argv[1]
d = json.load(open(arg)) if arg.endswith(".json") else json.loads(arg)
ids = d if isinstance(d, list) else (d.get("freeRunningReference") or d["teacherForcedReference"])
prompt = int(sys.argv[2]) if len(sys.argv) > 2 else (d.get("promptToken") if isinstance(d, dict) else None) or 15496
print(repr(codec.decode_token(prompt) + "".join(codec.decode_token(t) for t in ids)))
