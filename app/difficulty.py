"""Difficulty levers. Every lever raises the cost of reaching the answer; none
changes the answer, so the grader is untouched by the preset.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import asdict, dataclass

from .data import Dataset, Patient


@dataclass(frozen=True)
class Difficulty:
    name: str
    max_questions: int = 20
    # all: any patient. hard: the rule-based reference differential itself ranks
    # another condition first AND gives the truth under 25%, so the textbook
    # picture points elsewhere (about 22% of DDXPlus patients).
    case_pool: str = "all"
    # Probability that a question first gets "I'm not sure". Asking again gets the
    # real answer, so the information is recoverable but costs a turn.
    patient_recall: float = 0.0
    # Whether the doctor is shown the list of candidate conditions. Hidden, the
    # doctor must name the condition in free text, which is normalised against the
    # list; an unrecognised name is graded as a miss.
    show_candidates: bool = True
    # Whether the doctor is told how many clues the patient has on record.
    show_clue_count: bool = False
    description: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


PRESETS: dict[str, Difficulty] = {
    "warmup": Difficulty(
        "warmup", max_questions=20, description="20 questions, any patient, candidate list shown."
    ),
    "standard": Difficulty(
        "standard", max_questions=12, description="12 questions, any patient, candidate list shown."
    ),
    "hard": Difficulty(
        "hard", max_questions=8, case_pool="hard", patient_recall=0.25, show_candidates=False,
        description="8 questions, misleading cases only, patient unsure 25% of the time, no candidate list.",
    ),
    "brutal": Difficulty(
        "brutal", max_questions=6, case_pool="hard", patient_recall=0.35, show_candidates=False,
        description="6 questions, misleading cases only, patient unsure 35% of the time, no candidate list.",
    ),
}


def truth_stats(patient: Patient) -> tuple[int | None, float]:
    """(rank of the true condition in the reference differential, its probability)."""
    for i, (name, p) in enumerate(patient.differential, 1):
        if name == patient.pathology:
            return i, p
    return None, 0.0


def is_hard_case(patient: Patient) -> bool:
    rank, p = truth_stats(patient)
    return rank != 1 and p < 0.25


def eligible(ds: Dataset, d: Difficulty) -> list[Patient]:
    if d.case_pool == "hard":
        return [p for p in ds.patients if is_hard_case(p)]
    return ds.patients


def unsure(case_id: str, code: str, p: float) -> bool:
    """Deterministic per (case, question), so a replay reproduces the same hesitations."""
    if p <= 0:
        return False
    h = hashlib.sha256(f"{case_id}:{code}".encode()).digest()
    return int.from_bytes(h[:4], "big") / 2**32 < p


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def normalise_condition(name: str | None, ds: Dataset) -> str | None:
    """Map a free-text condition name onto the dataset's spelling, or None."""
    if not name:
        return None
    if name in ds.conditions:
        return name
    wanted = _norm(name)
    by_norm = {_norm(c): c for c in ds.conditions}
    if wanted in by_norm:
        return by_norm[wanted]
    for n, c in by_norm.items():
        if wanted and (wanted in n or n in wanted):
            return c
    close = difflib.get_close_matches(wanted, list(by_norm), n=1, cutoff=0.85)
    return by_norm[close[0]] if close else None
