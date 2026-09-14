# Fully packed direct argmax

Decision: **reject**.

This negative control tries to encode score bucket, group identity, and local
token identity in one expanded width, removing 396 first-stage decoder nodes.
The idea is not generally exact: `--score-group-*` is already rounded to a
4 px bucket, so its modulo-4 payload is zero and cannot recover the local
token. Later exact search stages happen to repair the tested final outputs, but
that does not validate the first-stage local decode.

The narrow end-to-end screen passes 6/6 final checks but is also much slower
than pruned direct-max: mean is 2,064.6 versus 1,789.7 ms (**1.154x**) and
median is 2,429.8 versus 1,805.4 ms (**1.346x**). Per-operand packing arithmetic
and roughly 10-million-pixel widths cost more than the removed nodes save.

Raw results are in `ab-vs-direct-max-pruned.json`.
