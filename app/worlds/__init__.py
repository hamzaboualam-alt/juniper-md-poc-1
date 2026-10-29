"""The playable worlds: one per situation of the diagnosis-by-elimination
dataset, each adding what the dataset's prose does not carry: the result a test
returns for each true condition, machine-checkable elimination rules, prices,
and case variants built to tempt a specific mistake.

Every rule names the dataset step or rule it was derived from. A rule marked
``inferred`` is not written as an exclusion rule in any source and is weaker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..prices import PRICES, Price


@dataclass(frozen=True)
class Test:
    id: str
    title: str
    price_key: str
    results: dict[str, str]  # result id -> what the report says
    station: str  # where in the room it happens: desk, bedside, lab, imaging, radiology
    dataset_step: str | None = None  # step id in the dataset, when it maps to one
    requires: tuple[str, ...] = ()  # tests that must be done first (clinical scores need the history)

    @property
    def price(self) -> Price:
        return PRICES[self.price_key]


@dataclass(frozen=True)
class Clause:
    """One way to eliminate a hypothesis: every listed test must have shown the
    listed result (a tuple means any of them), and every listed finding must be
    present in the patient's examination."""

    results: dict[str, str | tuple[str, ...]]
    text: str
    source: str
    findings: tuple[str, ...] = ()
    inferred: bool = False
    # Populations in which the sources say the rule does not hold.
    unless_findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Shortcut:
    """A combination the sources warn against using to eliminate a hypothesis."""

    results: dict[str, str | tuple[str, ...]]
    text: str
    source: str
    findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Hypothesis:
    id: str
    name: str
    tier: str  # must_not_miss | other
    results: dict[str, str]  # test id -> result id this condition produces by default
    eliminate_when: tuple[Clause, ...] = ()
    do_not_rely: tuple[Shortcut, ...] = ()
    confirmed_by: dict[str, str] = field(default_factory=dict)  # test -> result that establishes it
    remainder: bool = False  # the diagnosis of exclusion: never eliminated, it is what is left
    no_rule_note: str = ""


@dataclass(frozen=True)
class CaseTemplate:
    id: str
    truth: str
    age: int
    sex: str  # female | male
    complaint: str  # what the patient says on arrival
    findings: tuple[str, ...]  # what history and examination reveal
    results: dict[str, str] = field(default_factory=dict)  # overrides of the truth's default results
    unstable: bool = False  # the gate: escalate before the work-up
    tempts: str = ""  # the mistake this variant is built to induce
    decoy: str | None = None  # the hypothesis the opening picture points to
    note: str = ""


@dataclass(frozen=True)
class World:
    situation: str
    title: str
    presentation: str  # one line a viewer understands
    tests: dict[str, Test]
    hypotheses: dict[str, Hypothesis]
    cases: tuple[CaseTemplate, ...]
    route: tuple[str, ...]  # the guideline order of tests, the baseline's script
    order_rules: tuple[Any, ...] = ()  # OrderRule entries

    def must_not_miss(self) -> list[str]:
        return [h.id for h in self.hypotheses.values() if h.tier == "must_not_miss"]

    def resolve(self, text: str) -> str | None:
        """Map the doctor's free-text hypothesis to one of this world's ids."""
        from .aliases import resolve

        if text in self.hypotheses:
            return text
        return resolve(self.situation, text)


@dataclass(frozen=True)
class OrderRule:
    """A sequencing constraint the sources state: ordering ``test`` while
    ``unless`` has not been done (or has not shown ``unless_result``) is a
    violation."""

    test: str
    unless: str
    unless_result: str | tuple[str, ...] | None
    text: str
    source: str
    findings: tuple[str, ...] = ()  # only applies when these findings are present


def load_worlds() -> dict[str, World]:
    from . import chest_pain, dyspnea, focal_deficit, headache, lower_abdominal_pain

    worlds = [chest_pain.WORLD, dyspnea.WORLD, lower_abdominal_pain.WORLD, headache.WORLD, focal_deficit.WORLD]
    return {w.situation: w for w in worlds}
