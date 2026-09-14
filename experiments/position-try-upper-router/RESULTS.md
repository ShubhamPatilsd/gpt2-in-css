# Native position-try upper router

## Result

Reject `position-try-order: most-width` as a 197-way score argmax.

Chrome 153 parses all 197 fallbacks and supports the required anchor and
position-try syntax. The ten saved certified fixtures and their first-winner
masking mutations happened to pass, and isolated mutation was 2.05x faster
than the existing two-pass max/match/max router (1.090 ms versus 2.233 ms).

The decisive coverage fixture places a unique maximum at fallback index 9.
Chrome selected index 4 with width 104 instead. In this topology the browser
effectively considers only the early fitting alternatives; `most-width` ranks
fallback placement space, not an arbitrary candidate anchor's encoded score.
Therefore passing fixtures whose winner lies near the front do not establish
general argmax correctness.

This is a semantic rejection, despite the attractive isolated timing. Raw
evidence is in `browser-results.json`.

## Reproduce

```sh
PYTHONPATH=tools uv run --with numpy python \
  tools/build_position_try_upper_router_probe.py
node tools/test_position_try_upper_router_probe.mjs
```
