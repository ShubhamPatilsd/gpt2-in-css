# Better small language-model checkpoints

`sshleifer/tiny-gpt2` is useful as a systems test, but its hidden width is only
two. Its repeated `stairs` and `factors` completions are a property of that
checkpoint, not CSS inference.

The best next target found is
[`calum/tinystories-gpt2-3M`](https://huggingface.co/calum/tinystories-gpt2-3M).
It is a genuine GPT-2 architecture trained on TinyStories, with eight layers,
16 attention heads, width 64, and a 50,257-token vocabulary. The downloadable
PyTorch checkpoint is 14.8 MB. Its model card reports coherent story generation
for its size, especially for simple in-domain prompts.

The cost is CSS expansion. For one context position, the checkpoint requires
approximately 3.61 million multiply-accumulate terms:

- 393,216 across the eight transformer blocks;
- 3,216,448 in the full language head.

At the source densities measured in this repository, that projects to roughly
100–190 MB of CSS for one exact token. Four growing-context steps would be
roughly 400–800 MB before browser working-memory overhead.

Other candidates:

- [`roneneldan/TinyStories-1M`](https://huggingface.co/roneneldan/TinyStories-1M)
  is the research authors' small coherent checkpoint, but it uses GPT-Neo rather
  than GPT-2. Its configuration is also width 64 and eight layers.
- [`distilbert/distilgpt2`](https://huggingface.co/distilbert/distilgpt2) is a
  better general-English model, but it remains width 768 with six layers and 82M
  parameters, so its exact CSS circuit would still be multi-gigabyte.

The 3M TinyStories full output vocabulary is browser-loadable without an
approximation by using exact lazy clustered search. Sharing token dot-product
functions reduced the output head from 291.9 MB to 213.0 MB. A complete static
transformer-plus-head update takes 670–702 ms median, while the CSS-only
KV-cached recurrent implementation produced four correct tokens in 42.69
seconds. Its roughly 234 MB linked graph used about 1.4 GB of renderer memory.
This is a viable research path, not yet a lightweight page. See
[`tinystories/RESULTS.md`](tinystories/RESULTS.md).

The exact 16-token convex-hull reduction used for the current width-two test
checkpoint should not be assumed for this width-64 model. Convex hulls become
far less selective in higher dimensions.
