#!/bin/zsh
# R6X: R6P/reference_prompt.py with the MERGED tools -> R6X/scratch/reference_once.json, compared with R6P/reference_ids_once_upon_a_time.json
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
PYTHONPATH=tools nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli python ../R6P/reference_prompt.py "Once upon a time" scratch/reference_once.json 32 12 > logs/reference_once.log 2>&1; echo "rc=$?"
python3 - <<'PY'
import json
a = json.load(open("scratch/reference_once.json")); b = json.load(open("../R6P/reference_ids_once_upon_a_time.json"))
keys = ["promptTokens", "freeRunningReference", "winners", "generatedIds", "inputs", "generatedText"]
print({k: a.get(k) == b.get(k) for k in keys}); print("winners:", a["winners"])
PY
touch DONE-numpy-once
