# CSS-only GPT-2 tokenizer: implemented path

## Runtime interface

The recurrent model accepts four prompt positions. Each position supplies the
two coordinates of its raw GPT-2 embedding:

```css
--interactive-token-N-0: <number>;
--interactive-token-N-1: <number>;
```

It also consumes `--initial-count`. The tokenizer now produces those values
directly; it does not materialize token IDs or use the old `<select>` mapping.

## Editable input

The visible `style[contenteditable]` is reparsed by the browser while it is
edited:

```css
.prompt-source { --prompt: "Hello world!"; }
```

This remains the only user-input workaround. There is no runtime script.

## Tokenization and embedding pipeline

1. `content: var(--prompt)` renders the same prompt into eight invisible text
   runs: four token positions by two embedding dimensions.
2. Two generated OpenType fonts contain GPT-2's byte vocabulary and complete
   50,000-rule ranked BPE merge table as GSUB substitutions.
3. Position features `p000` through `p003` erase every shaped token except the
   requested position.
4. The remaining glyph's advance encodes one coordinate from
   `transformer.wte.weight`:

   ```text
   advance = round((embedding + 0.1) * 160000) + 1
   ```

   Zero advance means that the requested position does not exist.
5. CSS Anchor Positioning copies each intrinsic text width onto a nested size
   query container.
6. A registered inheriting custom property converts `100cqi` back to a number:

   ```css
   calc((100cqi / 1px * 64 - 1) / 160000 - .1)
   ```

7. The decoded coordinates and inferred prompt length feed the existing
   `recurrent.css` unchanged.

The conservative GSUB batching is exact: only consecutive merge rules whose
input and output glyph sets are disjoint share a lookup, so rules that could
compete or consume one another remain rank ordered.

## Measured prototype

- Complete input vocabulary: 50,257 GPT-2 token embeddings.
- Complete BPE table: 50,000 ranked merges, compressed into 2,782 independent
  lookup batches.
- Font size: about 1.6 MB per embedding coordinate.
- Six browser prompt replacements measured 81–270 ms end to end through the
  automation layer, including editor input, style reparsing, eight shaping
  passes, layout, and computed-style synchronization.
- The fixed-point transport's maximum observed embedding error was
  `3.12e-6`; it caused zero next-token winner changes across 200 sampled
  prompts.
- `Hello world!` produced token embeddings for `15496, 995, 0`.
- `CSS is computing` produced embeddings for `49155, 318, 14492`; the unchanged
  recurrent model generated `stairs stairs`.

## Current boundary

The production proof supports one-line printable ASCII input and uses the first
four BPE tokens, matching the current interactive model's
four-position input boundary. General Unicode needs an additional codepoint to
UTF-8-byte expansion stage in the font; that is separate from BPE correctness
and model integration.

## Rebuild and verify

```sh
uv run --with fonttools --with numpy \
  python tools/build_metric_tokenizer_font.py --full
uv run --with fonttools --with numpy \
  python tools/test_metric_tokenizer_font.py
```
