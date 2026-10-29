from __future__ import annotations

import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .baseline import RouteDoctor
from .difficulty import PRESETS
from .doctor_llm import DEFAULT_MODEL, ClaudeDoctor, DoctorUnavailable
from .elim import ElimCase, IllegalMove, eligible, new_case
from .eval import EvalStore, compare, presets, run_eval, summarise
from .shift import Shift, new_shift
from .worlds import load_worlds

STATIC = Path(__file__).resolve().parent.parent / "static"
CLAUDE_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.worlds = load_worlds()
    app.state.cases = {}
    app.state.shifts = {}
    app.state.doctors = {}
    app.state.doctor_error = None
    app.state.baseline = RouteDoctor(app.state.worlds)
    app.state.evals = EvalStore()
    try:
        app.state.doctors[DEFAULT_MODEL] = ClaudeDoctor(app.state.worlds, DEFAULT_MODEL)
    except DoctorUnavailable as exc:
        app.state.doctor_error = str(exc)
    yield


app = FastAPI(title="Diagnosis by elimination POC", lifespan=lifespan)


def _case(case_id: str) -> ElimCase:
    case = app.state.cases.get(case_id)
    if case is None:
        raise HTTPException(404, "unknown case")
    return case


def _shift(shift_id: str) -> Shift:
    shift = app.state.shifts.get(shift_id)
    if shift is None:
        raise HTTPException(404, "unknown shift")
    return shift


def _preset(name: str):
    if name not in PRESETS:
        raise HTTPException(400, f"unknown preset {name}; one of {', '.join(PRESETS)}")
    return PRESETS[name]


def _doctor(name: str, model: str | None = None):
    if name == "baseline":
        return app.state.baseline
    if name == "claude":
        model = model or DEFAULT_MODEL
        if model not in app.state.doctors:
            if app.state.doctor_error:
                raise HTTPException(409, app.state.doctor_error)
            try:
                app.state.doctors[model] = ClaudeDoctor(app.state.worlds, model)
            except DoctorUnavailable as exc:
                raise HTTPException(409, str(exc))
        return app.state.doctors[model]
    raise HTTPException(400, f"unknown doctor {name}")


class ActionBody(BaseModel):
    action: str
    test: str | None = None
    hypothesis: str | None = None
    hypotheses: list[str] = []
    cited: list[str] = []
    case_id: str | None = None
    rationale: str = ""
    thinking: str = ""


class EvalBody(BaseModel):
    doctor: str = "claude"
    model: str | None = None
    preset: str = "standard"
    n: int = 20
    seed: int | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/eval")
def eval_page():
    return FileResponse(STATIC / "eval.html")


@app.get("/api/meta")
def meta():
    worlds = app.state.worlds
    return {
        "situations": [
            {"id": w.situation, "title": w.title, "hypotheses": len(w.hypotheses), "must_not_miss": len(w.must_not_miss()),
             "tests": len(w.tests), "cases": len(w.cases), "traps": sum(1 for c in w.cases if c.decoy)}
            for w in worlds.values()
        ],
        "cases": sum(len(w.cases) for w in worlds.values()),
        "claude_available": app.state.doctor_error is None,
        "claude_error": app.state.doctor_error,
        "claude_models": CLAUDE_MODELS,
        "default_model": DEFAULT_MODEL,
        "presets": presets(),
    }


# ---- single cases -----------------------------------------------------------


@app.post("/api/cases")
def new_case_route(seed: int | None = None, preset: str = "standard", situation: str | None = None, template: str | None = None):
    d = _preset(preset)
    if d.shift:
        raise HTTPException(400, f"{preset} is a clinic-day preset; use /api/shifts")
    worlds = app.state.worlds
    if template:
        hit = [(w, c) for w in worlds.values() for c in w.cases if c.id == template]
        if not hit:
            raise HTTPException(400, f"unknown case template {template}")
        case = ElimCase(*hit[0], difficulty=d)
    else:
        pool = [(w, c) for w, c in eligible(worlds, d) if situation is None or w.situation == situation]
        if not pool:
            raise HTTPException(400, "no case matches that situation and preset")
        w, c = random.Random(seed).choice(pool)
        case = ElimCase(w, c, difficulty=d)
    app.state.cases[case.id] = case
    return case.view()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    return _case(case_id).view()


