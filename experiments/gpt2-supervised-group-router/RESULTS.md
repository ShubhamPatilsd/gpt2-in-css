# Supervised GPT-2 vocabulary-group router

A deterministic screen tested whether the final 768-value GPT-2 state can
route evaluation into a few of the existing 197 contiguous 256-token groups.
The dataset has 1,024 full 12-layer states: equal uniform-random and local-text
contexts at lengths 2, 4, 8, and 16. Each source/length stratum is split into
64 training, 32 validation, and 32 test states, for 512/256/256 overall.

Two router families were tested:

- a 151,493-weight linear ridge classifier/regressor; and
- exact scoring of the tokens most often locally maximal within each group on
  training states.

The held-out frontier is:

| Router | Scored rows | Top 1 | Top 2 groups | Top 8 groups |
| --- | ---: | ---: | ---: | ---: |
| Majority groups 0/1 | 0 | 43.0% | 70.3% | — |
| Linear ridge, group-score target | 197 outputs | 59.4% | 75.4% | 84.8% |
| 4 representatives/group | 788 | 62.9% | 71.5% | 79.3% |
| 64 representatives/group | 12,608 | 85.5% | 87.5% | 90.6% |
| 128 representatives/group | 25,216 | 92.2% | 93.0% | 94.9% |
| 192 representatives/group | 37,824 | 95.3% | 96.1% | 97.7% |
| 256 representatives/group | 50,432 slots | 100% | 100% | 100% |

The ridge margin is not a dependable guard. Calibrating a zero-error
validation threshold accepts only 17/256 test cases for the group-score model;
those 17 happen to be correct, but 93% of states still require fallback. The
64-representative margin accepts 21/256 and already makes one error.

Contiguous token-ID groups therefore have no useful exact routing frontier.
Even evaluating 75% of the vocabulary misses ten test states, and exactness
returns only with every row. Reject this route for the frozen checkpoint.

## Reproduce

```sh
make analyze-gpt2-supervised-group-router
```
