"""A clinic day: a waiting room, a clock, and earnings. Tests cost real minutes
and real money; patients still waiting at closing time cost money, urgent
ones more.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any

from .difficulty import Difficulty, ShiftRules
from .elim import ElimCase, IllegalMove, eligible
from .worlds import World

DAY_START_HOUR = 9


def clock_text(minutes: int) -> str:
    h, m = divmod(DAY_START_HOUR * 60 + minutes, 60)
    return f"{h:02d}:{m:02d}"


@dataclass
class Shift:
    cases_in_order: list[ElimCase]
    difficulty: Difficulty
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    cases: dict[str, ElimCase] = field(init=False)
    order: list[str] = field(init=False)
    clock: int = 0
    current: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    # The reasoning behind the day-level move being applied, when there is one.
    pending_thinking: str = ""
    result: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.difficulty.shift is None:
            raise ValueError("shift presets only")
        self.cases = {c.id: c for c in self.cases_in_order}
        self.order = [c.id for c in self.cases_in_order]

    @property
    def rules(self) -> ShiftRules:
        assert self.difficulty.shift is not None
        return self.difficulty.shift

    @property
    def time_left(self) -> int:
        return max(0, self.rules.day_minutes - self.clock)

    # ---- what the doctor sees -------------------------------------------

    def waiting_room(self) -> list[dict[str, Any]]:
        rows = []
        for cid in self.order:
            case = self.cases[cid]
            status = "done" if case.result else ("in consult" if cid == self.current else "waiting")
            rows.append({
                "case_id": cid, "age": case.template.age, "sex": case.template.sex,
                "situation": case.world.title, "complaint": case.template.complaint,
                "triage": "urgent" if case.template.unstable else "routine",
                "status": status, "spend": case.spend,
                "outcome": self._outcome_label(case) if case.result else None,
            })
        return rows

    def view(self) -> dict[str, Any]:
        return {
            "shift_id": self.id, "mode": "shift", "difficulty": self.difficulty.as_dict(),
            "clock": self.clock, "clock_text": clock_text(self.clock), "day_end_text": clock_text(self.rules.day_minutes),
            "time_left": self.time_left, "earnings": self.earnings(),
            "seen": sum(1 for c in self.cases.values() if c.result),
            "waiting": sum(1 for cid, c in self.cases.items() if not c.result and cid != self.current),
            "waiting_room": self.waiting_room(),
            "current": self.cases[self.current].view() if self.current else None,
            "events": self.events[-14:],
            "done": self.result is not None, "result": self.result,
        }

    # ---- actions ---------------------------------------------------------

    def _tick(self, minutes: int, what: str) -> None:
        self.clock += minutes
        event = {"at": clock_text(min(self.clock, self.rules.day_minutes)), "what": what}
        if self.pending_thinking:
            event["thinking"] = self.pending_thinking
        self.events.append(event)
        if self.clock >= self.rules.day_minutes and self.result is None:
            self._end("the clock ran out")

    def see(self, case_id: str) -> None:
        self._open()
        if case_id not in self.cases:
            raise IllegalMove("unknown patient")
        if self.cases[case_id].result is not None:
            raise IllegalMove("that patient has already been seen")
        if self.current == case_id:
            return
        self.current = case_id
        c = self.cases[case_id]
        self._tick(self.rules.minutes_per_handover, f"called in the {c.template.age} year old {c.template.sex} ({c.world.title.lower()})")

    def apply(self, action: dict[str, Any]) -> None:
        self._open()
        kind = action["action"]
        self.pending_thinking = (action.get("thinking") or "").strip()
        try:
            self._dispatch(kind, action)
        finally:
            self.pending_thinking = ""

    def _dispatch(self, kind: str, action: dict[str, Any]) -> None:
        if kind == "see_patient":
            self.see(action["case_id"])
            return
        if kind == "end_day":
            self.end_day(action.get("by", "human"))
            return
        if self.current is None:
            raise IllegalMove("no patient in the consultation room; call one in first")
        case = self.cases[self.current]
        minutes = case.apply(action)
        what = {
            "history_exam": "took the history", "order": f"ordered {case.world.tests[action['test']].title}" if kind == "order" else "",
            "propose": "proposed " + ", ".join(list(action.get("hypotheses") or []) + ([action["hypothesis"]] if action.get("hypothesis") else [])),
            "eliminate": f"crossed off {case.eliminations[-1].name}" if kind == "eliminate" and case.eliminations else "",
            "escalate": "escalated", "diagnose": f"diagnosed {case.result['doctor_name'] if case.result else ''}",
            "undeterminable": "referred without a diagnosis",
        }.get(kind, kind)
        if case.result is not None:
            self.current = None
            what = f"{self._outcome_label(case)}: {case.result['truth_name']}"
        self._tick(minutes, what)
        if self.result is None and all(c.result for c in self.cases.values()):
            self._end("every patient was seen")

    def end_day(self, by: str = "human") -> dict[str, Any]:
        self._open()
        self._end("the doctor ended the day", by)
        assert self.result is not None
        return self.result

    def _open(self) -> None:
        if self.result is not None:
            raise IllegalMove("the day is over")

    # ---- economics -------------------------------------------------------

    def _outcome_label(self, case: ElimCase) -> str:
        r = case.result
        if r is None:
            return "open"
        if r["timed_out"]:
            return "unfinished"
        if r["undeterminable"]:
            return "referred"
        return "correct" if r["exact"] else "wrong"

    def _value(self, case: ElimCase) -> float:
        r = case.result
        rules = self.rules
        urgent = case.urgent
        if r is None or r["timed_out"]:
            return -(rules.penalty_unseen_urgent if urgent else rules.penalty_unseen) - case.spend
        if r["undeterminable"]:
            return rules.fee_referred - case.spend
        if r["exact"]:
            return rules.fee_correct - case.spend
        return -(rules.penalty_wrong_urgent if urgent else rules.penalty_wrong) - case.spend

    def earnings(self) -> float:
        return round(sum(self._value(c) for c in self.cases.values() if c.result), 2)

    def _end(self, why: str, by: str = "clock") -> None:
        if self.current is not None:
            case = self.cases[self.current]
            case._close(None, [], by=by, rationale="the day ended mid-consultation", timed_out=True)
            self.current = None
        rules = self.rules
        per_patient = []
        for cid in self.order:
            case = self.cases[cid]
            per_patient.append({
                "case_id": cid, "triage": "urgent" if case.urgent else "routine",
                "outcome": self._outcome_label(case) if case.result else "unseen",
                "value": round(self._value(case), 2), "spend": case.spend,
                "truth": case.truth_hyp.name, "situation": case.world.title,
                "tests": len([o for o in case.orders if o.test != "history_exam"]),
            })
        earnings = round(sum(p["value"] for p in per_patient), 2)
        best = rules.fee_correct * len(self.order)
        worst = -sum(rules.penalty_wrong_urgent if p["triage"] == "urgent" else rules.penalty_wrong for p in per_patient)
        counts = {k: sum(1 for p in per_patient if p["outcome"] == k) for k in ("correct", "wrong", "referred", "unfinished", "unseen")}
        urgent_unseen = sum(1 for p in per_patient if p["triage"] == "urgent" and p["outcome"] in ("unseen", "unfinished"))
        self.result = {
            "ended_because": why, "clock": min(self.clock, rules.day_minutes), "clock_text": clock_text(min(self.clock, rules.day_minutes)),
            "earnings": earnings, "best_possible": best, "spend": round(sum(p["spend"] for p in per_patient), 2),
            "day_score": round(max(0.0, min(1.0, (earnings - worst) / (best - worst))), 3) if best > worst else 0.0,
            "patients": len(self.order), **counts, "urgent_unseen": urgent_unseen, "per_patient": per_patient,
            "verdict": (
                f"Day over at {clock_text(min(self.clock, rules.day_minutes))} because {why}. "
                f"{counts['correct']} correct, {counts['wrong']} wrong, {counts['referred']} referred, "
                f"{counts['unseen'] + counts['unfinished']} not seen" + (f" ({urgent_unseen} urgent)" if urgent_unseen else "")
                + f". Earnings {earnings:+.0f} of a possible {best}."
            ),
        }


def new_shift(worlds: dict[str, World], d: Difficulty, rng: random.Random) -> Shift:
    assert d.shift is not None
    pool = eligible(worlds, d)
    picks = rng.sample(pool, min(d.shift.patients, len(pool)))
    return Shift([ElimCase(w, c, difficulty=d) for w, c in picks], d)
