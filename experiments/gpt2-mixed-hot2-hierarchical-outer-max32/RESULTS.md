# Hierarchical outer maximum, fan-in 32

Decision: **reject**. The seven chunk nodes pass 6/6 exact checks but are
1.060x slower by mean and 1.177x by median than fan-in 16. Raw results are in
`ab-vs-max16.json`.
