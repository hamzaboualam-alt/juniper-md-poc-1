"""Run a doctor over many cases and keep every trajectory, so the dashboard can
aggregate accuracy, process metrics and cost per run.
"""
from __future__ import annotations

import json
import random
import sqlite3
import threading
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .data import Dataset
from .difficulty import PRESETS, Difficulty, eligible
from .game import BudgetExhausted, Case

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "evals.sqlite"

# Claude Opus 5.5 list prices, USD per million tokens.
PRICE = {"input_tokens": 4.0, "output_tokens": 20.0, "cache_read_input_tokens": 0.20, "cache_creation_input_tokens": 5.0}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute(
        "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, started REAL, finished REAL, "
        "doctor TEXT, preset TEXT, config TEXT, n INTEGER, done INTEGER, status TEXT, error TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS cases (run_id TEXT, idx INTEGER, data TEXT, PRIMARY KEY (run_id, idx))"
    )
    return con


class EvalStore:
    def __init__(self) -> None:
        self.con = _connect()
        self.lock = threading.Lock()

    def create_run(self, doctor: str, d: Difficulty, n: int) -> str:
        run_id = uuid.uuid4().hex[:8]
        with self.lock:
            self.con.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, time.time(), None, doctor, d.name, json.dumps(d.as_dict()), n, 0, "running", None),
            )
            self.con.commit()
        return run_id

    def add_case(self, run_id: str, idx: int, data: dict[str, Any]) -> None:
        with self.lock:
            self.con.execute("INSERT OR REPLACE INTO cases VALUES (?,?,?)", (run_id, idx, json.dumps(data)))
            self.con.execute("UPDATE runs SET done = done + 1 WHERE id = ?", (run_id,))
            self.con.commit()

    def finish(self, run_id: str, status: str, error: str | None = None) -> None:
        with self.lock:
            self.con.execute(
                "UPDATE runs SET finished = ?, status = ?, error = ? WHERE id = ?",
                (time.time(), status, error, run_id),
            )
            self.con.commit()

    def runs(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.con.execute(
                "SELECT id, started, finished, doctor, preset, config, n, done, status, error FROM runs ORDER BY started DESC"
            ).fetchall()
        return [
            dict(zip(["id", "started", "finished", "doctor", "preset", "config", "n", "done", "status", "error"], r))
            | {"config": json.loads(r[5])}
            for r in rows
        ]

    def run(self, run_id: str) -> dict[str, Any] | None:
        return next((r for r in self.runs() if r["id"] == run_id), None)

    def cases(self, run_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.con.execute(
                "SELECT data FROM cases WHERE run_id = ? ORDER BY idx", (run_id,)
            ).fetchall()
        return [json.loads(r[0]) for r in rows]


def play_case(case: Case, doctor: Any) -> dict[str, Any]:
    """Drive one case to a verdict. Returns the case record for storage."""
    usage: Counter = Counter()
    t0 = time.time()
    error = None
    while case.result is None:
        try:
            action = doctor.decide(case)
        except Exception as exc:  # the run must survive one bad call
            error = str(exc)
            case.diagnose(None, [], undeterminable=True, by=doctor.name, rationale=f"doctor error: {exc}", timed_out=True)
            break
        usage.update(getattr(doctor, "last_usage", {}) or {})
        try:
            if action.action == "ask":
                case.ask(action.evidence_code, by=doctor.name, rationale=action.rationale)
            else:
                case.diagnose(
                    action.pathology,
                    list(action.differential or []),
                    undeterminable=action.action == "undeterminable",
                    by=doctor.name,
                    rationale=action.rationale,
                )
        except BudgetExhausted:
            case.diagnose(None, [], undeterminable=True, by=doctor.name, rationale="budget exhausted", timed_out=True)
        except KeyError as exc:
            case.diagnose(None, [], undeterminable=True, by=doctor.name, rationale=f"unknown name {exc}", timed_out=True)
    cost = sum(usage[k] * PRICE.get(k, 0) for k in usage) / 1e6
    return {
        "case_id": case.id,
        "truth": case.truth(),
        "view": case.view(),
        "result": case.result,
        "usage": dict(usage),
        "cost_usd": round(cost, 4),
        "seconds": round(time.time() - t0, 2),
        "error": error,
    }


def run_eval(store: EvalStore, ds: Dataset, doctor: Any, d: Difficulty, n: int, seed: int | None) -> str:
    run_id = store.create_run(doctor.name, d, n)

    def work() -> None:
        try:
            rng = random.Random(seed)
            pool = eligible(ds, d)
            for i in range(n):
                case = Case(ds, rng.choice(pool), difficulty=d)
                store.add_case(run_id, i, play_case(case, doctor))
            store.finish(run_id, "done")
        except Exception as exc:
            store.finish(run_id, "failed", str(exc))

    threading.Thread(target=work, daemon=True).start()
    return run_id


def summarise(cases: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(cases)
    if n == 0:
        return {"n": 0}
    rs = [c["result"] for c in cases]
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
    wrong = [r for r in rs if not r["exact"]]
    by_condition: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "correct": 0})
    confusion: Counter = Counter()
    for r in rs:
        by_condition[r["truth"]]["n"] += 1
        by_condition[r["truth"]]["correct"] += int(r["exact"])
        if not r["exact"]:
            confusion[(r["doctor_pathology"] or ("timed out" if r["timed_out"] else "undetermined"), r["truth"])] += 1
    usage: Counter = Counter()
    for c in cases:
        usage.update(c["usage"])
    return {
        "n": n,
        "top1": mean([float(r["exact"]) for r in rs]),
        "top3": mean([float(r["truth_rank_in_doctor_ddx"] is not None and r["truth_rank_in_doctor_ddx"] <= 3) for r in rs]),
        "mean_rank": mean([r["truth_rank_in_doctor_ddx"] for r in rs if r["truth_rank_in_doctor_ddx"]]),
        "score": mean([r["score"] for r in rs]),
        "questions": mean([r["questions_asked"] for r in rs]),
        "coverage": mean([r["evidence_coverage"] for r in rs]),
        "ddx_overlap": mean([r["ddx_overlap"] for r in rs]),
        "abstain_rate": mean([float(r["undeterminable"] and not r["timed_out"]) for r in rs]),
        "timeout_rate": mean([float(r["timed_out"]) for r in rs]),
        "unrecognised_rate": mean([float(r["unrecognised_name"]) for r in rs]),
        # Premature closure proxy: a wrong commit after using less than half the budget.
        "premature_closure_rate": mean(
            [float((not r["exact"]) and (not r["undeterminable"]) and r["questions_asked"] * 2 < r["questions_budget"]) for r in rs]
        ),
        "repeat_rate": mean([r["repeats"] / max(1, r["questions_asked"]) for r in rs]),
        "unsure_per_case": mean([r["unsure_answers"] for r in rs]),
        "hard_share": mean([float(r["truth_rank_in_reference"] != 1 and r["truth_probability_in_reference"] < 0.25) for r in rs]),
        "accuracy_when_truth_is_ref_top": mean([float(r["exact"]) for r in rs if r["truth_rank_in_reference"] == 1]),
        "accuracy_when_truth_not_ref_top": mean([float(r["exact"]) for r in rs if r["truth_rank_in_reference"] != 1]),
        "errors": sum(1 for c in cases if c["error"]),
        "tokens": dict(usage),
        "cost_usd": round(sum(c["cost_usd"] for c in cases), 4),
        "seconds_per_case": mean([c["seconds"] for c in cases]),
        "by_condition": sorted(
            ({"condition": k, **v, "accuracy": round(v["correct"] / v["n"], 3)} for k, v in by_condition.items()),
            key=lambda x: (x["accuracy"], -x["n"]),
        ),
        "confusion": [{"said": s, "truth": t, "n": k} for (s, t), k in confusion.most_common(12)],
        "wrong_with_few_questions": sum(1 for r in wrong if not r["undeterminable"] and r["questions_asked"] * 2 < r["questions_budget"]),
    }


def presets() -> list[dict[str, Any]]:
    return [p.as_dict() for p in PRESETS.values()]
