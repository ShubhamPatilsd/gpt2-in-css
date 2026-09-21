"""R4M: resolve the two textual conflicts of R4D's diff on top of R4S's (both touch the same neighbourhoods).
usage: python3 apply_conflicts.py <tools-dir>
1. browser_gpt2_reused_adapter.py: R4D's `import r4d_flags as r4d` goes after R4S's `import r4s_small_hops as r4s` (adjacent import lines).
2. browser_gpt2_font_vector_cache.py: R4D's hide-unfilled / gate-scores block (the hunk anchored on the `html{timeline-scope}` line that R4S
   wrapped in `if not r4s.SMALL_HOPS:`) is inserted before R4S's guarded line. Merge decision: R4D_GATE_SCORES (default OFF) is additionally
   disabled under R4S_SMALL_HOPS — its selector `.fvs-score-source .fvs-score-H-S` targets the timeline scroller R4S removes, and
   `display:none` on an R4S anchor row would invalidate the chain's `anchor-size()`; the score masking it duplicated (`--fv-S`) is unchanged."""
import sys, pathlib
tools = pathlib.Path(sys.argv[1])

def edit(path, old, new, count=1):
    p = tools / path; s = p.read_text()
    assert s.count(old) == count, (path, old[:60], s.count(old))
    p.write_text(s.replace(old, new))

# 1. adapter import
edit("browser_gpt2_reused_adapter.py",
     "import r4s_small_hops as r4s\n",
     "import r4s_small_hops as r4s\nimport r4d_flags as r4d\n")

# 2. font_vector_cache: R4D block before R4S's guarded timeline-scope line
old = '''    body = '<div class="fvs-query">' + body + "</div>"
    if not r4s.SMALL_HOPS:  # R4S: no score timelines
        css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
'''
new = '''    body = '<div class="fvs-query">' + body + "</div>"
    # R4M merge: R4D_GATE_SCORES is off under R4S (no score scroller; display:none on an
    # anchor row would invalidate the chain's anchor-size()); --fv-S masking is unchanged.
    gate_scores = r4d.GATE_SCORES and sequential and not r4s.SMALL_HOPS
    if hide_unfilled or gate_scores:
        # R4D: per-slot filled flag on the fvscache container (same expression
        # as --fv-S on the score reader, which is inherits:false and therefore
        # invisible to the glyph leaves).
        css += hybrid.regs([f"--fvq-{slot}" for slot in range(capacity)]).replace(
            "inherits:true", "inherits:false"
        )
        css += ".fvs-query{" + ";".join(
            f"--fvq-{slot}:clamp(0,sign(var({write_epoch}) - {slot + 1}) + 1,1)"
            for slot in range(capacity)
        ) + "}"
    if hide_unfilled:
        for slot in range(capacity):
            selectors = ",".join(f".fvs-v-{head}-{slot}" for head in range(HEADS))
            css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
    if gate_scores:
        # R4D (opt-in): unfilled slots' score carriers have no box, so their 12
        # view-timelines are inactive; --fs/--fe of those slots are masked by
        # --fv-S anyway (both branches give the same masked values).
        for slot in range(capacity):
            selectors = ",".join(f".fvs-score-source .fvs-score-{head}-{slot}" for head in range(HEADS))
            css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
    if not r4s.SMALL_HOPS:  # R4S: no score timelines
        css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
'''
edit("browser_gpt2_font_vector_cache.py", old, new)
# the manifest value R4D emits must reflect the merge decision
edit("browser_gpt2_font_vector_cache.py",
     '            "r4dGateScores": r4d.GATE_SCORES and sequential,\n',
     '            "r4dGateScores": gate_scores,\n')
print("conflicts resolved")
