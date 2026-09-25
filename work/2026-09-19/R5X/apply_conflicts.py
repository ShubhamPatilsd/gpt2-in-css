"""R5X: resolve the one textual conflict of R5H's diff on top of R5E's (browser_gpt2_reused_adapter.py, the inline pass-reader count
assertion — both owners edit the same two lines).
  R5E: `diag = 1 if r5e.KEEP_DIAG else 0` and `tagged != (6 if r4s.SMALL_HOPS else 7) - 1 + diag or tagged_position != 1 + diag`
       (the reused-probe / block-11-probe epoch twins are gone unless R5E_KEEP_DIAG=1);
  R5H: `tagged != (6 if r5h.no_score_hop() else 7) or tagged_position != 2`
       (the score stamp marker is gone under R4S OR R5H, r5h.no_score_hop()).
Union (both effects on the same body): `tagged != (6 if r5h.no_score_hop() else 7) - 1 + diag or tagged_position != 1 + diag`.
usage: python3 apply_conflicts.py <tools-dir>"""
import sys, pathlib
tools = pathlib.Path(sys.argv[1])

def edit(path, old, new, count=1):
    p = tools / path; s = p.read_text()
    assert s.count(old) == count, (path, old[:60], s.count(old))
    p.write_text(s.replace(old, new))

edit("browser_gpt2_reused_adapter.py",
     "        # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists\n"
     "        diag = 1 if r5e.KEEP_DIAG else 0  # R5E: the reused-probe / block-11-probe epoch twins\n"
     "        if tagged != (6 if r4s.SMALL_HOPS else 7) - 1 + diag or tagged_position != 1 + diag:\n",
     "        # R4S / R5H: the score stamp marker (one inline var(--epoch) reader) no longer exists\n"
     "        diag = 1 if r5e.KEEP_DIAG else 0  # R5E: the reused-probe / block-11-probe epoch twins\n"
     "        if tagged != (6 if r5h.no_score_hop() else 7) - 1 + diag or tagged_position != 1 + diag:  # R5X: R5E x R5H union\n")
print("conflicts resolved")
