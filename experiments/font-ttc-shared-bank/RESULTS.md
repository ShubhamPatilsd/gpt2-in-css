# Shared TTC metric bank

A TrueType Collection can physically share the expensive HVAR/VarRegionList
tables. The 64-face collection is 257,660 bytes versus 4,893,184 bytes for 64
standalone copies: 5.27% of the duplicated size.

However, Chrome loaded the first face for all 64 `@font-face` sources even when
their URLs used the standardized PostScript-name fragments
`bank.ttc#BankRow000` through `bank.ttc#BankRow063`. Consequently every pair
returned face zero's values. The 128-output RMSE was 68.78.

The collection is therefore a real file-size deduplication mechanism but not a
working Chrome row selector. It does not scale as a web runtime unless Chrome
honors per-source collection fragments.

The runtime page contains no JavaScript.
