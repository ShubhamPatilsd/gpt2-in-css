# Rejected: fuse block 1 LN1 into QKV

This variant removes the raster boundary between block 1 LN1 and its centered
QKV projection. The arithmetic is placed in one SVG filter dependency graph.

Rejected result: Chromium did not complete one render after more than three
minutes. The staged version completes in about 1.5 seconds. The intermediate
raster boundary is therefore enabling Chromium to materialize and schedule the
768-value vector; it is not removable overhead in the current design.
