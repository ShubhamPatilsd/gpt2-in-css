#!/bin/zsh
# R6X: NumPy references for the typed prompt "Shubham was" (ids 2484 549 2763 373; 4 teacher-forced + 28 generated) with the merged tools: 12 layers and the 2-layer smoke twin
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
PYTHONPATH=tools nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli python ../R6P/reference_prompt.py "Shubham was" reference_ids_shubham_was.json 32 12 > logs/reference_shubham.log 2>&1; echo "12L rc=$?"
PYTHONPATH=tools nice -n 19 uv run --with numpy --with fonttools --with pillow --with brotli python ../R6P/reference_prompt.py "Shubham was" reference_ids_shubham_was_2layers.json 32 2 > logs/reference_shubham_2l.log 2>&1; echo "2L rc=$?"
python3 -c "
import json
for f in ['reference_ids_shubham_was.json','reference_ids_shubham_was_2layers.json']:
    d=json.load(open(f)); print(f, d['promptTokens'], d['winners'], repr(d['fullText'][:200]), 'q==f', d.get('quantizedEqualsFloat'), 'tf', d.get('teacherForcedEqualsWinners'))"
touch DONE-numpy-shubham
