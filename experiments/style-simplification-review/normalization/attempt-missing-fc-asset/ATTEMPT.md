# Asset-location failure before complete results

The isolated Python 3.11 run generated the declared inputs, verified layer-0 QKV
font weights, and calculated that matrix's 56 cases. It then stopped because the
analyzer assumed `gpt2-block-css/fc-rowbase-s0.woff2` existed. The actual current
compiler falls back to `hybrid-12block-profile/fonts/b0-fc-s0.woff2` when that
preferred bank is absent. No complete report or gate decision was produced.

The exact inputs and source snapshot are preserved here. The repair follows the
existing compiler's asset preference/fallback and checkpoints partial reports
after each matrix. Cases, arithmetic, rounding models, and thresholds are
unchanged. This failure is not excluded numerical evidence; no numeric outcome
was available from the stopped run.
