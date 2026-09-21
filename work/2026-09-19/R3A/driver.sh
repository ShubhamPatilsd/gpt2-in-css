#!/bin/zsh
# R3A driver: wait for B3/DONE (poll 60 s, up to 3 h), then one heavy traced session of bundles/R2F.
W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19
logline() { echo "- $(date '+%Y-%m-%d %H:%M:%S') [driver] $*" >> $W/R3A.log.md; echo "$*"; }
CATS=${R3A_CATS:-blink,blink.style,blink.animations,blink.user_timing,disabled-by-default-blink.debug,disabled-by-default-blink.debug.layout,devtools.timeline,disabled-by-default-devtools.timeline,cc,v8.gc}
logline "waiting for $W/B3/DONE (poll 60 s, up to 3 h); cats=$CATS"
for i in {1..180}; do [[ -e $W/B3/DONE ]] && break; (( i % 10 == 0 )) && logline "still waiting for B3/DONE ($i min); B3 last: $(tail -1 $W/B3.log.md | cut -c1-160)"; sleep 60; done
if [[ ! -e $W/B3/DONE ]]; then logline "B3/DONE not seen after 3 h — proceeding anyway per plan cap"; fi
logline "B3/DONE present: $(ls -la $W/B3/DONE 2>/dev/null | tr -s ' ')"
$W/R3A/run_heavy.sh R2F ${R3A_LABEL:-R2F-heavy} $CATS ${R3A_FROM:-2} 900000
echo "driver-exit rc=$?" >> $W/R3A/driver.status
logline "driver done rc=$?"
