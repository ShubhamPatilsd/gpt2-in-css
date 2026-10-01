#!/bin/zsh
# R6X v2 build session (run under CHROME.lock so no other agent's Chrome runs during the builds): rebuild demo-c32 and demo-8 one at a time into
# R6X/twin-<b>-v2, prove with compare_rules.py that each differs from the shipped bundle ONLY by `html .visible-output{bottom:96px;overflow:auto}`
# (index.html byte-identical), then swap it in (BUILD.md / README.txt / READY carried over), static check + pack dry-run, delete the old build.
set -u; W=/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19; cd $W; R=$W/R6X
for b in demo-c32 demo-8; do
  if [[ $b == demo-c32 ]]; then cap=32; extra=(VALUE_LAYOUT=widths R4S_SMALL_HOPS=0); else cap=8; extra=(); fi
  echo "### $(date '+%T') build $b v2"; rm -rf $R/twin-$b-v2
  env ${extra[@]} $R/compile.sh $R/twin-$b-v2 $cap 12 > $R/logs/compile-$b-v2.log 2>&1 || { echo "BUILD FAILED"; tail -3 $R/logs/compile-$b-v2.log; exit 1; }
  echo "### $(date '+%T') compare_rules twin-$b-v2 vs bundles/$b"; python3 $R/compare_rules.py $R/twin-$b-v2 bundles/$b | tee $R/logs/compare_rules-$b-v2.log | cut -c1-400
  # every rule only in NEW must be an R6X display rule (layout rule / .pg head segment / its keyframes); nothing only in REF; HTML identical
  # v5: HTML may differ ONLY by the embedding receipt marker; rules only in NEW/REF must be typed-prompt wiring or R6X display rules
  # (selectors .tk-*, .visible-output, .feedback-reader,.visible-output, html .visible-output / .tk-aside, .pg*, .controls>label, keyframes pg-head-*,
  # @property --prompt-live, body:has(...) chains ending in .tk-high-k / .tk-editor / .controls>label); the model core rules must be identical.
  python3 $R/check_v5_identity.py $R/twin-$b-v2 bundles/$b | tee $R/logs/identity-$b-v5.log | cut -c1-300
  grep -q '^RESULT: PASS' $R/logs/identity-$b-v5.log || { echo "IDENTITY CHECK FAILED for $b — not swapping"; exit 2; }
  for f in BUILD.md README.txt READY; do [[ -f bundles/$b/$f ]] && cp bundles/$b/$f $R/twin-$b-v2/$f; done
  # atomic swap protocol (coordinator, 21:xx): build is never written into the live dir; .next → live, live → .prev (kept)
  rm -rf bundles/$b.next bundles/$b.prev; mv $R/twin-$b-v2 bundles/$b.next && mv bundles/$b bundles/$b.prev && mv bundles/$b.next bundles/$b && echo "### $(date '+%T') swapped $b (new build live; previous kept as bundles/$b.prev)"
  python3 $W/../../tools/launch_browser_gpt2.py --check --directory bundles/$b | tee $R/logs/static-check-$b-v2.log | tr -d '\n' | cut -c1-200; echo
  python3 $W/R6L/pack_bundle.py bundles/$b /tmp/r6x-dry --dry-run | tee $R/logs/pack-dryrun-$b-v2.log | tail -1
  cat >> bundles/$b/BUILD.md <<EOT

## v6 ($(date '+%F %T'), R6X) — headed-Chrome id-readback fix (R7H): \`.feedback-scroller{scrollbar-width:none}\`; plus v5's typed-prompt arming fix
Rebuilt with the same recipe after \`R6X/apply_conflicts.py\` edit 7 (R6X.md §11: in headed Chrome with macOS "Show scroll bars: Always" the classic 15 px scrollbar inside \`.feedback-scroller\` (524288 px scrollport hardcoded in the id decode, 8 px per id) biased every read-back id ≥ 9283 by +1 — found by R7H; headless harness runs cannot see it) and edit 6 (R6X.md §10: the typed prompt could be shown while the model ran the dropdown prompt — the embedding receipt stamped only the epoch, so layer 0 could consume the idle dropdown embedding; plus the 86,400 s latch could freeze pre-armed values). Model core rules identical (\`R6X/check_v5_identity.py\`). Also v4's two sizing rules at the end of runtime.css, \`html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto}\` (the output box is its content, never shorter than 4 lines, never taller than the window allows above the footer; scrolls when longer) and \`html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto}\` (the footer sits right below the output's maximum extent — off-screen in windows shorter than ≈320 px, never overlapping; v2/v3's \`bottom:96px\` clipped the box to ≤ 20 px in such windows). \`R6X/compare_rules.py\` vs the v1 build: index.html byte-identical, rule multiset + order identical except that one rule (\`R6X/logs/compare_rules-$b-v2.log\`). Plus the 13th bar segment for the vocabulary-head phase (`.pg::before/::after`, `@container corestate style(--held:1)` fill over an estimated 2.8 s + opacity pulse, label "vocabulary head: 50,257 rows → next token… (fill ≈ estimate)"; transform/opacity only). The v1 ids results (READY) therefore transfer; re-verification: R6X.md §7.
EOT
done
# 2-layer, capacity-32 smoke twin of demo-c32 (all flags on) for the quick headed display tests (R6P's smoke2 recipe: blocks 2, widths, R4S off)
[[ -d $R/smoke-demo-2L ]] && { echo "smoke twin exists (v3), kept"; touch $R/BUILD-V2-DONE; echo "### $(date '+%T') builds done"; exit 0; }
echo "### $(date '+%T') build R6X/smoke-demo-2L (blocks 2, cap 32)"; rm -rf $R/smoke-demo-2L
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 $R/compile.sh $R/smoke-demo-2L 32 2 > $R/logs/compile-smoke-demo-2L.log 2>&1 && echo "smoke built: $(du -sm $R/smoke-demo-2L | cut -f1) MB" || { echo "SMOKE BUILD FAILED"; tail -3 $R/logs/compile-smoke-demo-2L.log; }
touch $R/BUILD-V2-DONE; echo "### $(date '+%T') builds done"
