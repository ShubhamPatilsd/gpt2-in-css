#!/bin/zsh
# usage: prepare_upload.sh <out-dir>   -> <out-dir>/model (upload tree), <out-dir>-zip/gpt2-in-css.zip (GitHub Release)
set -e
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
R=/Users/shubhampatil/Documents/programming/gpt2-css
out=${1:?out-dir}; out=${out%/}
[[ -e $out ]] && { echo "refusing: $out exists"; exit 1; }
$W/R6X/pack_demo.sh demo-c32 $out
M=$out/model
# full pack zip (launcher + README + model) BEFORE nothing private: strip first, then zip
rm -f $M/BUILD.md $M/manifest.json $M/font-witnesses.json
find $out -type f \( -name '*.br' -o -name '*.gz' \) -delete
grep -rl "/Users/" $out 2>/dev/null | while read f; do echo "removing private file $f"; rm -f "$f"; done
if grep -rIl "/Users/" $out 2>/dev/null | grep -q .; then echo "FAIL: /Users/ remains"; exit 1; fi
python3 - $M <<'PY'
import re,sys,os
m=sys.argv[1]; css=open(m+'/runtime.css',encoding='utf-8').read()
urls=set(re.findall(r'url\(\s*["\']?([^"\')]+)',css)); bad=[u for u in urls if u.startswith('data:')==False and not os.path.isfile(m+'/'+u.split('?')[0]) ]
inside=[u for u in urls if not u.startswith('data:') and not u.split('?')[0].startswith('fonts/')]
print(len(urls),'url() refs; missing:',len(bad),'outside fonts/:',len(inside))
sys.exit(1 if bad or inside else 0)
PY
(cd $R && python3 tools/launch_browser_gpt2.py --check --directory $M) || { echo "FAIL: launcher --check"; exit 1; }
mkdir -p $out-zip; (cd $out && zip -qr ../$(basename $out)-zip/gpt2-in-css.zip .)
echo "upload tree: $(find $M -type f | wc -l | tr -d ' ') files, $(find $M -type f -exec stat -f %z {} + | awk '{s+=$1}END{print s}') bytes"
ls -l $out-zip/gpt2-in-css.zip
