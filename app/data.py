"""DDXPlus loading and code-to-English rendering.

DDXPlus encodes everything as opaque codes (``E_54`` for an evidence,
``E_54_@_V_161`` for an evidence with a value). Nothing outside this module
should ever see a code without the English text next to it.
"""
from __future__ import annotations

import ast
import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Default values DDXPlus uses for "the patient does not have this".
_DEFAULT_TEXT = {"NA": "Not applicable", "N": "No", "0": "0 (none)"}


@dataclass(frozen=True)
class Evidence:
    code: str
    question: str
    is_antecedent: bool
    data_type: str  # B binary, C categorical, M multi-choice
    default_value: str
    values: dict[str, str]  # value code -> English meaning

    @property
    def kind(self) -> str:
        return "history" if self.is_antecedent else "symptom"

    def value_text(self, value: str) -> str:
        text = self.values.get(value, value)
        return _DEFAULT_TEXT.get(text, text)


@dataclass(frozen=True)
class Condition:
    name: str
    icd10: str
    severity: int  # 1 is the most severe in DDXPlus
    symptoms: frozenset[str]
    antecedents: frozenset[str]

    @property
    def clue_codes(self) -> frozenset[str]:
        return self.symptoms | self.antecedents


@dataclass(frozen=True)
class Patient:
    age: int
    sex: str
    pathology: str
    evidences: tuple[str, ...]
    initial_evidence: str
    differential: tuple[tuple[str, float], ...]

    @property
    def evidence_codes(self) -> frozenset[str]:
        return frozenset(split_item(item)[0] for item in self.evidences)


_PAST = {
    "lose": "lost", "have": "had", "feel": "felt", "notice": "noticed", "gain": "gained",
    "take": "took", "see": "saw", "get": "got", "throw": "threw", "turn": "turned",
}
# Order matters: the earlier, more specific openers win.
_OPENERS: tuple[tuple[str, str], ...] = (
    (r"^do you have (.*)", r"I have \1"),
    (r"^do you feel (.*)", r"I feel \1"),
    (r"^do you (.*)", r"I \1"),
    (r"^have you noticed (.*)", r"I've noticed \1"),
    (r"^have you had (.*)", r"I've had \1"),
    (r"^have you been (.*)", r"I've been \1"),
    (r"^have you recently (.*)", r"I've recently \1"),
    (r"^have you lost (.*)", r"I've lost \1"),
    (r"^have you gained (.*)", r"I've gained \1"),
    (r"^have you (.*)", r"I have \1"),
    (r"^are you (.*)", r"I am \1"),
    (r"^are your (\w+) (.*)", r"my \1 are \2"),
    (r"^is your (\w+) (.*)", r"my \1 is \2"),
    (r"^were you (.*)", r"I was \1"),
    (r"^did your (\w+) (\w+) (.*)", r"my \1 \2 \3"),
)
_SPECIAL = {
    "Do you have pain somewhere, related to your reason for consulting?": "I'm in pain, and that's why I'm here.",
    "Is your nose or the back of your throat itchy?": "My nose or the back of my throat is itchy.",
    "Did you previously, or do you currently, have any weakness/paralysis in one or more of your limbs or in your face?": "I have, or have had, weakness or paralysis in a limb or in my face.",
    "Do you currently, or did you ever, have numbness, loss of sensitivity or tingling anywhere on your body?": "I have, or have had, numbness, loss of sensitivity or tingling somewhere on my body.",
    "Are you more irritable or has your mood been very unstable recently?": "I am more irritable, and my mood has been very unstable recently.",
    "Did your cheeks suddenly turn red?": "My cheeks suddenly turned red.",
}


