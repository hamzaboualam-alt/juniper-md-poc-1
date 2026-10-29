import json, csv, os, sys, shutil
from sources import SOURCES, LAST_VERIFIED
from situations_a import CHEST_PAIN, HEADACHE, SYNCOPE
from situations_b import DYSPNEA, LOWER_ABDO, UGIB, LEG
from situations_c import DIZZY, FOCAL, LBP, FLANK, FEVER
from evidence import EXTRA_EVIDENCE

SITUATIONS = [CHEST_PAIN, DYSPNEA, LOWER_ABDO, HEADACHE, FEVER, SYNCOPE, UGIB, LEG, DIZZY, FOCAL, LBP, FLANK]
EFFECT_TYPES = {"rule": "Can eliminate", "conf": "Can confirm", "steer": "Shifts suspicion", "blind": "Cannot decide it"}
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"

errors, unsourced = [], []
_titles = {(s["id"], st["title"]) for s in SITUATIONS for st in s["steps"]}
for key in EXTRA_EVIDENCE:
    if key not in _titles: print("evidence key not found:", key); sys.exit(1)
for s in SITUATIONS:
    for st in s["steps"]:
        st["evidence"] = list(st.get("evidence", [])) + EXTRA_EVIDENCE.get((s["id"], st["title"]), [])
def chk_src(sid, where):
    if sid is None:
        unsourced.append(where)
    elif sid not in SOURCES:
        errors.append(f"unknown source '{sid}' at {where}")

used = set()
for s in SITUATIONS:
    sid = s["id"]
    hids = [h["id"] for h in s["hypotheses"]]
    if len(set(hids)) != len(hids): errors.append(f"{sid}: duplicate hypothesis ids")
    for g in s["lead_guidelines"]: chk_src(g, f"{sid}.lead"); used.add(g)
    if s.get("priority_source"): chk_src(s["priority_source"], f"{sid}.priority"); used.add(s["priority_source"])
    for i, x in enumerate(s["layer0"]): chk_src(x["source"], f"{sid}.layer0[{i}]"); used.add(x["source"])
    for i, x in enumerate(s["gate"]): chk_src(x["source"], f"{sid}.gate[{i}]"); used.add(x["source"])
    chk_src(s.get("gate_note_source"), f"{sid}.gate_note"); used.add(s.get("gate_note_source"))
    for h in s["hypotheses"]:
        if h.get("clue_source"): chk_src(h["clue_source"], f"{sid}.{h['id']}.clue"); used.add(h["clue_source"])
        if h["tier"] not in ("must_not_miss", "other"): errors.append(f"{sid}.{h['id']}: bad tier")
        if h["id"] not in s["rules"]: errors.append(f"{sid}: no rules for {h['id']}")
    for i, st in enumerate(s["steps"]):
        st["id"] = f"{sid}.s{i+1}"; st["order"] = i + 1
        if st.get("source"): chk_src(st["source"], f"{st['id']}"); used.add(st["source"])
        for j, ev in enumerate(st.get("evidence", [])): chk_src(ev["source"], f"{st['id']}.evidence[{j}]"); used.add(ev["source"])
        st.setdefault("evidence", [])
        for hid, e in st["effects"].items():
            if hid not in hids: errors.append(f"{st['id']}: effect for unknown hypothesis {hid}")
            if e["type"] not in EFFECT_TYPES: errors.append(f"{st['id']}.{hid}: bad effect type")
            chk_src(e["source"], f"{st['id']}.{hid}"); used.add(e["source"])
    for hid, r in s["rules"].items():
        if hid not in hids: errors.append(f"{sid}: rules for unknown hypothesis {hid}")
        for k in ("eliminate_when", "do_not_rely"):
            for j, x in enumerate(r[k]): chk_src(x["source"], f"{sid}.rules.{hid}.{k}[{j}]"); used.add(x["source"])
        if not r["eliminate_when"] and not r["no_rule_note"]:
            errors.append(f"{sid}.{hid}: no elimination rule and no note explaining why")
    for i, gp in enumerate(s["gaps"]): chk_src(gp["source"], f"{sid}.gaps[{i}]"); used.add(gp["source"])

used.discard(None)
used.add("stern_s2d")  # structural reference for the situation format, cited in README
unused = sorted(set(SOURCES) - used)
if errors:
    print("VALIDATION FAILED"); [print(" -", e) for e in errors]; sys.exit(1)

# ---------- write ----------
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(f"{OUT}/situations"); os.makedirs(f"{OUT}/csv")
dataset = {"name": "Diagnosis-by-elimination routes", "version": "0.2.0", "last_verified": LAST_VERIFIED,
           "effect_types": EFFECT_TYPES, "sources": SOURCES, "situations": SITUATIONS}
