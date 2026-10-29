"""One diagnosis-by-elimination case: a patient from a world, a test menu with
results, prices and minutes, and a grader that judges the doctor's actions
against the world's hidden hypothesis board.

The doctor never sees the board. They name what could be going on in their
own words (``propose``), order tests, cross hypotheses off citing results, and
commit. The grader maps their wording to the world's hypotheses and scores the
differential they built, every elimination against the world's rules, the
final answer, and spend.

Everything the grader needs is in the case: the truth comes with the template
and every rule is machine-checkable, so no medical judgement happens here.
"""
from __future__ import annotations

import itertools
import random
import uuid
from dataclasses import dataclass, field
from typing import Any

from .difficulty import PRESETS, Difficulty
from .worlds import CaseTemplate, Clause, Hypothesis, Shortcut, World


class IllegalMove(ValueError):
    pass


@dataclass
class Order:
    test: str
    title: str
    result: str
    report: str
    price: float
    minutes: int
    by: str
    rationale: str
    at_minute: int
    repeat: bool = False
    violations: list[str] = field(default_factory=list)
    unnecessary: bool = False
    seq: int = 0

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Elimination:
    hypothesis: str
    cited: list[str]
    by: str
    rationale: str
    at_minute: int
    validity: str  # valid | shortcut | unsupported
    reason: str
    inferred: bool = False
    seq: int = 0
    name: str = ""
    text: str = ""  # the doctor's own wording

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Proposal:
    """One hypothesis the doctor put forward, in their words."""

    text: str
    hypothesis: str | None  # the world's id it resolved to; None when it is not on the hidden board
    by: str
    rationale: str
    at_minute: int
    seq: int
    tests_before: int  # paid tests already ordered when it was proposed
    implicit: bool = False  # inferred from an eliminate/diagnose that named it without proposing it first

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _matches(required: dict[str, str | tuple[str, ...]], known: dict[str, str]) -> bool:
    for test, wanted in required.items():
        got = known.get(test)
        if got is None:
            return False
        if isinstance(wanted, tuple):
            if got not in wanted:
                return False
        elif got != wanted:
            return False
    return True


