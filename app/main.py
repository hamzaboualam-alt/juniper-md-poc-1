from __future__ import annotations

import os
import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .baseline import GreedyDoctor
from .data import Dataset
from .difficulty import PRESETS, eligible
from .doctor_llm import ClaudeDoctor, DoctorUnavailable
from .eval import EvalStore, presets, run_eval, summarise
from .game import BudgetExhausted, Case

STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    limit = os.environ.get("DDX_LIMIT")
    app.state.ds = Dataset.load(limit=int(limit) if limit else None)
    app.state.cases = {}
    app.state.doctor = None
    app.state.doctor_error = None
    app.state.baseline = GreedyDoctor(app.state.ds)
    app.state.evals = EvalStore()
    try:
        app.state.doctor = ClaudeDoctor(app.state.ds)
    except DoctorUnavailable as exc:
        app.state.doctor_error = str(exc)
    yield


app = FastAPI(title="DDXPlus diagnosis game POC", lifespan=lifespan)


def _case(case_id: str) -> Case:
    case = app.state.cases.get(case_id)
    if case is None:
        raise HTTPException(404, "unknown case")
    return case


def _preset(name: str):
    if name not in PRESETS:
        raise HTTPException(400, f"unknown preset {name}; one of {', '.join(PRESETS)}")
    return PRESETS[name]


class AskBody(BaseModel):
    code: str


class DiagnoseBody(BaseModel):
    pathology: str | None = None
    differential: list[str] = []
    undeterminable: bool = False


class EvalBody(BaseModel):
    doctor: str = "claude"
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
    ds: Dataset = app.state.ds
    return {
        "patients": len(ds.patients),
        "hard_patients": len(eligible(ds, PRESETS["hard"])),
        "conditions": len(ds.conditions),
        "questions": len(ds.evidences),
        "claude_available": app.state.doctor is not None,
        "claude_error": app.state.doctor_error,
        "presets": presets(),
    }


@app.get("/api/questions")
def questions():
    ds: Dataset = app.state.ds
    return [
        {
            "code": ev.code,
            "question": ev.question,
            "kind": ev.kind,
            "answers": list(ev.values.values()) or (["Yes", "No"] if ev.data_type == "B" else []),
        }
        for ev in ds.evidences.values()
    ]


@app.get("/api/conditions")
def conditions():
    ds: Dataset = app.state.ds
    return [
        {"name": c.name, "icd10": c.icd10, "severity": c.severity}
        for c in sorted(ds.conditions.values(), key=lambda c: c.name)
    ]


@app.post("/api/cases")
def new_case(seed: int | None = None, preset: str = "warmup"):
    ds: Dataset = app.state.ds
    d = _preset(preset)
    rng = random.Random(seed)
    case = Case(ds, rng.choice(eligible(ds, d)), difficulty=d)
    app.state.cases[case.id] = case
    return case.view()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    return _case(case_id).view()


@app.get("/api/cases/{case_id}/truth")
def truth(case_id: str):
    return _case(case_id).truth()


@app.post("/api/cases/{case_id}/ask")
def ask(case_id: str, body: AskBody):
    case = _case(case_id)
    try:
        case.ask(body.code)
    except KeyError:
        raise HTTPException(400, f"unknown question code {body.code}")
    except BudgetExhausted as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return case.view()


@app.post("/api/cases/{case_id}/diagnose")
def diagnose(case_id: str, body: DiagnoseBody):
    case = _case(case_id)
    if not body.undeterminable and not body.pathology:
        raise HTTPException(400, "pick a condition or declare the case undeterminable")
    try:
        case.diagnose(body.pathology, body.differential, body.undeterminable)
    except KeyError:
        raise HTTPException(400, f"unknown condition {body.pathology}")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return case.view()


def _doctor(name: str):
    if name == "baseline":
        return app.state.baseline
    if name == "claude":
        if app.state.doctor is None:
            raise HTTPException(409, app.state.doctor_error or "Claude doctor unavailable")
        return app.state.doctor
    raise HTTPException(400, f"unknown doctor {name}")


@app.post("/api/cases/{case_id}/{doctor}/step")
def doctor_step(case_id: str, doctor: str):
    case = _case(case_id)
    doc = _doctor(doctor)
    if case.result is not None:
        raise HTTPException(409, "case already diagnosed")
    try:
        action = doc.decide(case)
        if action.action == "ask":
            case.ask(action.evidence_code, by=doc.name, rationale=action.rationale)
        else:
            case.diagnose(
                action.pathology,
                list(action.differential or []),
                undeterminable=action.action == "undeterminable",
                by=doc.name,
                rationale=action.rationale,
            )
    except DoctorUnavailable as exc:
        raise HTTPException(502, str(exc))
    except BudgetExhausted as exc:
        raise HTTPException(409, str(exc))
    except KeyError as exc:
        raise HTTPException(502, f"the doctor named something unknown: {exc}")
    return case.view()


@app.post("/api/eval/runs")
def start_eval(body: EvalBody):
    if not 1 <= body.n <= 500:
        raise HTTPException(400, "n must be between 1 and 500")
    doc = _doctor(body.doctor)
    run_id = run_eval(app.state.evals, app.state.ds, doc, _preset(body.preset), body.n, body.seed)
    return {"run_id": run_id}


@app.get("/api/eval/runs")
def list_runs():
    store: EvalStore = app.state.evals
    out = []
    for r in store.runs():
        out.append(r | {"summary": summarise(store.cases(r["id"]))})
    return out


@app.get("/api/eval/runs/{run_id}")
def get_run(run_id: str):
    store: EvalStore = app.state.evals
    run = store.run(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    cases = store.cases(run_id)
    return run | {"summary": summarise(cases), "cases": cases}


app.mount("/static", StaticFiles(directory=STATIC), name="static")
