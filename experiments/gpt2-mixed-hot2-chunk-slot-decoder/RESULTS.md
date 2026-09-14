# Chunk/slot quotient-remainder decoder

Decision: **reject**.

This non-expanded design reuses the 13 fan-in-16 chunk maxima, then maps the
chosen chunk through sixteen slot carriers. It reduces 394 flat decoder leaves
to 29 and keeps selected widths below 68 px. Typed chunk selection and explicit
anchor rebinding were added after diagnostics exposed two wiring hazards.

The corrected one-round screen still fails the two initial-route checks while
the root bucket and later exact final winner remain correct. It is already
1.265x slower by mean and 1.363x by median than fan-in-16. Dynamic `if(style())`
branches expose enough upstream anchor work that reducing boxes does not reduce
latency.

Raw corrected results are in `ab-fixed-vs-hierarchical-max16.json`; earlier
diagnostic runs are retained beside it.