json.dump(dataset, open(f"{OUT}/dataset.json", "w"), indent=1, ensure_ascii=False)
for s in SITUATIONS:
    json.dump(s, open(f"{OUT}/situations/{s['id']}.json", "w"), indent=1, ensure_ascii=False)

def wcsv(name, header, rows):
    with open(f"{OUT}/csv/{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

wcsv("sources", ["source_id", "title", "url", "publisher", "year", "kind", "tier", "notes", "last_verified"],
     [[k, v["title"], v["url"], v["publisher"], v["year"], v["kind"], v["tier"], v["notes"], LAST_VERIFIED] for k, v in SOURCES.items()])
wcsv("situations", ["situation_id", "title", "setting", "population", "status", "priority", "priority_source", "lead_guidelines", "gate_note", "gate_note_source"],
     [[s["id"], s["title"], s["setting"], s["population"], s["status"], s["priority"], s.get("priority_source"), ";".join(s["lead_guidelines"]), s["gate_note"], s.get("gate_note_source")] for s in SITUATIONS])
wcsv("layer0_inputs", ["situation_id", "position", "label", "detail", "source_id"],
     [[s["id"], i+1, x["label"], x["detail"], x["source"]] for s in SITUATIONS for i, x in enumerate(s["layer0"])])
wcsv("gate_branches", ["situation_id", "position", "urgent", "label", "detail", "source_id"],
     [[s["id"], i+1, x["urgent"], x["label"], x["detail"], x["source"]] for s in SITUATIONS for i, x in enumerate(s["gate"])])
wcsv("hypotheses", ["situation_id", "hypothesis_id", "name", "short_name", "tier", "clue", "clue_source", "status"],
     [[s["id"], h["id"], h["name"], h["short"], h["tier"], h["clue"], h.get("clue_source"), h["status"]] for s in SITUATIONS for h in s["hypotheses"]])
wcsv("steps", ["situation_id", "step_id", "order", "title", "timing", "description", "source_id"],
     [[s["id"], st["id"], st["order"], st["title"], st["timing"], st["description"], st.get("source")] for s in SITUATIONS for st in s["steps"]])
wcsv("step_evidence", ["situation_id", "step_id", "text", "source_id"],
     [[s["id"], st["id"], ev["text"], ev["source"]] for s in SITUATIONS for st in s["steps"] for ev in st["evidence"]])
wcsv("step_effects", ["situation_id", "step_id", "hypothesis_id", "effect_type", "effect_label", "text", "source_id"],
     [[s["id"], st["id"], hid, e["type"], EFFECT_TYPES[e["type"]], e["text"], e["source"]] for s in SITUATIONS for st in s["steps"] for hid, e in st["effects"].items()])
rows = []
for s in SITUATIONS:
    for hid, r in s["rules"].items():
        for k, kind in (("eliminate_when", "eliminate_when"), ("do_not_rely", "do_not_rely")):
            for x in r[k]: rows.append([s["id"], hid, kind, x["text"], x["source"], x["inferred"], r["validation"]])
        if r["no_rule_note"]: rows.append([s["id"], hid, "no_rule_note", r["no_rule_note"], None, False, r["validation"]])
wcsv("elimination_rules", ["situation_id", "hypothesis_id", "rule_kind", "text", "source_id", "inferred", "validation_note"], rows)
wcsv("gaps", ["situation_id", "title", "text", "source_id"], [[s["id"], g["title"], g["text"], g["source"]] for s in SITUATIONS for g in s["gaps"]])

# ---------- stats ----------
st = {"situations": len(SITUATIONS), "hypotheses": sum(len(s["hypotheses"]) for s in SITUATIONS),
      "steps": sum(len(s["steps"]) for s in SITUATIONS),
      "effects": sum(len(x["effects"]) for s in SITUATIONS for x in s["steps"]),
      "elimination_rules": sum(len(r["eliminate_when"]) for s in SITUATIONS for r in s["rules"].values()),
      "do_not_rely": sum(len(r["do_not_rely"]) for s in SITUATIONS for r in s["rules"].values()),
      "inferred_rules": sum(1 for s in SITUATIONS for r in s["rules"].values() for x in r["eliminate_when"] if x["inferred"]),
      "sources_used": len(used), "sources_unused": unused, "unsourced_items": len(unsourced)}
status = {}
for s in SITUATIONS:
    for h in s["hypotheses"]: status[h["status"]] = status.get(h["status"], 0) + 1
st["hypothesis_status"] = status
json.dump({"stats": st, "unsourced_items": unsourced}, open(f"{OUT}/validation_report.json", "w"), indent=1)
print(json.dumps(st, indent=1))
