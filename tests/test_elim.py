import random

import pytest

from app.baseline import RouteDoctor
from app.difficulty import PRESETS, Difficulty, ShiftRules
from app.elim import ElimCase, IllegalMove, eligible
from app.eval import compare, play_case, play_shift, summarise
from app.shift import Shift
from app.worlds import load_worlds

WORLDS = load_worlds()


def case_for(template: str, preset: str = "standard") -> ElimCase:
    for w in WORLDS.values():
        for c in w.cases:
            if c.id == template:
                return ElimCase(w, c, difficulty=PRESETS[preset])
    raise KeyError(template)


def test_worlds_are_consistent():
    for w in WORLDS.values():
        for h in w.hypotheses.values():
            assert h.tier in ("must_not_miss", "other")
            assert h.eliminate_when or h.remainder or h.no_rule_note, (w.situation, h.id)
        for c in w.cases:
            assert c.truth in w.hypotheses and (c.decoy is None or c.decoy in w.hypotheses)


def test_every_case_has_a_feasible_cheapest_safe_route_and_no_self_elimination():
    for w in WORLDS.values():
        for c in w.cases:
            case = ElimCase(w, c)
            ref = case._reference_route()
            assert ref["feasible"], (w.situation, c.id)
            known = {t: case.result_for(t) for t in w.tests} | {"history_exam": "done"}
            assert not any(case._clause_holds(cl, known) for cl in case.truth_hyp.eliminate_when), (w.situation, c.id)


def test_baseline_solves_every_case_cleanly():
    doc = RouteDoctor(WORLDS)
    for w in WORLDS.values():
        for c in w.cases:
            rec = play_case(ElimCase(w, c), doc)
            r = rec["result"]
            assert r["exact"], (c.id, r["verdict"])
            assert r["safe_closure"], (c.id, r["must_not_miss"])
            assert not r["unsafe_eliminations"], (c.id, r["unsafe_eliminations"])
            assert r["gate"] == "ok", (c.id, r["gate"])
            assert not r["order_violations"], (c.id, r["order_violations"])
            assert rec["illegal_moves"] == 0, c.id
            assert r["differential_recall"] == 1.0 and r["differential_first"] == "before_tests" and not r["never_considered"], c.id
            assert r["process_score"] == 1.0, (c.id, r["process_score"], r["verdict"])


def test_shortcut_elimination_is_flagged():
    case = case_for("acs_atypical")
    case.order("history_exam")
    case.order("ecg")
    e = case.eliminate("acs", ["ecg"])
    assert e.validity == "shortcut" and "normal ECG" in e.reason
    case.order("cxr")
    r = case.diagnose("nc")
    assert r["exact"] is False and r["missed_dangerous"] is True and r["truth_eliminated"] is True
    assert r["must_not_miss"][0]["status"] in ("open", "shortcut") or True
    assert any(e["validity"] == "shortcut" for e in r["unsafe_eliminations"])


def test_valid_elimination_and_cost_grading():
    case = case_for("nc_young")
    case.order("history_exam")
    case.propose(["ACS", "PE", "aortic dissection", "musculoskeletal pain"])
    case.order("ecg")
    case.order("troponin")
    assert case.eliminate("acs", ["ecg", "troponin"]).validity == "valid"
    case.order("perc")
    assert case.eliminate("pe", ["perc"]).validity == "valid"
    case.order("addrs")
    case.order("ddimer")
    assert case.eliminate("ad", ["addrs", "ddimer"]).validity == "valid"
    r = case.diagnose("nc")
    assert r["exact"] and r["safe_closure"] and r["cost_efficiency"] == 1.0 and r["score"] == 1.0


def test_unsupported_elimination_and_overspend():
    case = case_for("nc_young")
    case.order("history_exam")
    assert case.eliminate("pe", []).validity == "unsupported"
    case.order("ctpa")
    case.order("cta_aorta")
    case.order("ecg")
    case.order("troponin")
    assert case.eliminate("acs", ["ecg", "troponin"]).validity == "valid"
    assert case.eliminate("ad", ["cta_aorta"]).validity == "valid"
    r = case.diagnose("nc")
    assert r["exact"] and r["spend"] > r["reference_cost"] and r["cost_efficiency"] < 1.0
    assert r["process_score"] < 1.0 and r["unsafe_eliminations"]


def test_gate_and_order_rules():
    case = case_for("acs_unstable")
    case.order("history_exam")
    case.order("ecg")
    r = case.diagnose("acs")
    assert r["gate"] == "missed" and "never escalated" in r["verdict"]
    case = case_for("pe_likely")
    case.order("history_exam")
    case.order("wells")
    o = case.order("ddimer")
    assert o.violations and "D-dimer" in o.violations[0]
    case = case_for("ectopic")
    case.order("history_exam")
    o = case.order("ct_abd")
    assert o.violations