def as_complaint(question: str, answer: str, data_type: str = "B") -> str:
    """Turn a DDXPlus yes/no question into what the patient would say on arrival.

    'Have you noticed a high pitched sound when breathing in?' becomes
    'I've noticed a high pitched sound when breathing in.' Categorical
    questions keep their value: 'I feel pain somewhere: lower chest.'
    """
    import re

    if question in _SPECIAL and data_type == "B":
        return _SPECIAL[question]
    text = question.strip().rstrip("?").strip()
    stem = None
    m = re.match(r"^did you (\w+) (.*)", text, flags=re.IGNORECASE)
    if m:
        stem = f"I {_PAST.get(m.group(1).lower(), 'did ' + m.group(1))} {m.group(2)}"
    else:
        for pattern, repl in _OPENERS:
            if re.match(pattern, text, flags=re.IGNORECASE):
                stem = re.sub(pattern, repl, text, count=1, flags=re.IGNORECASE)
                break
    if stem is None:
        stem = text
    stem = re.sub(r"\byourself\b", "myself", stem)
    stem = re.sub(r"\byour\b", "my", stem)
    stem = re.sub(r"\byou are\b", "I am", stem)
    stem = re.sub(r"\byou\b", "I", stem)
    # Compound questions ("... or do you feel ...") keep a second auxiliary verb.
    stem = re.sub(r"\bor do I\b", "or I", stem)
    stem = re.sub(r"\bor did I\b", "or I", stem)
    stem = re.sub(r"\bor are I\b", "or I am", stem)
    stem = re.sub(r"\bor have I\b", "or I have", stem)
    stem = re.sub(r"^did I ", "I ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\b(keeping|keep|stop|prevent|make|makes|made|bother|bothers) I\b", r"\1 me", stem)
    stem = re.sub(r"^(I have|I've noticed) any ", r"\1 ", stem)
    stem = stem[0].upper() + stem[1:]
    if data_type != "B":
        return f"{stem}: {answer}."
    return stem + "."


def split_item(item: str) -> tuple[str, str | None]:
    """``E_54_@_V_161`` -> (``E_54``, ``V_161``); ``E_12`` -> (``E_12``, None)."""
    code, sep, value = item.partition("_@_")
    return code, (value if sep else None)


class Dataset:
    def __init__(
        self,
        evidences: dict[str, Evidence],
        conditions: dict[str, Condition],
        patients: list[Patient],
    ) -> None:
        self.evidences = evidences
        self.conditions = conditions
        self.patients = patients

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR, limit: int | None = None) -> "Dataset":
        evidences = {
            code: Evidence(
                code=code,
                question=raw["question_en"],
                is_antecedent=bool(raw["is_antecedent"]),
                data_type=raw["data_type"],
                default_value=str(raw["default_value"]),
                values={
                    str(v): meaning["en"] for v, meaning in raw["value_meaning"].items()
                },
            )
            for code, raw in json.loads(
                (data_dir / "release_evidences.json").read_text()
            ).items()
        }
        conditions = {
            name: Condition(
                name=name,
                icd10=raw["icd10-id"],
                severity=int(raw["severity"]),
                symptoms=frozenset(raw["symptoms"]),
                antecedents=frozenset(raw["antecedents"]),
            )
            for name, raw in json.loads(
                (data_dir / "release_conditions.json").read_text()
            ).items()
        }
        patients: list[Patient] = []
        with (data_dir / "release_test_patients.csv").open(newline="") as fh:
            for row in csv.DictReader(fh):
                patients.append(
                    Patient(
                        age=int(row["AGE"]),
                        sex=row["SEX"],
                        pathology=row["PATHOLOGY"],
                        evidences=tuple(ast.literal_eval(row["EVIDENCES"])),
                        initial_evidence=row["INITIAL_EVIDENCE"],
                        differential=tuple(
                            (name, float(p))
                            for name, p in ast.literal_eval(row["DIFFERENTIAL_DIAGNOSIS"])
                        ),
                    )
                )
                if limit is not None and len(patients) >= limit:
                    break
        return cls(evidences, conditions, patients)

    def describe(self, item: str) -> tuple[str, str]:
        """Render one patient evidence item as (question, answer) in English."""
        code, value = split_item(item)
        ev = self.evidences[code]
        if value is None:
            return ev.question, "Yes"
        return ev.question, ev.value_text(value)

    def answer(self, patient: Patient, code: str) -> str:
        """What the patient says when asked question ``code``.

        Binary: yes if present. Categorical and multi-choice: the value(s) the
        patient carries, otherwise the DDXPlus default for that question.
        """
        ev = self.evidences[code]
        values = [
            v for item in patient.evidences for c, v in [split_item(item)] if c == code
        ]
        if ev.data_type == "B":
            return "Yes" if values else "No"
        if not values:
            return ev.value_text(ev.default_value)
        return ", ".join(ev.value_text(v) for v in values if v is not None)

    def random_patient(self, rng: random.Random) -> Patient:
        return rng.choice(self.patients)

    @property
    def candidate_conditions(self) -> list[str]:
        return sorted(self.conditions)
