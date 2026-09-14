# Nonlinear GPT-2 vocabulary-group router

A small ReLU router is attractive operationally because the existing HVAR and
`avar2` path can deploy it in hundreds of glyphs. This experiment trains
`768 → H → 197` networks on the 1,024-state contextual dataset. The loss is
winning-group cross-entropy plus a small exact group-maximum regression term;
three seeds are early-stopped by validation ranking.

| Hidden width | Parameters | Test top 1 | Test top 2 | Test top 8 |
| ---: | ---: | ---: | ---: | ---: |
| 128 | 123,845 | 57.8% | 67.6% | 78.9% |
| 256 | 247,493 | 59.8% | 73.4% | 80.9% |
| Linear ridge baseline | 151,493 | **62.9%** | **74.6%** | **81.6%** |

The nonlinear router does not learn a compact surrogate for each group's
maximum of 256 unrelated linear token scores. Its validation-zero-error margin
also fails out of sample: width 256 accepts 24/256 test states, but only 20 are
correct. The architecture would be cheap in CSS, but its routing accuracy is
strictly inadequate. Reject it for the frozen checkpoint.

## Reproduce

```sh
make analyze-gpt2-nonlinear-group-router
```
