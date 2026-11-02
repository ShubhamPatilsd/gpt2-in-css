#!/bin/zsh
# R6X: pack a demo bundle for recipients = R6L/pack_bundle.py (launcher + model/{index.html,runtime.css,fonts/285} [+ .br/.gz]) + the bundle's
# recipient README.txt (pack_bundle.py writes a generic one). usage: pack_demo.sh <bundle-name> <out-dir> [--br]   e.g. pack_demo.sh demo-c32 /tmp/gpt2-css-demo --br
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
b=${1:?bundle}; out=${2:?out}; shift 2
python3 "$REPO_ROOT/pack/pack_bundle.py" "$REPO_ROOT/bundles/$b" $out "$@"
[[ -f $REPO_ROOT/bundles/$b/README.txt ]] && cp $REPO_ROOT/bundles/$b/README.txt $out/README.txt
echo "packed $b -> $out ($(du -sm $out | cut -f1) MB); recipient: cd $out && python3 tools/launch_browser_gpt2.py --directory model"
