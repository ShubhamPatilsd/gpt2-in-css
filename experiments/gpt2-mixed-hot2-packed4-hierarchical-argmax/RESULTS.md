# Packed-four hierarchical argmax

Decision: **reject**.

This probe replaces both 197-leaf first-stage decoder banks with fifty
four-group packed blocks, fifty block matches, and fifty selected-block
carriers. Certified packed widths stay below 202k px, but the initial browser
screen fails every route check (0/6) even though the root bucket and later
six-stage final winner remain correct.

It is also decisively slower: mean is 2,921.2 versus 1,876.0 ms (**1.557x**)
and median is 3,143.6 versus 2,045.4 ms (**1.537x**) against fan-in-16. The
additional packed arithmetic and anchor dependencies dominate the smaller DOM,
so no corrective broad run is justified.

Raw results are in `ab-vs-hierarchical-max16.json`.
