"""R4P: write reference_ids_32_<id>.json (R4C shape minus savedCodex32) for the given prompt ids from screen_results.json."""
import json, sys
rows = {r["id"]: r for r in json.load(open("screen_results.json"))}
for arg in sys.argv[1:]:
    r = rows[int(arg)]
    assert r["teacherForcedEqualsFree"], r["id"]
    json.dump({"promptToken": r["id"], "promptText": r["text"],
               "teacherForcedReference": r["teacherForced"], "freeRunningReference": r["quantized"],
               "floatReference": r["float"], "quantizedEqualsFloat": r["quantizedEqualsFloat"],
               "agree": r["teacherForced"] == r["quantized"]},
              open(f"reference_ids_32_{r['id']}.json", "w"), indent=1)
    print("wrote", f"reference_ids_32_{r['id']}.json", r["text"], r["quantized"])
