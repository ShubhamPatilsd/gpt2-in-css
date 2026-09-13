# Additional font-relative numeric outputs

Chrome recognizes `font-size-adjust: ic-height 1`, but CSS font-relative units
are resolved from the computed font metrics rather than the adjusted used glyph
size. With VVAR water-height deltas of -100, -50, 0, 50, and 100, the decoded
`1ch` value stayed zero in every case.

Therefore `font-size-adjust: ic-height` can affect rendered glyph geometry but
cannot expose VVAR as a reusable CSS number. It adds no transport channel.

The runtime page contains no JavaScript.
