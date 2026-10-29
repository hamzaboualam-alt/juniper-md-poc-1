"""A rule-following doctor that needs no model: it knows the world's board, so
it proposes the full differential at once, walks the guideline route in order,
crosses a hypothesis off the moment a rule allows it, and commits when one
hypothesis is left or a confirming result is in. It is the floor any model
should clear, and the proof that every case is solvable.
"""
from __future__ import annotations

from typing import Any

from .elim import ElimCase
from .shift import Shift
from .worlds import World


class RouteDoctor:
    name = "baseline"
    model = "rule-based"
    label = "baseline · guideline route"

    def __init__(self, worlds: dict[str, World]) -> None:
        self.worlds = worlds

    def decide(self, case: ElimCase) -> dict[str, Any]:
        w = case.world
        if not case.history_taken:
            return {"action": "history_exam", "rationale": "Start with the history and examination."}
        if case.template.unstable and case.escalated_at is None:
            return {"action": "escalate", "rationale": "The patient is unstable: emergency pathway first."}
        if not case.proposals:
            return {"action": "propose", "hypotheses": [h.name for h in w.hypotheses.values()],
                    "rationale": "The full differential for this presentation, dangerous causes first."}
        known = case.known
        open_hyps = [h for h in w.hypotheses.values() if case.status_of(h.id) == "open"]
        # Cross off whatever a rule now allows.
        for h in open_hyps:
            if h.remainder:
                continue
            for c in h.eliminate_when:
                if case._clause_holds(c, known):
                    return {"action": "eliminate", "hypothesis": h.id, "cited": [t for t in c.results if t in known],
                            "rationale": c.text}
        # Commit on a confirming result.
        for h in open_hyps:
            if any(known.get(t) == r for t, r in h.confirmed_by.items()):
                return {"action": "diagnose", "hypothesis": h.id, "rationale": f"{h.name} is confirmed by {', '.join(w.tests[t].title for t, r in h.confirmed_by.items() if known.get(t) == r)}."}
        if len(open_hyps) == 1:
            return {"action": "diagnose", "hypothesis": open_hyps[0].id, "rationale": f"{open_hyps[0].name} is what remains."}
        # Next test on the route that can still move an open hypothesis.
        for test in w.route:
            if test in known:
                continue
            t = w.tests[test]
            missing = [r for r in t.requires if r not in known]
            if missing:
                continue  # its prerequisite comes earlier on the route and is handled on its own turn
            if not any(case._test_informs(test, h) for h in open_hyps):
                continue
            blocked = False
            for rule in w.order_rules:
                if rule.test != test or not all(f in case.findings for f in rule.findings):
                    continue
                if rule.unless not in known:
                    blocked = True
                elif rule.unless_result is not None:
                    allowed = rule.unless_result if isinstance(rule.unless_result, tuple) else (rule.unless_result,)
                    if known[rule.unless] not in allowed:
                        blocked = True
            if blocked:
                continue
            return {"action": "order", "test": test, "rationale": f"Next on the route: {t.title}."}
        remainder = [h for h in open_hyps if h.remainder]
        if remainder and all(h.remainder or h.tier != "must_not_miss" for h in open_hyps):
            return {"action": "diagnose", "hypothesis": remainder[0].id, "rationale": "The dangerous causes are excluded; this is what remains."}
        return {"action": "undeterminable", "rationale": "The route is exhausted without a confirmed diagnosis."}

    def decide_shift(self, shift: Shift) -> dict[str, Any]:
        waiting = [w for w in shift.waiting_room() if w["status"] == "waiting"]
        if shift.current is None:
            if not waiting:
                return {"action": "end_day", "rationale": "Nobody left in the waiting room."}
            urgent = [w for w in waiting if w["triage"] == "urgent"]
            pick = (urgent or waiting)[0]
            return {"action": "see_patient", "case_id": pick["case_id"], "rationale": f"{pick['triage'].capitalize()} patient, first in line."}
        return self.decide(shift.cases[shift.current])
