"""A rule-based doctor that needs no model: a floor for the dashboard and a way
to exercise the evaluation harness offline.

It keeps the set of conditions still consistent with every positive answer,
asks the question that splits that set most evenly, and commits when one
condition is left or the budget is spent.
"""
from __future__ import annotations

from dataclasses import dataclass

from .data import Dataset, split_item
from .game import Case


@dataclass
class Decision:
    action: str  # ask | diagnose | undeterminable
    evidence_code: str | None = None
    pathology: str | None = None
    differential: list[str] | None = None
    rationale: str = ""


class GreedyDoctor:
    name = "baseline"

    def __init__(self, ds: Dataset) -> None:
        self.ds = ds

    def _candidates(self, case: Case) -> list[str]:
        positives = {split_item(case.patient.initial_evidence)[0]}
        negatives: set[str] = set()
        for t in case.turns:
            if t.unsure:
                continue
            ev = self.ds.evidences[t.code]
            is_no = t.answer in ("No", "Not applicable", "0 (none)")
            (negatives if is_no else positives).add(t.code)
        cands = [
            c for c in self.ds.conditions.values() if positives <= c.clue_codes
        ] or list(self.ds.conditions.values())
        # Rank by how many of the known positives the condition explains, then by
        # how few negatives it would have expected.
        cands.sort(
            key=lambda c: (-len(positives & c.clue_codes), len(negatives & c.clue_codes), c.name)
        )
        return [c.name for c in cands]

    def decide(self, case: Case) -> Decision:
        cands = self._candidates(case)
        asked = {t.code for t in case.turns if not t.unsure}
        left = case.difficulty.max_questions - len(case.turns)
        if len(cands) == 1 or left <= 0:
            return Decision(
                "diagnose", pathology=cands[0], differential=cands[1:4],
                rationale=f"{len(cands)} condition(s) still fit what the patient said.",
            )
        half = len(cands) / 2
        best, best_gap = None, None
        for code, ev in self.ds.evidences.items():
            if code in asked or ev.data_type != "B":
                continue
            k = sum(code in self.ds.conditions[c].clue_codes for c in cands)
            if k == 0 or k == len(cands):
                continue
            gap = abs(k - half)
            if best_gap is None or gap < best_gap:
                best, best_gap = code, gap
        if best is None:
            return Decision(
                "diagnose", pathology=cands[0], differential=cands[1:4],
                rationale="No question separates the remaining candidates.",
            )
        return Decision(
            "ask", evidence_code=best,
            rationale=f"Splits the {len(cands)} remaining candidates most evenly.",
        )