@app.get("/api/cases/{case_id}/truth")
def truth(case_id: str):
    return _case(case_id).truth()


def _apply(target: Any, body: ActionBody, by: str = "human") -> None:
    try:
        target.apply(body.model_dump() | {"by": by})
    except IllegalMove as exc:
        raise HTTPException(409, str(exc))
    except KeyError as exc:
        raise HTTPException(400, f"missing field for this action: {exc}")


@app.post("/api/cases/{case_id}/act")
def case_act(case_id: str, body: ActionBody):
    case = _case(case_id)
    _apply(case, body)
    return case.view()


@app.post("/api/cases/{case_id}/{doctor}/step")
def doctor_step(case_id: str, doctor: str, model: str | None = None):
    case = _case(case_id)
    doc = _doctor(doctor, model)
    if case.result is not None:
        raise HTTPException(409, "case already closed")
    try:
        action = doc.decide(case)
        case.apply(action | {"by": doc.name})
    except DoctorUnavailable as exc:
        raise HTTPException(502, str(exc))
    except IllegalMove as exc:
        raise HTTPException(409, f"the doctor tried an illegal move: {exc}")
    return case.view()


# ---- clinic days ------------------------------------------------------------


@app.post("/api/shifts")
def new_shift_route(seed: int | None = None, preset: str = "clinic-day"):
    d = _preset(preset)
    if not d.shift:
        raise HTTPException(400, f"{preset} is a single-case preset; use /api/cases")
    shift = new_shift(app.state.worlds, d, random.Random(seed))
    app.state.shifts[shift.id] = shift
    for cid, case in shift.cases.items():
        app.state.cases[cid] = case
    return shift.view()


@app.get("/api/shifts/{shift_id}")
def get_shift(shift_id: str):
    return _shift(shift_id).view()


@app.post("/api/shifts/{shift_id}/act")
def shift_act(shift_id: str, body: ActionBody):
    shift = _shift(shift_id)
    _apply(shift, body)
    return shift.view()


@app.post("/api/shifts/{shift_id}/{doctor}/step")
def shift_step(shift_id: str, doctor: str, model: str | None = None):
    shift = _shift(shift_id)
    doc = _doctor(doctor, model)
    if shift.result is not None:
        raise HTTPException(409, "the day is over")
    try:
        action = doc.decide_shift(shift)
        shift.apply(action | {"by": doc.name})
    except DoctorUnavailable as exc:
        raise HTTPException(502, str(exc))
    except IllegalMove as exc:
        raise HTTPException(409, f"the doctor tried an illegal move: {exc}")
    return shift.view()


# ---- evaluation -------------------------------------------------------------


@app.post("/api/eval/runs")
def start_eval(body: EvalBody):
    if not 1 <= body.n <= 500:
        raise HTTPException(400, "n must be between 1 and 500")
    doc = _doctor(body.doctor, body.model)
    run_id = run_eval(app.state.evals, app.state.worlds, doc, _preset(body.preset), body.n, body.seed)
    return {"run_id": run_id}


@app.get("/api/eval/runs")
def list_runs():
    store: EvalStore = app.state.evals
    return [r | {"summary": summarise(store.cases(r["id"]))} for r in store.runs()]


@app.get("/api/eval/runs/{run_id}")
def get_run(run_id: str):
    store: EvalStore = app.state.evals
    run = store.run(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    cases = store.cases(run_id)
    return run | {"summary": summarise(cases), "cases": cases}


@app.get("/api/eval/compare")
def compare_runs(a: str, b: str):
    store: EvalStore = app.state.evals
    ra, rb = store.run(a), store.run(b)
    if ra is None or rb is None:
        raise HTTPException(404, "unknown run")
    return compare(ra | {"summary": summarise(store.cases(a))}, rb | {"summary": summarise(store.cases(b))})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
