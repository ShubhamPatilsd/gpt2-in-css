# Real-dummy AlternateSet targeted result

This three-group/three-fixture probe tests whether a source glyph at AlternateSet index 1 caused the group-0/1 failures. It patches only score/base h3 and reuses the other full-bank faces.

FontTools verified score indices 1–4 as `probeDummy, y000, y256, y512` and correction indices 1–4 as `probeDummy, y256, y512, y768`. Chrome received real groups 0/1/2 at feature values 2/3/4.

Across 2,304 candidates, maximum absolute deltas by group were 8,694, 12,008, and 3. The first two groups retain the same huge failures while group 2 remains bounded. The self alternate is not causal; the failures track h3 correction advances crossing Chrome's 32,768 px adjusted-metric cap.
