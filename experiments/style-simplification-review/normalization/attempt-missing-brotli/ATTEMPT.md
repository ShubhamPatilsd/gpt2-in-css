# Environment failure before candidate calculation

The first isolated invocation used `/usr/bin/python3` (Python 3.9). It generated
and saved the declared reference inputs, then stopped while opening the first
existing WOFF2 font: fontTools required the missing Brotli Python extension.
It did not calculate candidate errors or produce a result report. The inputs
and exact analyzer snapshot are retained here.

The corrected invocation uses an isolated `uv run --python 3.11 --with numpy
--with fonttools --with brotli --with pillow` environment. The protocol, cases,
formulas, and rejection thresholds are unchanged. This is an environment repair,
not an exclusion of a numerical failure.
