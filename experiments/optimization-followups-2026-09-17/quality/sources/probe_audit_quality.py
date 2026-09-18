#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "fonttools", "brotli", "pillow"]
# ///
"""Offline teacher-forced q9/q16 versus float quality beyond Hello."""
import json
from pathlib import Path
import numpy as np
from analyze_full_gpt2 import MODEL_PATH,SafeTensors
from browser_gpt2_core import reference_sequence
from build_pretrained_gpt2 import Gpt2Tokenizer
import build_gpt2_block_css as b
from build_gpt2_groupwise_production_q16_sixfont import AXIS_STEPS,SCORE_GAIN,WEIGHT_SCALE,R
from benchmark_audit_followups import OUT,ROOT,save,snapshot

PROMPTS=('The quick brown fox jumps over the lazy dog.',
         'Paris is the capital of France and Berlin is',
         'CSS can perform matrix multiplication without JavaScript.',
         'def fibonacci(n):\n    if n < 2:',
         'In 2026, the price was $19.95 per item.',
         'She said, "Why does this work?"')

def main():
    snapshot('quality',[Path(__file__),ROOT/'tools/browser_gpt2_core.py'])
    tokenizer=Gpt2Tokenizer(ROOT/'data/gpt2/vocab.json',ROOT/'data/gpt2/merges.txt')
    t=SafeTensors(MODEL_PATH)
    gamma=np.asarray(t.tensor('ln_f.weight'),dtype=np.float64);beta=np.asarray(t.tensor('ln_f.bias'),dtype=np.float64)
    weights=np.asarray(t.tensor('wte.weight'),dtype=np.float64)
    qweights=np.rint(weights/WEIGHT_SCALE)*WEIGHT_SCALE
    rows=[]
    for prompt in PROMPTS:
        tokens=tokenizer.encode(prompt)[:12]
        refs={key:reference_sequence(tokens,12,quantized=quantized) for key,quantized in (('q9',True),('float',False))}
        hidden={key:np.stack([b.layer_norm(np.asarray(v),gamma,beta) for v in ref['outputs']]) for key,ref in refs.items()}
        qh=np.rint(hidden['q9']/R*AXIS_STEPS)/AXIS_STEPS*R
        logits=qh@qweights.T
        # The head's exact observable winner includes integer score buckets.
        winners=np.rint(logits*SCORE_GAIN*256).argmax(1)
        floating=hidden['float']@weights.T
        fw=floating.argmax(1)
        order=np.argsort(floating,axis=1)[:,-2:]
        margins=floating[np.arange(len(tokens)),order[:,-1]]-floating[np.arange(len(tokens)),order[:,-2]]
        def log_probs(values):
            shifted=values-values.max(1,keepdims=True)
            return shifted-np.log(np.exp(shifted).sum(1,keepdims=True))
        qlog=log_probs(logits);flog=log_probs(floating)
        kl=np.sum(np.exp(flog)*(flog-qlog),axis=1)
        row={'prompt':prompt,'tokens':tokens,'positions':len(tokens),'q9Q16Winners':winners.tolist(),'floatWinners':fw.tolist(),
            'agreement':(winners==fw).tolist(),'floatTopTwoMargins':margins.tolist(),
            'floatToQuantizedKlNats':kl.tolist(),'logitRmse':np.sqrt(np.mean((logits-floating)**2,axis=1)).tolist(),
            'normalizedHeadRangeMaximum':float(np.max(np.abs(hidden['q9']))),'headAxisRange':R,
            'rangeExceeded':bool(np.any(np.abs(hidden['q9'])>R))}
        rows.append(row)
        save(OUT/'quality/results.json',{'scope':'Offline teacher forcing at up to12 positions for6 specified prompts. No CSS transport and no claim of broad language-model quality equivalence.',
            'runtimeChangeEvaluated':False,'rows':rows,'totalPositions':sum(r['positions'] for r in rows),
            'winnerAgreements':sum(sum(r['agreement']) for r in rows)})
        print(json.dumps({k:v for k,v in row.items() if k in ('prompt','positions','agreement','rangeExceeded')}),flush=True)

if __name__=='__main__':main()
