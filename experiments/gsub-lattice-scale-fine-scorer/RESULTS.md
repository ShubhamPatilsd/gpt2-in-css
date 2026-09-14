# GSUB lattice-scale fine-scorer probe

Decision: **reject lattice scaling: bounded probe failed winner, oracle-winner, or advance gate**.

This was bounded to eight groups and ten fixtures; no full bank was built. 20,480 candidate buckets were compared against a newly generated 0.03125-scale exact CSS-dispatch baseline. The maximum absolute delta was 2, with 4,673 differing buckets. GSUB/exact winner agreement was 100.00%; GSUB/model-oracle and exact/model-oracle winner agreement were 97.50% and 97.50%.

Dynamic cv01 settings were valid. 491,520 individual glyph advances were measured; the maximum was 13693.078px. The source-font theoretical maximum is 29,296px and the existing full-bank h3 complement projects to 10,536px at this scale, below the 32,768px ceiling.

Median isolated group switching was 5.700ms for GSUB and 7.500ms for matched CSS dispatch (24.0% speedup; 25% required).

Limitations: Only the existing eight spread groups and ten fixtures are exercised. No full-vocabulary fonts were built or loaded; the full h3 complement value is projected from its existing metric. Timing is local headless Chrome wall-clock layout timing and is not portable across machines or Chrome builds.
