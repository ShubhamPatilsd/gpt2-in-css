# Mixed-precision hot-2 upper: static exact-font subset

Browser status: **not run by instruction**.

The 512 in-place hot rows now use a local exact global-int16 subset. Each of the 12 high/residual shard faces contains exactly 512 token codepoints (plus `.notdef`), for 6,144 encoded token glyphs across the bank. Dynamic non-hot fallback rows retain the existing full exact-family path.

## Size

- Full exact WOFF2 bank: 79,431,996 bytes across 12 files.
- Hot-two subset WOFF2 bank: 881,772 bytes across 12 files.
- Subset/full ratio: 1.110%.
- Bytes avoidable on a hot-only route: 78,550,224.

## Static loading topology

Yes: the initial hot-row CSS can avoid eagerly using the full exact fonts. `.mixed-hot-candidate` names only the 12 local `HotScore*` subset families. The full `Score*` families remain attached to the six dynamically gated `.fine-stage` fallbacks, which are `display:none` for groups 0 and 1. CSS font faces are demand-loaded, so this structure permits a hot-only route to fetch only the subset bank. Network behavior remains unmeasured because no browser was launched.

## Validation

- All 12 WOFF2 files decoded successfully.
- Every subset cmap is exactly its plane's 512 codepoints for tokens 0..511.
- Source codepoint-to-glyph names and selected glyph order are preserved (`y000` through `y511`).
- Every face retains the source 128-axis `fvar` contract and all 256 HVAR regions.
- All 513 direct glyph-ID HVAR rows per face (including `.notdef`) and all default advances match the source.
- The source and subset selected glyphs both have empty `gvar` entries; metric variation remains exclusively in HVAR.
- The standard lower-token tie geometry `(255 - local) / 64px` is unchanged.
- Static page routing checks pass: 512 hot rows, 12 local subset faces, six gated dynamic fallbacks, no full-bank URL or full-family use in the hot topology rule.
