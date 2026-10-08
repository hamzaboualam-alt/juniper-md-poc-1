"""One diagnosis case: what the doctor sees, what the patient answers, how it is graded.

Grading is label comparison only. The truth comes with the DDXPlus patient, so
no medical judgement is needed anywhere in this file.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .data import Dataset, Patient, as_complaint, split_item
from .difficulty import PRESETS, Difficulty, normalise_condition, truth_stats, unsure

UNSURE_ANSWER = "I'm not sure, sorry."


class BudgetExhausted(ValueError):
    pass


@dataclass
class Turn:
    code: str
    question: str
    answer: str
    repeat: bool
    by: str  # "human", "claude" or "baseline"
    rationale: str = ""
    unsure: bool = False

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class Case:
    ds: Dataset
    patient: Patient
    difficulty: Difficulty = field(default_factory=lambda: PRESETS["warmup"])
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    turns: list[Turn] = field(default_factory=list)
    result: dict[str, Any] | None = None

    # ---- what the doctor sees -------------------------------------------

    def view(self) -> dict[str, Any]:
        item = self.patient.initial_evidence
        question, answer = self.ds.describe(item)
        data_type = self.ds.evidences[split_item(item)[0]].data_type
        return {
            "case_id": self.id,
            "age": self.patient.age,
            "sex": "female" if self.patient.sex == "F" else "male",
            "initial_complaint": {
                "question": question,
                "answer": answer,
                "statement": as_complaint(question, answer, data_type),
            },
            "difficulty": self.difficulty.as_dict(),
            "questions_left": self.difficulty.max_questions - len(self.turns),
            "clue_count": len(self.patient.evidence_codes) if self.difficulty.show_clue_count else None,
            "transcript": [t.as_dict() for t in self.turns],
            "done": self.result is not None,
            "result": self.result,
        }

    # ---- the hidden truth, for the reveal panel --------------------------

    def truth(self) -> dict[str, Any]:
        cond = self.ds.conditions[self.patient.pathology]
        rank, p = truth_stats(self.patient)
        clues = []
        for item in self.patient.evidences:
            code, _ = split_item(item)
            question, answer = self.ds.describe(item)
            clues.append(
                {
                    "code": code,
                    "question": question,
                    "answer": answer,
                    "kind": self.ds.evidences[code].kind,
                    "is_initial": item == self.patient.initial_evidence,
                    "points_to_truth": code in cond.clue_codes,
                }
            )
        return {
            "pathology": cond.name,
            "icd10": cond.icd10,
            "severity": cond.severity,
            "truth_rank_in_reference": rank,
            "truth_probability_in_reference": round(p, 3),
            "age": self.patient.age,
            "sex": "female" if self.patient.sex == "F" else "male",
            "clues": clues,
            "reference_differential": [
                {"name": n, "probability": p} for n, p in self.patient.differential
            ],
        }

    # ---- actions ---------------------------------------------------------

    def ask(self, code: str, by: str = "human", rationale: str = "") -> Turn:
        if self.result is not None:
            raise ValueError("case already diagnosed")
        if code not in self.ds.evidences:
            raise KeyError(code)
        if len(self.turns) >= self.difficulty.max_questions:
            raise BudgetExhausted("question budget exhausted; commit a diagnosis")
        asked_before = [t for t in self.turns if t.code == code]
        hesitates = unsure(self.id, code, self.difficulty.patient_recall) and not any(
            t.unsure for t in asked_before
        )
        turn = Turn(
            code=code,
            question=self.ds.evidences[code].question,
            answer=UNSURE_ANSWER if hesitates else self.ds.answer(self.patient, code),
            # Re-asking after "I'm not sure" is the intended move, not a repeat.
            repeat=any(not t.unsure for t in asked_before),
            by=by,
            rationale=rationale,
            unsure=hesitates,
        )
        self.turns.append(turn)
        return turn

    def diagnose(
        self,
        pathology: str | None,
        differential: list[str],
        undeterminable: bool = False,
        by: str = "human",
        rationale: str = "",
        timed_out: bool = False,
    ) -> dict[str, Any]:
        if self.result is not None:
            raise ValueError("case already diagnosed")
        raw = pathology
        if not undeterminable:
            pathology = normalise_condition(pathology, self.ds)
            if pathology is None and raw and self.difficulty.show_candidates:
                raise KeyError(raw)
        differential = [
            d for d in (normalise_condition(x, self.ds) for x in differential) if d
        ]
        self.result = self._grade(pathology, raw, differential, undeterminable, by, rationale, timed_out)
        return self.result

    # ---- grading ---------------------------------------------------------

    def _grade(
        self,
        pathology: str | None,
        raw: str | None,
        differential: list[str],
        undeterminable: bool,
        by: str,
        rationale: str,
        timed_out: bool,
    ) -> dict[str, Any]:
        truth = self.patient.pathology
        cond = self.ds.conditions[truth]
        answered = {t.code for t in self.turns if not t.unsure}
        patient_codes = self.patient.evidence_codes
        initial_code = split_item(self.patient.initial_evidence)[0]
        known = (answered | {initial_code}) & patient_codes

        doctor_ddx: list[str] = []
        for name in ([pathology] if pathology else []) + list(differential):
            if name and name not in doctor_ddx:
                doctor_ddx.append(name)
        reference = [n for n, _ in self.patient.differential]

        exact = (not undeterminable) and pathology == truth
        rank = doctor_ddx.index(truth) + 1 if truth in doctor_ddx else None
        overlap = (
            len(set(doctor_ddx) & set(reference)) / len(reference) if reference else 0.0
        )
        coverage = len(known) / len(patient_codes) if patient_codes else 0.0
        missed = [
            {
                "code": c,
                "question": self.ds.evidences[c].question,
                "answer": self.ds.answer(self.patient, c),
            }
            for c in sorted(patient_codes - known)
            if c in cond.clue_codes
        ]
        score = round(0.6 * exact + 0.2 * overlap + 0.2 * coverage, 3)
        ref_rank, ref_p = truth_stats(self.patient)

        return {
            "by": by,
            "rationale": rationale,
            "undeterminable": undeterminable,
            "timed_out": timed_out,
            "doctor_pathology": pathology,
            "doctor_pathology_raw": raw,
            "unrecognised_name": bool(raw) and pathology is None and not undeterminable,
            "doctor_differential": doctor_ddx,
            "truth": truth,
            "truth_severity": cond.severity,
            "truth_rank_in_reference": ref_rank,
            "truth_probability_in_reference": round(ref_p, 3),
            "exact": exact,
            "truth_rank_in_doctor_ddx": rank,
            "answer_in_reference_ddx": (pathology in reference) if pathology else False,
            "reference_differential": reference,
            "ddx_overlap": round(overlap, 3),
            "evidence_coverage": round(coverage, 3),
            "clues_known": len(known),
            "clues_total": len(patient_codes),
            "questions_asked": len(self.turns),
            "questions_budget": self.difficulty.max_questions,
            "repeats": sum(t.repeat for t in self.turns),
            "unsure_answers": sum(t.unsure for t in self.turns),
            "missed_key_clues": missed,
            "score": score,
            "verdict": self._verdict(
                pathology, raw, undeterminable, timed_out, truth, exact, rank, coverage, missed, reference
            ),
        }

    def _verdict(
        self,
        pathology: str | None,
        raw: str | None,
        undeterminable: bool,
        timed_out: bool,
        truth: str,
        exact: bool,
        rank: int | None,
        coverage: float,
        missed: list[dict[str, str]],
        reference: list[str],
    ) -> str:
        n = len(self.turns)
        pct = f"{coverage:.0%}"
        if timed_out:
            return (
                f"The doctor used all {n} questions without committing. "
                f"The patient has {truth}; {pct} of the clues had been uncovered."
            )
        if undeterminable:
            return (
                f"The doctor declined to diagnose after {n} questions. "
                f"The patient does have a condition on record: {truth}. "
                f"Only {pct} of the patient's clues had been uncovered."
            )
        if exact:
            return (
                f"Correct: {truth}, reached after {n} questions, "
                f"having uncovered {pct} of the patient's clues."
            )
        said = pathology or f"'{raw}' (not a recognised condition)"
        where = (
            f"{truth} was rank {rank} in the doctor's own differential"
            if rank
            else f"{truth} was not in the doctor's differential at all"
        )
        plausible = (
            f"{pathology} was a plausible alternative in the reference differential"
            if pathology in reference
            else f"{said} was not in the reference differential"
        )
        missed_text = ""
        if missed:
            names = "; ".join(f"'{m['question']}' ({m['answer']})" for m in missed[:3])
            missed_text = f" Never asked: {names}."
        return f"Missed: said {said}, the patient has {truth}. {where}; {plausible}.{missed_text}"
