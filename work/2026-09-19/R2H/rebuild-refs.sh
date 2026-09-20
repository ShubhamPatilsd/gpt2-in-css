#!/bin/zsh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2H
export R2D_HEAD_LOCK=0 R2D_OVERFLOW_CLIP=0 R2D_CONTAIN_PAINT=0
./compile-combined3.sh combined3-noR2D > compile-combined3-noR2D.log 2>&1; echo "noR2D rc=$?"
export R2C_HOIST_FVS=0 R2F_LEAN_HANDSHAKE=0
./compile-combined3.sh combined3-alloff > compile-combined3-alloff.log 2>&1; echo "alloff rc=$?"
echo REBUILD-DONE
