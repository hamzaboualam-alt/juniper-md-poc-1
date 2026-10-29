"""Claude plays the doctor: one structured decision per call, for a single
case or for a whole clinic day."""
from __future__ import annotations

import os
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field

from .elim import ElimCase
from .shift import Shift
from .worlds import World

DEFAULT_MODEL = os.environ.get("DOCTOR_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("DOCTOR_EFFORT", "medium")


class DoctorAction(BaseModel):
    action: Literal["history_exam", "propose", "order", "eliminate", "escalate", "diagnose", "undeterminable", "see_patient", "end_day"]
    test: str | None = Field(default=None, description="For 'order': the test id from the menu.")
    hypotheses: list[str] = Field(default_factory=list, description="For 'propose': the conditions you are considering, each named in plain clinical terms.")
    hypothesis: str | None = Field(default=None, description="For 'eliminate' or 'diagnose': the condition, named as you proposed it.")
    cited: list[str] = Field(default_factory=list, description="For 'eliminate': the ids of the tests whose results justify crossing it off.")
    case_id: str | None = Field(default=None, description="For 'see_patient': the waiting-room id.")
    rationale: str = Field(description="One short sentence a non-doctor can follow: the headline of your reasoning.")


class DoctorUnavailable(RuntimeError):
    pass


SYSTEM = (
    "You are the emergency physician. A patient arrives with a complaint; you take the history, decide "
    "what could be going on, order tests from the menu (each costs money and minutes), cross conditions "
    "off as results come back, and commit to one diagnosis. Nobody hands you a list of conditions: the "
    "differential is yours to build, and it is graded.\n\n"
    "Actions:\n"
    "- 'history_exam': take the history and examine the patient. Do this first; the bedside scores need it.\n"
    "- 'propose': name the conditions you are considering, in plain clinical terms (for example "
    "'pulmonary embolism', 'aortic dissection'). Propose your differential before ordering paid tests; "
    "you can add to it later.\n"
    "- 'order': one test from the menu, by id.\n"
    "- 'eliminate': cross one condition off, citing the test ids whose results justify it.\n"
    "- 'escalate': call the emergency team. Do it before paid tests when the patient is unstable "
    "(hypotension, ongoing ischemia, a stroke within the treatment window); escalating a stable patient "
    "counts against you.\n"
    "- 'diagnose': commit to one condition. 'undeterminable' is allowed when the dangerous causes are "
    "excluded and nothing confirms the rest; it scores less than the right answer.\n\n"
    "How you are graded:\n"
    "- The differential: whether the dangerous causes of this presentation came up at all, and whether "
    "they came up before tests were ordered.\n"
    "- Each elimination, against guideline rules: a valid rule with the cited results earns credit; a "
    "shortcut the guidelines warn against (one normal ECG for ACS, a D-dimer at high probability, a chest "
    "film for dissection) counts against you; an elimination with no supporting result counts against you.\n"
    "- Closure: every dangerous cause other than your diagnosis should be eliminated by a valid rule "
    "before you commit, unless a confirming result establishes the diagnosis.\n"
    "- The gate (escalation), test ordering rules the guidelines state, and spend against the cheapest "
    "safe route. Do not order tests that cannot change your differential.\n"
    "- Your rationale is the headline shown to a viewer with no medical background: one plain sentence. "
    "Your full reasoning is shown next to it, so think the decision through."
)

SHIFT_SYSTEM = (
    "\n\nYou are running a clinic day. Each message shows the clock, the time left, the waiting room "
    "(with a triage tag from the nurse) and the patient currently in the room. Test minutes and prices are "
    "real, each outcome is worth money as stated, test spend is subtracted, and patients still waiting when "
    "the day ends cost money, urgent ones much more. With no patient in the room you must 'see_patient' "
    "with a waiting-room id, or 'end_day'. Plan the day: thoroughness on one patient is paid for by the "
    "ones still waiting."
)


def _case_prompt(case: ElimCase) -> str:
    v = case.view()
    d = case.difficulty
    lines = [
        f"Situation: {v['title']}. {v['presentation']}",
        f"Patient: {v['age']} year old {v['sex']}. On arrival they say: \"{v['complaint']}\"",
    ]
    if v["findings"] is not None:
        lines.append("History and examination: " + "; ".join(v["findings"]) + ".")
    else:
        lines.append("History and examination: not taken yet.")
    lines.append("")
    lines.append("Your differential so far:")
    if not v["differential"]:
        lines.append("(nothing proposed yet)")
    for h in v["differential"]:
        lines.append(f"- {h['text']} [{h['status']}]")
    lines.append("")
    lines.append("Test menu (id: title, station, minutes" + (", price" if d.show_prices else "") + "):")
    for t in v["tests"]:
        price = f", ${t['price']:.0f}" if t["price"] is not None else ""
        req = f" (needs {', '.join(t['requires'])} first)" if t["requires"] else ""
        done = " [done]" if t["done"] else ""
        lines.append(f"- {t['id']}: {t['title']}, {t['station']}, {t['minutes']} min{price}{req}{done}")
    lines.append("")
    lines.append("Results so far:")
    if not v["orders"]:
        lines.append("(nothing ordered yet)")
    for o in v["orders"]:
        lines.append(f"- {o['test']}: {o['report']}")
    if v["eliminations"]:
        lines.append("Crossed off: " + "; ".join(f"{e['text']} (citing {', '.join(e['cited']) or 'nothing'})" for e in v["eliminations"]))
    if v["escalated"]:
        lines.append("Escalated: yes.")
    if v["spend"] is not None:
        lines.append(f"Spend so far: ${v['spend']:.0f}" + (f" of a budget of ${v['budget_usd']:.0f}" if v["budget_usd"] else "") + f". Minutes: {v['minutes']}.")
    return "\n".join(lines)


def _shift_prompt(shift: Shift) -> str:
    r = shift.rules
    v = shift.view()
    lines = [
        f"Clock: {v['clock_text']} (day ends {v['day_end_text']}, {v['time_left']} minutes left).",
        f"Worth: correct diagnosis +{r.fee_correct}, referral +{r.fee_referred}, wrong -{r.penalty_wrong} (urgent -{r.penalty_wrong_urgent}), "
        f"not seen by the end -{r.penalty_unseen} (urgent -{r.penalty_unseen_urgent}); test spend is subtracted. Calling a patient in takes {r.minutes_per_handover} min.",
        f"Earnings so far: {v['earnings']:+.0f}. Seen: {v['seen']} of {len(v['waiting_room'])}.",
        "",
        "Waiting room:",
    ]
    waiting = [w for w in v["waiting_room"] if w["status"] == "waiting"]
    if not waiting:
        lines.append("(empty)")
    for w in waiting:
        lines.append(f"- id {w['case_id']} | {w['triage'].upper()} | {w['age']} year old {w['sex']} | {w['situation']} | \"{w['complaint']}\"")
    lines.append("")
    if shift.current:
        lines.append(_case_prompt(shift.cases[shift.current]))
        lines.append("")
        lines.append("Decide your next action for the patient in the room.")
    else:
        lines.append("No patient is in the room. Decide: see_patient (with an id from the waiting room) or end_day.")
    return "\n".join(lines)


# Claude list prices, USD per million tokens, keyed by model id.
PRICES = {
    "claude-opus-5-5": {"input_tokens": 4.0, "output_tokens": 20.0, "cache_read_input_tokens": 0.20, "cache_creation_input_tokens": 5.0},
    "claude-sonnet-5-5": {"input_tokens": 2.0, "output_tokens": 10.0, "cache_read_input_tokens": 0.20, "cache_creation_input_tokens": 2.5},
    "claude-haiku-5-5": {"input_tokens": 0.10, "output_tokens": 0.50, "cache_read_input_tokens": 0.01, "cache_creation_input_tokens": 0.125},
}


class ClaudeDoctor:
    name = "claude"

    def __init__(self, worlds: dict[str, World], model: str = DEFAULT_MODEL) -> None:
        self.worlds = worlds
        self.model = model
        self._client = anthropic.Anthropic()
        if not (self._client.api_key or self._client.auth_token or self._client.credentials):
            raise DoctorUnavailable("No Anthropic credentials found. Export ANTHROPIC_API_KEY and restart the server.")
        self.last_usage: dict[str, int] = {}
        self.last_thinking: str = ""

    @property
    def label(self) -> str:
        return f"claude · {self.model}"

    def decide(self, case: ElimCase) -> dict[str, Any]:
        a = self._call(SYSTEM, _case_prompt(case) + "\n\nDecide your next action.")
        if a.action in ("see_patient", "end_day"):
            raise DoctorUnavailable(f"Model chose '{a.action}' outside a clinic day.")
        return a.model_dump() | {"thinking": self.last_thinking}

    def decide_shift(self, shift: Shift) -> dict[str, Any]:
        a = self._call(SYSTEM + SHIFT_SYSTEM, _shift_prompt(shift))
        return a.model_dump() | {"thinking": self.last_thinking}

    def _call(self, system: str, user: str) -> DoctorAction:
        try:
            # Thinking is always on for the current models; "summarized" makes the
            # API return a readable summary of it instead of an empty string.
            # On a policy decline the API reroutes to a fallback model itself.
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_format=DoctorAction,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": EFFORT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise DoctorUnavailable("Anthropic rejected the API key.") from exc
        except anthropic.RateLimitError as exc:
            raise DoctorUnavailable("Rate limited by the Anthropic API; try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise DoctorUnavailable(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise DoctorUnavailable("Could not reach the Anthropic API.") from exc
        except (anthropic.AnthropicError, TypeError) as exc:
            raise DoctorUnavailable(f"Anthropic client error: {exc}") from exc
        u = response.usage
        self.last_usage = {
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        }
        self.last_thinking = "\n\n".join(b.thinking for b in response.content if b.type == "thinking" and b.thinking).strip()
        if response.stop_reason == "refusal":
            raise DoctorUnavailable("The model declined this request.")
        if response.stop_reason == "max_tokens":
            raise DoctorUnavailable("The model ran out of output tokens before deciding.")
        action = response.parsed_output
        if action is None:
            raise DoctorUnavailable("The model returned no structured decision.")
        return action
