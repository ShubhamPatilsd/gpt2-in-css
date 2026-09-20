# R2I — recovery of deleted rowbase fonts (experiments/gpt2-flat-12block-chain/layer01..10)

Date: 2026-09-20. Scratch: `work/2026-09-19/R2I/`. Log: `work/2026-09-19/R2I.log.md`. layer11 untouched.

## Result
- **360 files restored** (36 per layer x 10): `b{N}-attn-composed-rowbase-s{0..2}`, `b{N}-fc-rowbase-s{0..2}`, `b{N}-mlp-proj-rowbase-s{0..11}`, `.ttf` + `.woff2`. Every layer dir is back to 54 files; name sets equal layer11's modulo the `bNN-` prefix.
- **Determinism proven on the oracle**: regenerating layer11 into scratch gave 36/36 byte-identical files (`cmp`) with fontTools 4.65.0 AND with fontTools 4.63.0 (the version installed when the originals were built on Sep 15; 4.65.0 was installed Sep 17). The two versions' outputs are identical for all 396 files (11 layers). Installed files come from the 4.63.0 build (`R2I/out463`).
- **STOP removed**: `work/2026-09-19/bench/STOP` deleted; the bench queue may resume.

## How the fonts are produced (Step 1)
`tools/build_flat_twelve_block_chain.py` -> subprocess `tools/build_view_timeline_two_block_probe.py` (env `TWO_BLOCK_TARGET_LAYER=N`, `TWO_BLOCK_REBUILD_FONTS=1`, `GPT2_BLOCK_CSS_OUT=layerNN`) -> `build_font_group(name, codes, row_specific_bases=True)` in `tools/build_gpt2_block_css.py` -> `build_direct_font_backend` in `tools/build_matrix_backend_prototypes.py` (fvar/HVAR/STAT/gvar built directly; woff2 via fontTools+brotli).
- Inputs: `data/gpt2/model.safetensors` block `h.N`; attn-composed = `c_proj.W^T @ V^T`, fc = `c_fc.W^T`, mlp-proj = `c_proj(mlp).W^T`; symmetric per-row q9 (`QUANT_BITS=9`, `quantize_float_rows`); shards of 256 input columns (3 for 768-wide, 12 for 3072-wide). Fonts depend only on weights, never on the input vector.
- Timestamps pinned: `setupHead(created=modified=2082844800)`, `recalcTimestamp=False`. No random seeds. Fonts are then renamed `b1-*` -> `b{N}-*`.
- Emitters embed `?v=sha256(woff2)[:12]` in `layerNN/layer.css`; bundles' `runtime.css` copy these digests verbatim. So yes, bytes had to match the digests.
- Env used: `uv run --with fonttools==4.63.0 --with numpy --with pillow --with brotli==1.2.0 python` (numpy 2.5.3, python 3.13.2). ~36 s per layer.

## Verification (Steps 2-3)
Per layer 01..10 (`R2I/verify_layers.py`, results in `R2I/verify_inplace.txt`):
- 36 files present, name set == layer11's.
- 18/18 woff2 digests match `layerNN/layer.css` (`?v=`) — see caveat below for 5 of them.
- All witness values (codepoint/advance/upem) in every bundle's `font-witnesses.json` match the restored files (753 entries checked); original `mtime_ns` restored for the 300 files that have a witness record so the witness cache keys are unchanged.
- Sum of the 18 woff2 sizes == `font_bytes` in `layerNN/view-timeline-two-block-full-exact-reference.json` for every layer.
- F2 `global-projection-assets` filenames embed `sha256(source rowbase woff2)[:16]`: 132/132 match (covers all 120 restored mlp-proj woff2 + layer11).

### Caveat found: 5 digests in layer.css/runtime.css are pre-existing mangled strings (NOT a regeneration diff)
`rewrite_layer_assets()` does `css.replace("b1", f"b{layer}")`, which also rewrites the substring `b1` inside hex digests. Real digest -> what layer.css and all bundle runtime.css contain:
- layer04 `b4-mlp-proj-rowbase-s10.woff2`: `8ba244cb147d` -> `8ba244cb447d`
- layer06 `b6-mlp-proj-rowbase-s10.woff2`: `51188cdb1fb3` -> `51188cdb6fb3`
- layer07 `b7-attn-composed-rowbase-s0.woff2`: `53420a2c04b1` -> `53420a2c04b7`
- layer10 `b10-fc-rowbase-s2.woff2`: `4d647b12afbd` -> `4d647b102afbd` (13 chars)
- layer10 `b10-mlp-proj-rowbase-s8.woff2`: `518b145907b7` -> `518b1045907b7` (13 chars)
This was already the case before the deletion (the CSS predates it); the query string is ignored by the static server/allowlist, so it is cosmetic. No bundle rebuild is needed. A future fix would be to restrict the replace to `b1-`/`b1p`/... tokens in `tools/build_flat_twelve_block_chain.py` (not changed here — read-only).

## Static checks (Step 3b) — all PASS via `tools/launch_browser_gpt2.py --directory <bundle> --check`
baseline 263 files / 280,706,452 B (== BUILD.md); combined 285; combined2 285; combined3 285; F2 263; F3a 263; F5 263; R2C 285; R2D 285; R2F 285; smoke-R2F-2L-ref 75. (Pre-restore: baseline failed on `layer10/b10-mlp-proj-rowbase-s11.woff2`.)

## Other missing assets (Step 4)
`R2I/scan_refs.py` resolved every `url(...)`/`href`/`src` in each bundle's `runtime.css` + `index.html`. Before: 753 missing refs, all of them rowbase fonts in layer01..10 (`R2I/scan_refs_before.txt`). After: 0 missing in all 11 bundles (`R2I/scan_refs_after.txt`). Nothing else was missing.

## Not found elsewhere
Fonts are not git-tracked; no copies in `~/.Trash`, no Time Machine destination; only OS-update APFS snapshots exist.

## Scratch artefacts
`R2I/regen_layer.py`, `R2I/regen_shard.py`, `R2I/verify_layers.py`, `R2I/install_layers.py`, `R2I/scan_refs.py`, `R2I/out/` (4.65.0 build, 11 layers), `R2I/out463/` (4.63.0 build, installed), `R2I/seed/` (PYTHONHASHSEED sweep), logs `R2I/out/*.log`.