@dataclass
class ElimCase:
    world: World
    template: CaseTemplate
    difficulty: Difficulty = field(default_factory=lambda: PRESETS["standard"])
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    orders: list[Order] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    eliminations: list[Elimination] = field(default_factory=list)
    escalated_at: int | None = None
    escalation_rationale: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    # The reasoning behind the move being applied right now, when the doctor
    # supplies one. Set by apply(), attached to the action log by _log().
    pending_thinking: str = ""
    minutes: int = 0
    result: dict[str, Any] | None = None

    # ---- what the patient produces ----------------------------------------

    @property
    def truth_id(self) -> str:
        return self.template.truth

    @property
    def truth_hyp(self) -> Hypothesis:
        return self.world.hypotheses[self.truth_id]

    def result_for(self, test: str) -> str:
        return self.template.results.get(test) or self.truth_hyp.results.get(test) or next(iter(self.world.tests[test].results))

    @property
    def findings(self) -> tuple[str, ...]:
        return self.template.findings

    @property
    def known(self) -> dict[str, str]:
        return {o.test: o.result for o in self.orders}

    @property
    def spend(self) -> float:
        return round(sum(o.price for o in self.orders), 2)

    @property
    def history_taken(self) -> bool:
        return "history_exam" in self.known

    @property
    def urgent(self) -> bool:
        return self.template.unstable or self.truth_hyp.tier == "must_not_miss"

    def status_of(self, hyp: str) -> str:
        if self.result and self.result["doctor_hypothesis"] == hyp:
            return "diagnosed"
        for e in self.eliminations:
            if e.hypothesis == hyp:
                return "eliminated"
        return "open"

    def considered(self, hyp: str) -> bool:
        return any(p.hypothesis == hyp for p in self.proposals)

    @property
    def paid_tests(self) -> int:
        return sum(1 for o in self.orders if o.price > 0)

    def _differential(self) -> list[dict[str, Any]]:
        out = []
        for p in self.proposals:
            h = self.world.hypotheses.get(p.hypothesis) if p.hypothesis else None
            out.append(p.as_dict() | {
                "name": h.name if h else p.text,
                "status": self.status_of(p.hypothesis) if p.hypothesis else "open",
            })
        return out

    def _thoughts(self) -> list[dict[str, Any]]:
        """The reasoning behind each move, in order. The seq of a logged action
        is its index, which is what orders, proposals and eliminations carry."""
        return [
            {"seq": i, "kind": a["kind"], "by": a["by"], "at_minute": a["at_minute"],
             "rationale": a.get("rationale", ""), "thinking": a["thinking"]}
            for i, a in enumerate(self.actions) if a.get("thinking")
        ]

    # ---- views ---------------------------------------------------------------

    def view(self) -> dict[str, Any]:
        d = self.difficulty
        tests = []
        for t in self.world.tests.values():
            p = t.price
            tests.append({
                "id": t.id, "title": t.title, "station": t.station,
                "price": p.usd if d.show_prices else None, "minutes": p.minutes,
                "cpt": p.cpt if d.show_prices else None,
                "requires": list(t.requires), "done": t.id in self.known,
            })
        return {
            "case_id": self.id,
            "situation": self.world.situation,
            "title": self.world.title,
            "presentation": self.world.presentation,
            "age": self.template.age,
            "sex": self.template.sex,
            "complaint": self.template.complaint,
            # The nurse's flag at the door: visible, like the vital signs it rests on.
            "triage": "urgent" if self.template.unstable else "routine",
            "findings": list(self.findings) if self.history_taken else None,
            # The doctor's own differential: nothing here comes from the hidden board.
            "differential": self._differential(),
            "tests": tests,
            "orders": [o.as_dict() for o in self.orders],
            # The doctor's own reasoning behind each move, when they gave any.
            "thoughts": self._thoughts(),
            "eliminations": [
                {"hypothesis": e.hypothesis, "name": e.name, "text": e.text, "cited": e.cited, "by": e.by, "rationale": e.rationale, "at_minute": e.at_minute, "seq": e.seq}
                for e in self.eliminations
            ],
            "escalated": self.escalated_at is not None,
            "spend": self.spend if d.show_prices else None,
            "minutes": self.minutes,
            "budget_usd": d.budget_usd or None,
            "difficulty": d.as_dict(),
            "done": self.result is not None,
            "result": self.result,
        }

    def truth(self) -> dict[str, Any]:
        t = self.template
        return {
            "truth": self.truth_id,
            "truth_name": self.truth_hyp.name,
            "tier": self.truth_hyp.tier,
            "case_template": t.id,
            "tempts": t.tempts,
            "decoy": t.decoy,
            "decoy_name": self.world.hypotheses[t.decoy].name if t.decoy else None,
            "note": t.note,
            "unstable": t.unstable,
            "findings": list(t.findings),
            "results": {tid: {"result": self.result_for(tid), "report": self.world.tests[tid].results[self.result_for(tid)]} for tid in self.world.tests},
            "reference_route": self._reference_route(),
            # The hidden board, for the verdict screen and the dashboard only.
            "board": [
                {"id": h.id, "name": h.name, "tier": h.tier, "remainder": h.remainder,
                 "rules": [c.text for c in h.eliminate_when], "do_not_rely": [x.text for x in h.do_not_rely],
                 "confirmed_by": {k: self.world.tests[k].results[v] for k, v in h.confirmed_by.items()},
                 "settled_by": [t.title for t in self.world.tests.values() if self._test_informs(t.id, h)]}
                for h in self.world.hypotheses.values()
            ],
            "route": list(self.world.route),
        }

    # ---- actions -------------------------------------------------------------

    def _open(self) -> None:
        if self.result is not None:
            raise IllegalMove("the case is already closed")

    def _log(self, kind: str, by: str, rationale: str, **extra: Any) -> None:
        entry = {"kind": kind, "by": by, "rationale": rationale, "at_minute": self.minutes, "spend": self.spend, **extra}
        if self.pending_thinking:
            entry["thinking"] = self.pending_thinking
        self.actions.append(entry)

    def order(self, test: str, by: str = "human", rationale: str = "") -> Order:
        self._open()
        t = self.world.tests.get(test)
        if t is None:
            raise IllegalMove(f"unknown test {test!r}")
        missing = [r for r in t.requires if r not in self.known]
        if missing:
            raise IllegalMove(f"{t.title} needs {', '.join(self.world.tests[m].title for m in missing)} first")
        result = self.result_for(test)
        violations = [
            r.text for r in self.world.order_rules
            if r.test == test and all(f in self.findings for f in r.findings)
            and (r.unless not in self.known or (r.unless_result is not None and self.known[r.unless] not in (r.unless_result if isinstance(r.unless_result, tuple) else (r.unless_result,))))
        ]
        informs = [h for h in self.world.hypotheses.values() if self._test_informs(test, h)]
        unnecessary = bool(informs) and all(self.status_of(h.id) != "open" for h in informs) and test != "history_exam"
        o = Order(test, t.title, result, t.results[result], t.price.usd, t.price.minutes, by, rationale, self.minutes,
                  repeat=test in self.known, violations=violations, unnecessary=unnecessary, seq=len(self.actions))
        self.orders.append(o)
        self.minutes += t.price.minutes
        self._log("order", by, rationale, test=test, result=result, violations=violations, unnecessary=unnecessary)
        if self.difficulty.budget_usd and self.spend > self.difficulty.budget_usd:
            self._close(None, [], by="budget", rationale="spend went over the budget", timed_out=True)
        return o

    def _test_informs(self, test: str, h: Hypothesis) -> bool:
        if test in h.confirmed_by:
            return True
        return any(test in c.results for c in h.eliminate_when)

    def propose(self, texts: list[str], by: str = "human", rationale: str = "", implicit: bool = False) -> list[Proposal]:
        """The doctor names what could be going on. Each phrase is mapped to the
        hidden board; a phrase that matches nothing is kept as off-board."""
        self._open()
        texts = [t.strip() for t in texts if t and t.strip()]
        if not texts:
            raise IllegalMove("propose at least one hypothesis")
        added = []
        for text in texts:
            hyp = self.world.resolve(text)
            if hyp is not None and self.considered(hyp):
                continue  # already on the doctor's differential
            if hyp is None and any(p.hypothesis is None and p.text.lower() == text.lower() for p in self.proposals):
                continue
            p = Proposal(text, hyp, by, rationale, self.minutes, len(self.actions), self.paid_tests, implicit)
            self.proposals.append(p)
            added.append(p)
        if added:
            self._log("propose", by, rationale, hypotheses=[p.text for p in added], resolved=[p.hypothesis for p in added], implicit=implicit)
        return added

    def _named(self, text: str | None, what: str) -> Hypothesis:
        if not text:
            raise IllegalMove(f"{what} needs a hypothesis")
        hyp = self.world.resolve(text)
        if hyp is None:
            raise IllegalMove(f"could not read {text!r} as a condition this case can be worked up for; name it differently")
        return self.world.hypotheses[hyp]

    def eliminate(self, hyp: str, cited: list[str], by: str = "human", rationale: str = "") -> Elimination:
        self._open()
        h = self._named(hyp, "eliminate")
        if h.remainder:
            raise IllegalMove(f"{h.name} is a diagnosis of exclusion; it cannot be crossed off, only left over")
        if self.status_of(h.id) != "open":
            raise IllegalMove(f"{h.name} is already crossed off")
        unknown = [c for c in cited if c not in self.known]
        if unknown:
            raise IllegalMove(f"cannot cite tests that were not done: {', '.join(unknown)}")
        if not self.considered(h.id):
            self.propose([hyp], by, rationale, implicit=True)
        validity, reason, inferred = self._judge(h, cited)
        e = Elimination(h.id, list(cited), by, rationale, self.minutes, validity, reason, inferred, seq=len(self.actions), name=h.name, text=hyp)
        self.eliminations.append(e)
        self._log("eliminate", by, rationale, hypothesis=h.id, name=h.name, text=hyp, cited=list(cited), validity=validity)
        return e

    def _judge(self, h: Hypothesis, cited: list[str]) -> tuple[str, str, bool]:
        known = {t: self.known[t] for t in cited}
        for c in h.eliminate_when:
            if self._clause_holds(c, known):
                return "valid", c.text, c.inferred
        # A valid rule exists in the results on file but was not cited: still a reasoning miss.
        for s in h.do_not_rely:
            if _matches(s.results, known) and all(f in self.findings for f in s.findings):
                return "shortcut", s.text, False
        if not cited:
            return "unsupported", "No test result was cited.", False
        return "unsupported", "The cited results do not satisfy any elimination rule for this hypothesis.", False

    def _clause_holds(self, c: Clause, known: dict[str, str]) -> bool:
        return (
            _matches(c.results, known)
            and all(f in self.findings for f in c.findings)
            and not any(f in self.findings for f in c.unless_findings)
        )

    def _truth_confirmed(self, known: dict[str, str]) -> bool:
        return any(known.get(t) == r for t, r in self.truth_hyp.confirmed_by.items())

    def escalate(self, by: str = "human", rationale: str = "") -> None:
        self._open()
        if self.escalated_at is not None:
            raise IllegalMove("already escalated")
        self.escalated_at = self.minutes
        self.escalation_rationale = rationale
        self._log("escalate", by, rationale)

    def diagnose(self, hyp: str | None, by: str = "human", rationale: str = "", undeterminable: bool = False) -> dict[str, Any]:
        """Commit. A diagnosis the board does not recognise is still a
        commitment: it is graded as wrong, not rejected."""
        self._open()
        if undeterminable:
            return self._close(None, [], by, rationale, timed_out=False, undeterminable=True)
        if not hyp or not hyp.strip():
            raise IllegalMove("diagnose needs a hypothesis")
        resolved = self.world.resolve(hyp)
        if resolved is not None and not self.considered(resolved):
            self.propose([hyp], by, rationale, implicit=True)
        return self._close(resolved, [], by, rationale, timed_out=False, undeterminable=False, said=hyp)

    def apply(self, action: dict[str, Any]) -> int:
        """Apply one doctor action; returns the minutes it took."""
        before = self.minutes
        kind = action["action"]
        by = action.get("by", "human")
        rationale = action.get("rationale", "")
        self.pending_thinking = (action.get("thinking") or "").strip()
        try:
            return self._dispatch(kind, action, by, rationale, before)
        finally:
            self.pending_thinking = ""

    def _dispatch(self, kind: str, action: dict[str, Any], by: str, rationale: str, before: int) -> int:
        if kind == "history_exam":
            self.order("history_exam", by, rationale)
        elif kind == "order":
            self.order(action["test"], by, rationale)
        elif kind == "propose":
            texts = list(action.get("hypotheses") or [])
            if action.get("hypothesis"):
                texts.append(action["hypothesis"])
            self.propose(texts, by, rationale)
        elif kind == "eliminate":
            self.eliminate(action["hypothesis"], list(action.get("cited") or []), by, rationale)
        elif kind == "escalate":
            self.escalate(by, rationale)
        elif kind == "diagnose":
            self.diagnose(action.get("hypothesis"), by, rationale)
        elif kind == "undeterminable":
            self.diagnose(None, by, rationale, undeterminable=True)
        else:
            raise IllegalMove(f"unknown action {kind!r}")
        return self.minutes - before

    # ---- grading -------------------------------------------------------------

    def _reference_route(self) -> dict[str, Any]:
        """The cheapest set of tests that validly eliminates every other
        must-not-miss hypothesis and confirms the truth where a confirming test
        exists. Brute force: the worlds have at most eleven tests."""
        w = self.world
        truth = self.truth_hyp
        others = [h for h in w.hypotheses.values() if h.tier == "must_not_miss" and h.id != truth.id]
        test_ids = [t for t in w.tests if t != "history_exam"]
        truth_results = {t: self.result_for(t) for t in w.tests}
        needs_confirm = bool(truth.confirmed_by) and not truth.remainder

        def ok(subset: tuple[str, ...]) -> bool:
            known = {t: truth_results[t] for t in subset} | {"history_exam": "done"}
            for t in subset:
                if any(r not in subset and r != "history_exam" for r in w.tests[t].requires):
                    return False
                for rule in w.order_rules:
                    if rule.test != t or not all(f in self.findings for f in rule.findings):
                        continue
                    if rule.unless not in subset and rule.unless != "history_exam":
                        return False
                    if rule.unless_result is not None:
                        allowed = rule.unless_result if isinstance(rule.unless_result, tuple) else (rule.unless_result,)
                        if truth_results[rule.unless] not in allowed:
                            return False
            # A confirmed diagnosis closes the case; otherwise every other
            # must-not-miss hypothesis needs a valid elimination.
            if needs_confirm and self._truth_confirmed(known):
                return True
            if needs_confirm:
                return False
            return all(any(self._clause_holds(c, known) for c in h.eliminate_when) for h in others)

        best: tuple[str, ...] | None = None
        best_cost = float("inf")
        for n in range(0, len(test_ids) + 1):
            for subset in itertools.combinations(test_ids, n):
                cost = sum(w.tests[t].price.usd for t in subset)
                if cost < best_cost and ok(subset):
                    best, best_cost = subset, cost
        tests = ["history_exam"] + list(best or ())
        return {"tests": tests, "cost": round(best_cost if best is not None else 0.0, 2),
                "minutes": sum(w.tests[t].price.minutes for t in tests), "feasible": best is not None}

    def _close(self, hyp: str | None, _unused: list, by: str, rationale: str, timed_out: bool, undeterminable: bool = False, said: str | None = None) -> dict[str, Any]:
        w = self.world
        truth = self.truth_hyp
        exact = (hyp == truth.id)
        others = [h for h in w.hypotheses.values() if h.tier == "must_not_miss" and h.id != truth.id]
        elim_by_hyp = {e.hypothesis: e for e in self.eliminations}
        mnm_report = []
        for h in others:
            e = elim_by_hyp.get(h.id)
            if e:
                status, reason = e.validity, e.reason
            elif self.considered(h.id):
                status, reason = "open", "proposed but never crossed off"
            else:
                status, reason = "never_considered", "never came up in the doctor's differential"
            mnm_report.append({"hypothesis": h.id, "name": h.name, "status": status, "reason": reason, "considered": self.considered(h.id)})
        valid_mnm = sum(1 for r in mnm_report if r["status"] == "valid")
        truth_confirmed = exact and self._truth_confirmed(self.known)
        if truth_confirmed:
            for r in mnm_report:
                if r["status"] in ("open", "never_considered"):
                    r["status"] = "explained"
                    r["reason"] = "the confirmed diagnosis explains the picture"
        # The differential the doctor built, judged against the whole hidden board.
        all_mnm = [h for h in w.hypotheses.values() if h.tier == "must_not_miss"]
        considered_mnm = [h.id for h in all_mnm if self.considered(h.id)]
        differential_recall = round(len(considered_mnm) / len(all_mnm), 3) if all_mnm else 1.0
        never_considered = [h.name for h in all_mnm if not self.considered(h.id)]
        off_board = [p.text for p in self.proposals if p.hypothesis is None]
        explicit = [p for p in self.proposals if not p.implicit]
        if not explicit:
            differential_first = "never"
        elif explicit[0].tests_before == 0:
            differential_first = "before_tests"
        else:
            differential_first = "after_tests"
        safe_closure = (not others) or valid_mnm == len(others) or truth_confirmed
        unsafe = [e.as_dict() for e in self.eliminations if e.validity != "valid"]
        truth_eliminated = truth.id in elim_by_hyp
        gate = "ok"
        if self.template.unstable:
            if self.escalated_at is None:
                gate = "missed"
            elif any(o.price > 0 and o.at_minute < self.escalated_at for o in self.orders):
                gate = "late"
        elif self.escalated_at is not None:
            gate = "false_alarm"
        violations = [v for o in self.orders for v in o.violations]
        unnecessary = [o.test for o in self.orders if o.unnecessary]
        repeats = sum(1 for o in self.orders if o.repeat)
        ref = self._reference_route()
        spend = self.spend
        cost_eff = 1.0 if spend <= ref["cost"] else round(ref["cost"] / spend, 3) if spend else 1.0
        missed_dangerous = truth.tier == "must_not_miss" and not exact
        # Thinking process: the differential built (did the dangerous causes
        # come up, and before tests were thrown at the patient?), the
        # eliminations (valid rules, cited results), then penalties for
        # shortcuts, a missed gate and ordering violations.
        elimination_share = 1.0 if (not others or truth_confirmed) else valid_mnm / len(others)
        timing = {"before_tests": 1.0, "after_tests": 0.5, "never": 0.0}[differential_first]
        process = 0.5 * elimination_share + 0.3 * differential_recall + 0.2 * timing
        process -= 0.25 * len(unsafe)
        if gate in ("missed", "late"):
            process -= 0.25
        process -= 0.1 * len(violations)
        process = round(max(0.0, min(1.0, process)), 3)
        outcome = 1.0 if exact else (0.3 if (undeterminable and safe_closure) else 0.0)
        score = round(0.5 * outcome + 0.3 * process + 0.2 * (cost_eff if not timed_out else 0.0), 3)
        if undeterminable:
            said = "cannot determine"
        elif hyp:
            said = w.hypotheses[hyp].name
        else:
            said = said or "nothing"
        thinking = f"Considered {len(self.proposals)} hypotheses, {len(considered_mnm)} of the {len(all_mnm)} dangerous ones"
        if never_considered:
            thinking += f"; never considered {', '.join(never_considered)}"
        thinking += "."
        if timed_out:
            verdict = f"Closed without a diagnosis ({rationale}). The patient has {truth.name}. {thinking}"
        elif exact and safe_closure and not unsafe and not never_considered:
            verdict = f"Correct: {truth.name}, every dangerous alternative considered and eliminated by a valid rule. Spent ${spend:.0f} against a cheapest safe route of ${ref['cost']:.0f}."
        elif exact:
            problems = []
            if never_considered:
                problems.append(f"{', '.join(never_considered)} never considered")
            if not safe_closure:
                left = [r["name"] for r in mnm_report if r["status"] not in ("valid", "explained", "never_considered")]
                if left:
                    problems.append(f"{', '.join(left)} never properly excluded")
            if unsafe:
                problems.append(f"{len(unsafe)} elimination(s) rested on a shortcut or no rule")
            verdict = f"Right answer, unsafe path: {truth.name}, but {'; '.join(problems)}."
        else:
            if truth_eliminated:
                why = f"{truth.name} was crossed off ({elim_by_hyp[truth.id].validity})"
            elif self.considered(truth.id):
                why = f"{truth.name} was on the differential and still open"
            else:
                why = f"{truth.name} never came up"
            verdict = f"Missed: said {said}, the patient has {truth.name}. {why}. {thinking}"
            if missed_dangerous:
                verdict += " A must-not-miss condition was missed."
        if gate == "missed":
            verdict += " The patient was unstable and was never escalated."
        elif gate == "late":
            verdict += " Escalation came after paid tests."
        elif gate == "false_alarm":
            verdict += " A stable patient was escalated."
        self.result = {
            "by": by, "rationale": rationale, "undeterminable": undeterminable, "timed_out": timed_out,
            "doctor_hypothesis": hyp, "doctor_name": said,
            "differential": self._differential(), "proposed_count": len(self.proposals),
            "differential_recall": differential_recall, "truth_considered": self.considered(truth.id),
            "never_considered": never_considered, "off_board": off_board, "differential_first": differential_first,
            "truth": truth.id, "truth_name": truth.name, "truth_tier": truth.tier,
            "situation": w.situation, "case_template": self.template.id, "tempts": self.template.tempts, "decoy": self.template.decoy,
            "exact": exact, "missed_dangerous": missed_dangerous, "truth_eliminated": truth_eliminated,
            "safe_closure": safe_closure, "truth_confirmed": truth_confirmed, "must_not_miss": mnm_report, "valid_mnm": valid_mnm, "mnm_total": len(others),
            "unsafe_eliminations": unsafe, "eliminations": [e.as_dict() for e in self.eliminations],
            "gate": gate, "unstable": self.template.unstable,
            "order_violations": violations, "unnecessary_tests": unnecessary, "repeats": repeats,
            "tests_ordered": [o.test for o in self.orders if o.test != "history_exam"],
            "spend": spend, "reference_cost": ref["cost"], "reference_tests": ref["tests"], "cost_efficiency": cost_eff,
            "minutes": self.minutes, "reference_minutes": ref["minutes"],
            "process_score": process, "outcome_score": outcome, "score": score,
            "verdict": verdict,
        }
        self.result["differential"] = self._differential()  # statuses now include "diagnosed"
        self._log("close", by, rationale, hypothesis=hyp, undeterminable=undeterminable)
        return self.result


def eligible(worlds: dict[str, World], d: Difficulty) -> list[tuple[World, CaseTemplate]]:
    out = []
    for w in worlds.values():
        if d.situations and w.situation not in d.situations:
            continue
        for c in w.cases:
            if d.case_pool == "traps" and not c.decoy:
                continue
            out.append((w, c))
    return out


def new_case(worlds: dict[str, World], d: Difficulty, rng: random.Random) -> ElimCase:
    w, c = rng.choice(eligible(worlds, d))
    return ElimCase(w, c, difficulty=d)