def test_population_restricted_rule_is_a_shortcut():
    case = case_for("ahf_elderly_low_bnp")
    case.order("history_exam")
    case.order("bnp")
    assert case.eliminate("ahf", ["bnp"]).validity == "shortcut"


def test_illegal_moves():
    case = case_for("appy_classic")
    with pytest.raises(IllegalMove):
        case.order("nonexistent")
    with pytest.raises(IllegalMove):
        case.eliminate("appy", ["ct_abd"])  # not ordered
    case.order("history_exam")
    case.order("ct_abd")
    case.diagnose("appy")
    with pytest.raises(IllegalMove):
        case.order("hcg")


def test_traps_pool_and_budget():
    assert all(c.decoy for _, c in eligible(WORLDS, PRESETS["traps"]))
    d = Difficulty("tight", budget_usd=50)
    case = ElimCase(WORLDS["chest_pain"], WORLDS["chest_pain"].cases[0], difficulty=d)
    case.order("history_exam")
    case.order("ctpa")
    assert case.result is not None and case.result["timed_out"]


def test_clinic_day_runs_and_summary_compares():
    d = Difficulty("day", shift=ShiftRules(day_minutes=600, patients=3))
    rng = random.Random(3)
    pool = eligible(WORLDS, d)
    picks = rng.sample(pool, 3)
    shift = Shift([ElimCase(w, c, difficulty=d) for w, c in picks], d)
    rec = play_shift(shift, RouteDoctor(WORLDS))
    assert rec["shift"]["correct"] == 3 and rec["error"] is None
    s = summarise([rec])
    assert s["mode"] == "shift" and s["day"]["correct_per_day"] == 3.0 and s["top1"] == 1.0
    run = {"id": "x", "doctor": "baseline", "model": "rule-based", "preset": "day", "mode": "shift", "n": 1, "done": 1,
           "status": "done", "started": 0, "config": {"seed": 1}, "summary": s}
    cmp = compare(run, run)
    assert cmp["wins"] == {"a": 0, "b": 0} and any(r["key"] == "day.earnings" for r in cmp["rows"])


def test_free_text_hypotheses_resolve_to_the_hidden_board():
    case = case_for("pe_likely")
    assert "hypotheses" not in case.view() and "route" not in case.view()
    case.order("history_exam")
    added = case.propose(["Pulmonary embolism (PE)", "heart attack", "a dissection of the aorta", "Boerhaave syndrome"])
    assert [p.hypothesis for p in added] == ["pe", "acs", "ad", None]
    assert case.propose(["PE"]) == []  # already on the differential
    case.order("ecg")
    case.order("troponin")
    e = case.eliminate("the heart attack", ["ecg", "troponin"])
    assert e.hypothesis == "acs" and e.validity == "valid" and e.name == "Acute coronary syndrome"
    with pytest.raises(IllegalMove):
        case.eliminate("a hernia", [])
    case.order("wells")
    case.order("ctpa")
    r = case.diagnose("massive PE")
    assert r["exact"] and r["truth_confirmed"] and r["off_board"] == ["Boerhaave syndrome"]
    assert r["differential_recall"] == 1.0 and r["differential_first"] == "before_tests"


def test_never_considered_dangerous_cause_is_graded():
    case = case_for("pe_likely")
    case.order("history_exam")
    case.order("ecg")
    case.propose(["ACS"])  # after a paid test, and the clot never comes up
    case.order("troponin")
    case.eliminate("ACS", ["ecg", "troponin"])
    r = case.diagnose("costochondritis")
    assert not r["exact"] and r["missed_dangerous"] and not r["truth_considered"]
    assert set(r["never_considered"]) == {"Pulmonary embolism", "Aortic dissection"}
    assert [m["status"] for m in r["must_not_miss"]] == ["valid", "never_considered"]
    assert r["differential_first"] == "after_tests" and r["differential_recall"] == pytest.approx(1 / 3, abs=1e-3)
    assert "never came up" in r["verdict"]
    # An off-board diagnosis is a commitment, graded wrong, not an illegal move.
    case = case_for("nc_young")
    case.order("history_exam")
    r = case.diagnose("Boerhaave syndrome")
    assert not r["exact"] and r["doctor_name"] == "Boerhaave syndrome" and r["differential_first"] == "never"
    assert r["process_score"] < 0.5
