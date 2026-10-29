"""Difficulty levers for the elimination game. The doctor never sees the
hypothesis board on any preset; the levers hide prices, narrow the case pool
to decoys, cap spend, or put a whole clinic day on the clock. None changes
the answer, so the grader is identical across presets.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ShiftRules:
    """A clinic day: a queue of patients, a clock, and what each outcome is worth.

    Test minutes come from the tests themselves; test spend is subtracted from
    the day's earnings, so thoroughness on one patient is paid for twice: in
    money and in the patients still waiting. Fees are on the hospital-charge
    scale of app/prices.py: the dearest safe route in the pool (aortic
    dissection, stroke in the window) costs about $7,500, so a correct
    diagnosis must be worth more than that or the right call never pays.
    """

    day_minutes: int = 480
    patients: int = 6
    minutes_per_handover: int = 2
    fee_correct: int = 10_000
    fee_referred: int = 2_000  # committed to "cannot determine" with the dangerous causes excluded
    penalty_wrong: int = 10_000
    penalty_wrong_urgent: int = 20_000
    penalty_unseen: int = 2_500
    penalty_unseen_urgent: int = 10_000


@dataclass(frozen=True)
class Difficulty:
    name: str
    # Whether test prices are shown. Hidden, spend is still graded.
    show_prices: bool = True
    # all: every case variant. traps: only variants whose opening picture points
    # at a decoy hypothesis.
    case_pool: str = "all"
    # Situations in play; empty means all five.
    situations: tuple[str, ...] = ()
    # Spend above which the case is closed as over budget (0 = no cap).
    budget_usd: float = 0.0
    shift: ShiftRules | None = None
    description: str = ""

    @property
    def mode(self) -> str:
        return "shift" if self.shift else "case"

    def as_dict(self) -> dict:
        return asdict(self) | {"mode": self.mode}


PRESETS: dict[str, Difficulty] = {
    "standard": Difficulty(
        "standard", description="One patient, any case. Prices shown. The doctor builds the differential from scratch."
    ),
    "traps": Difficulty(
        "traps", case_pool="traps",
        description="One patient, decoy cases only: the opening picture points at the wrong condition.",
    ),
    "blind": Difficulty(
        "blind", show_prices=False, case_pool="traps",
        description="Decoy cases with prices hidden; spend is still graded against the cheapest safe route.",
    ),
    "clinic-day": Difficulty(
        "clinic-day", shift=ShiftRules(),
        description="An 8-hour shift with 6 patients waiting. Test minutes and prices are real; correct +10,000, wrong -10,000 (urgent -20,000), unseen -2,500 (urgent -10,000), spend subtracted.",
    ),
}
