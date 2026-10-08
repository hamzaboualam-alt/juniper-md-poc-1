"""Claude plays the doctor: one structured decision per call."""
from __future__ import annotations

import os
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .data import Dataset
from .game import UNSURE_ANSWER, Case

MODEL = os.environ.get("DOCTOR_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("DOCTOR_EFFORT", "medium")


class DoctorAction(BaseModel):
    action: Literal["ask", "diagnose", "undeterminable"]
    evidence_code: str | None = Field(
        default=None, description="Required when action is 'ask': the question code, e.g. E_91."
    )
    pathology: str | None = Field(
        default=None, description="Required when action is 'diagnose': the condition's name."
    )
    differential: list[str] = Field(
        default_factory=list,
        description="Up to 4 other candidate conditions, most likely first.",
    )
    rationale: str = Field(description="One short sentence a non-doctor can follow.")


class DoctorUnavailable(RuntimeError):
    pass


def _system_prompt(ds: Dataset, show_candidates: bool) -> str:
    questions = []
    for ev in ds.evidences.values():
        extra = ""
        if ev.values:
            extra = " | answers: " + ", ".join(v for v in ev.values.values())
        questions.append(f"{ev.code} [{ev.kind}] {ev.question}{extra}")
    candidates = (
        "Candidate conditions (spell exactly):\n"
        + "\n".join(f"- {name}" for name in ds.candidate_conditions)
        if show_candidates
        else "The list of possible conditions is not given. Name the condition in ordinary "
        "clinical English (for example 'Pneumonia' or 'Unstable angina')."
    )
    return (
        "You are playing the doctor in a sequential-diagnosis game. A simulated patient has "
        "exactly one condition. Each turn you either ask ONE question from the question bank "
        "(the patient answers truthfully from their record), or you commit to a diagnosis with a "
        "short differential, or you declare the case undeterminable.\n\n"
        "The question budget is stated in each message; when it is spent you must commit. "
        f"If the patient answers '{UNSURE_ANSWER}', asking the same question again gets a real "
        "answer, at the cost of a turn. Prefer the question that best separates the conditions "
        "still consistent with what you know. Do not repeat a question that was answered. "
        "Diagnose as soon as one condition clearly dominates. Your rationale is shown to a viewer "
        "with no medical background: one plain sentence.\n\n"
        f"{candidates}\n\n"
        "Question bank (use the code):\n" + "\n".join(questions)
    )


def _user_prompt(case: Case) -> str:
    view = case.view()
    lines = [
        f"Patient: {view['age']} year old, {view['sex']}.",
        f"The patient says on arrival: \"{view['initial_complaint']['statement']}\" "
        f"(that is the question '{view['initial_complaint']['question']}' answered '{view['initial_complaint']['answer']}').",
        "",
        "Consultation so far:",
    ]
    if not view["transcript"]:
        lines.append("(no questions asked yet)")
    for i, t in enumerate(view["transcript"], 1):
        lines.append(f"{i}. [{t['code']}] {t['question']} -> {t['answer']}")
    budget = view["difficulty"]["max_questions"]
    left = view["questions_left"]
    lines += [
        "",
        f"Questions asked: {len(view['transcript'])} of {budget}. Questions left: {left}.",
        "You must commit now." if left <= 0 else "Decide your next action.",
    ]
    return "\n".join(lines)


class ClaudeDoctor:
    name = "claude"

    def __init__(self, ds: Dataset) -> None:
        self.ds = ds
        self._systems = {
            True: _system_prompt(ds, True),
            False: _system_prompt(ds, False),
        }
        self._client = anthropic.Anthropic()
        if not (self._client.api_key or self._client.auth_token or self._client.credentials):
            raise DoctorUnavailable(
                "No Anthropic credentials found. Export ANTHROPIC_API_KEY and restart the server."
            )
        self.last_usage: dict[str, int] = {}

    def decide(self, case: Case) -> DoctorAction:
        try:
            response = self._client.messages.parse(
                model=MODEL,
                max_tokens=2000,
                system=[
                    {
                        "type": "text",
                        "text": self._systems[case.difficulty.show_candidates],
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": _user_prompt(case)}],
                output_format=DoctorAction,
                output_config={"effort": EFFORT},
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
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        }
        if response.stop_reason == "refusal":
            raise DoctorUnavailable("The model declined this request.")
        action = response.parsed_output
        if action is None:
            raise DoctorUnavailable("The model returned no structured decision.")
        if action.action == "ask" and action.evidence_code not in self.ds.evidences:
            raise DoctorUnavailable(f"Model asked an unknown question code: {action.evidence_code!r}")
        return action
