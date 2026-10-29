"""Run a doctor over many cases or many clinic days and keep every trajectory,
so the dashboard can aggregate the final answers, the elimination process,
spend and cost per run.
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

from .difficulty import PRESETS, Difficulty
from .doctor_llm import PRICES
from .elim import ElimCase, IllegalMove, new_case
from .shift import Shift, new_shift
from .worlds import World

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "evals.sqlite"
FALLBACK_PRICE = PRICES["claude-opus-5-5"]
MAX_STEPS_PER_CASE = 40


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute(
        "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, started REAL, finished REAL, "
        "doctor TEXT, preset TEXT, config TEXT, n INTEGER, done INTEGER, status TEXT, error TEXT)"
    )
    con.execute("CREATE TABLE IF NOT EXISTS cases (run_id TEXT, idx INTEGER, data TEXT, PRIMARY KEY (run_id, idx))")
    return con


class EvalStore:
    def __init__(self) -> None:
        self.con = _connect()
        self.lock = threading.Lock()

    def create_run(self, doctor: str, config: dict[str, Any], preset: str, n: int) -> str:
        run_id = uuid.uuid4().hex[:8]
        with self.lock:
            self.con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (run_id, time.time(), None, doctor, preset, json.dumps(config), n, 0, "running", None))
            self.con.commit()
        return run_id

    def add_case(self, run_id: str, idx: int, data: dict[str, Any]) -> None:
        with self.lock:
            self.con.execute("INSERT OR REPLACE INTO cases VALUES (?,?,?)", (run_id, idx, json.dumps(data)))
            self.con.execute("UPDATE runs SET done = done + 1 WHERE id = ?", (run_id,))
            self.con.commit()

    def finish(self, run_id: str, status: str, error: str | None = None) -> None:
        with self.lock:
            self.con.execute("UPDATE runs SET finished = ?, status = ?, error = ? WHERE id = ?", (time.time(), status, error, run_id))
            self.con.commit()

    def runs(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.con.execute("SELECT id, started, finished, doctor, preset, config, n, done, status, error FROM runs ORDER BY started DESC").fetchall()
        out = []
        for r in rows:
            d = dict(zip(["id", "started", "finished", "doctor", "preset", "config", "n", "done", "status", "error"], r))
            d["config"] = json.loads(r[5])
            d["model"] = d["config"].get("model") or ("rule-based" if d["doctor"] == "baseline" else "claude-opus-5-5")
            d["mode"] = d["config"].get("mode", "case")
            d["engine"] = d["config"].get("engine", "ddxplus")
            out.append(d)
        return [r for r in out if r["engine"] == "elimination-v2"]

    def run(self, run_id: str) -> dict[str, Any] | None:
        return next((r for r in self.runs() if r["id"] == run_id), None)

    def cases(self, run_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.con.execute("SELECT data FROM cases WHERE run_id = ? ORDER BY idx", (run_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]


def _cost(usage: Counter, model: str) -> float:
    price = PRICES.get(model, FALLBACK_PRICE)
    return sum(usage[k] * price.get(k, 0) for k in usage) / 1e6


def _case_record(case: ElimCase) -> dict[str, Any]:
    return {"case_id": case.id, "truth": case.truth(), "view": case.view(), "result": case.result, "actions": case.actions}


def _with_by(action: dict[str, Any], doctor: Any) -> dict[str, Any]:
    return action | {"by": doctor.name}


def play_case(case: ElimCase, doctor: Any) -> dict[str, Any]:
    usage: Counter = Counter()
    t0 = time.time()
    error = None
    steps = 0
    while case.result is None and steps < MAX_STEPS_PER_CASE:
        steps += 1
        try:
            action = doctor.decide(case)
        except Exception as exc:  # the run must survive one bad call
            error = str(exc)
            case._close(None, [], by=doctor.name, rationale=f"doctor error: {exc}", timed_out=True)
            break
        usage.update(getattr(doctor, "last_usage", {}) or {})
        try:
            case.apply(_with_by(action, doctor))
        except IllegalMove as exc:
            case.actions.append({"kind": "illegal", "by": doctor.name, "rationale": action.get("rationale", ""), "error": str(exc), "at_minute": case.minutes, "spend": case.spend, "attempted": action})
    if case.result is None:
        case._close(None, [], by=doctor.name, rationale="step limit reached without a diagnosis", timed_out=True)
    return _case_record(case) | {
        "usage": dict(usage), "cost_usd": round(_cost(usage, getattr(doctor, "model", "")), 4),
        "seconds": round(time.time() - t0, 2), "error": error,
        "illegal_moves": sum(1 for a in case.actions if a["kind"] == "illegal"),
    }


def play_shift(shift: Shift, doctor: Any) -> dict[str, Any]:
    usage: Counter = Counter()
    t0 = time.time()
    error = None
    steps = 0
    illegal = 0
    while shift.result is None and steps < 400:
        steps += 1
        try:
            action = doctor.decide_shift(shift)
        except Exception as exc:
            error = str(exc)
            shift.end_day(by=doctor.name)
            break
        usage.update(getattr(doctor, "last_usage", {}) or {})
        try:
            shift.apply(_with_by(action, doctor))
        except IllegalMove as exc:
            illegal += 1
            if illegal > 10:
                error = f"too many illegal moves, last: {exc}"
                shift.end_day(by=doctor.name)
    if shift.result is None:
        shift.end_day(by=doctor.name)
    return {
        "shift_id": shift.id, "shift": shift.result, "view": shift.view(),
        "cases": [_case_record(shift.cases[cid]) for cid in shift.order],
        "usage": dict(usage), "cost_usd": round(_cost(usage, getattr(doctor, "model", "")), 4),
        "seconds": round(time.time() - t0, 2), "error": error, "illegal_moves": illegal,
    }


def run_eval(store: EvalStore, worlds: dict[str, World], doctor: Any, d: Difficulty, n: int, seed: int | None) -> str:
    config = d.as_dict() | {"model": getattr(doctor, "model", None), "seed": seed, "engine": "elimination-v2"}
    run_id = store.create_run(doctor.name, config, d.name, n)

    def work() -> None:
        try:
            rng = random.Random(seed)
            for i in range(n):
                if d.shift:
                    store.add_case(run_id, i, play_shift(new_shift(worlds, d, rng), doctor))
                else:
                    store.add_case(run_id, i, play_case(new_case(worlds, d, rng), doctor))
            store.finish(run_id, "done")
        except Exception as exc:
            store.finish(run_id, "failed", str(exc))

    threading.Thread(target=work, daemon=True).start()
    return run_id


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None


def summarise_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(cases)
    if n == 0:
        return {"n": 0}
    rs = [c["result"] for c in cases]
    by_situation: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "correct": 0, "safe": 0})
    by_tempt: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "correct": 0, "safe": 0})
    confusion: Counter = Counter()
    for r in rs:
        for key, bucket in ((r["situation"], by_situation), (r["tempts"], by_tempt)):
            bucket[key]["n"] += 1
            bucket[key]["correct"] += int(r["exact"])
            bucket[key]["safe"] += int(r["exact"] and r["safe_closure"] and not r["unsafe_eliminations"])
        if not r["exact"]:
            confusion[(r["doctor_name"], r["truth_name"])] += 1
    unstable = [r for r in rs if r["unstable"]]
    with_mnm = [r for r in rs if r["mnm_total"]]
    return {
        "n": n,
        "top1": _mean([float(r["exact"]) for r in rs]),
        "clean": _mean([float(r["exact"] and r["safe_closure"] and not r["unsafe_eliminations"]) for r in rs]),
        "safe_closure": _mean([float(r["safe_closure"]) for r in rs]),
        "score": _mean([r["score"] for r in rs]),
        "process_score": _mean([r["process_score"] for r in rs]),
        "outcome_score": _mean([r["outcome_score"] for r in rs]),
        "missed_dangerous_rate": _mean([float(r["missed_dangerous"]) for r in rs]),
        # The differential the doctor built, against the hidden board.
        "hypotheses_per_case": _mean([r["proposed_count"] for r in rs]),
        "differential_recall": _mean([r["differential_recall"] for r in rs]),
        "truth_considered_rate": _mean([float(r["truth_considered"]) for r in rs]),
        "never_considered_rate": _mean([float(bool(r["never_considered"])) for r in rs]),
        "off_board_per_case": _mean([len(r["off_board"]) for r in rs]),
        "differential_first_rate": _mean([float(r["differential_first"] == "before_tests") for r in rs]),
        "no_differential_rate": _mean([float(r["differential_first"] == "never") for r in rs]),
        "truth_eliminated_rate": _mean([float(r["truth_eliminated"]) for r in rs]),
        "shortcut_rate": _mean([float(any(e["validity"] == "shortcut" for e in r["eliminations"])) for r in rs]),
        "unsupported_rate": _mean([float(any(e["validity"] == "unsupported" for e in r["eliminations"])) for r in rs]),
        "eliminations_per_case": _mean([len(r["eliminations"]) for r in rs]),
        "valid_elimination_share": _mean([sum(e["validity"] == "valid" for e in r["eliminations"]) / len(r["eliminations"]) for r in rs if r["eliminations"]]),
        "mnm_cleared_share": _mean([r["valid_mnm"] / r["mnm_total"] for r in with_mnm]),
        "abstain_rate": _mean([float(r["undeterminable"]) for r in rs]),
        "timeout_rate": _mean([float(r["timed_out"]) for r in rs]),
        "gate_missed_rate": _mean([float(r["gate"] in ("missed", "late")) for r in unstable]) if unstable else None,
        "false_escalation_rate": _mean([float(r["gate"] == "false_alarm") for r in rs]),
        "order_violations_per_case": _mean([len(r["order_violations"]) for r in rs]),
        "unnecessary_tests_per_case": _mean([len(r["unnecessary_tests"]) for r in rs]),
        "tests_per_case": _mean([len(r["tests_ordered"]) for r in rs]),
        "spend": _mean([r["spend"] for r in rs]),
        "reference_cost": _mean([r["reference_cost"] for r in rs]),
        "overspend_ratio": _mean([r["spend"] / r["reference_cost"] for r in rs if r["reference_cost"]]),
        "cost_efficiency": _mean([r["cost_efficiency"] for r in rs]),
        "minutes": _mean([r["minutes"] for r in rs]),
        "illegal_moves_per_case": _mean([c.get("illegal_moves", 0) for c in cases]),
        "by_situation": sorted(({"situation": k, **v, "accuracy": round(v["correct"] / v["n"], 3), "clean_rate": round(v["safe"] / v["n"], 3)} for k, v in by_situation.items()), key=lambda x: x["accuracy"]),
        "by_tempt": sorted(({"tempts": k, **v, "accuracy": round(v["correct"] / v["n"], 3), "clean_rate": round(v["safe"] / v["n"], 3)} for k, v in by_tempt.items()), key=lambda x: (x["clean_rate"], x["accuracy"])),
        "confusion": [{"said": s, "truth": t, "n": k} for (s, t), k in confusion.most_common(12)],
    }


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"n": 0, "mode": "case"}
    usage: Counter = Counter()
    for c in records:
        usage.update(c.get("usage", {}))
    common = {
        "errors": sum(1 for c in records if c.get("error")),
        "tokens": dict(usage),
        "cost_usd": round(sum(c.get("cost_usd", 0) for c in records), 4),
        "seconds_per_rollout": _mean([c.get("seconds", 0) for c in records]),
    }
    if "shift" in records[0]:
        days = [c["shift"] for c in records]
        flat = [case for c in records for case in c["cases"] if case["result"] is not None]
        seen = [case for case in flat if not case["result"]["timed_out"]]
        day = {
            "days": len(days),
            "earnings": _mean([d["earnings"] for d in days]),
            "best_possible": _mean([d["best_possible"] for d in days]),
            "day_score": _mean([d["day_score"] for d in days]),
            "test_spend": _mean([d["spend"] for d in days]),
            "patients_per_day": _mean([d["patients"] for d in days]),
            "seen_per_day": _mean([d["correct"] + d["wrong"] + d["referred"] for d in days]),
            "correct_per_day": _mean([d["correct"] for d in days]),
            "wrong_per_day": _mean([d["wrong"] for d in days]),
            "referred_per_day": _mean([d["referred"] for d in days]),
            "unseen_per_day": _mean([d["unseen"] + d["unfinished"] for d in days]),
            "urgent_unseen_per_day": _mean([d["urgent_unseen"] for d in days]),
            "minutes_used": _mean([d["clock"] for d in days]),
            "ran_out_of_time_rate": _mean([float(d["ended_because"] == "the clock ran out") for d in days]),
        }
        return summarise_cases(seen) | common | {"mode": "shift", "day": day}
    return summarise_cases(records) | common | {"mode": "case"}


COMPARE_ROWS = [
    ("day.day_score", "Day score (0-1)", True),
    ("day.earnings", "Earnings per day", True),
    ("day.test_spend", "Test spend per day", False),
    ("day.seen_per_day", "Patients seen per day", True),
    ("day.correct_per_day", "Correct per day", True),
    ("day.wrong_per_day", "Wrong per day", False),
    ("day.unseen_per_day", "Left unseen per day", False),
    ("day.urgent_unseen_per_day", "Urgent left unseen per day", False),
    ("day.ran_out_of_time_rate", "Days that ran out of time", False),
    ("top1", "Correct diagnosis", True),
    ("clean", "Correct with a clean process", True),
    ("safe_closure", "Dangerous causes excluded before committing", True),
    ("score", "Case score", True),
    ("process_score", "Process score", True),
    ("missed_dangerous_rate", "Must-not-miss condition missed", False),
    ("differential_recall", "Dangerous causes that came up in the differential", True),
    ("truth_considered_rate", "True condition was on the differential", True),
    ("never_considered_rate", "Cases with a dangerous cause never considered", False),
    ("differential_first_rate", "Differential proposed before any paid test", True),
    ("hypotheses_per_case", "Hypotheses proposed per case", None),
    ("off_board_per_case", "Proposals the board does not recognise, per case", None),
    ("shortcut_rate", "Cases with a shortcut elimination", False),
    ("unsupported_rate", "Cases with an unsupported elimination", False),
    ("valid_elimination_share", "Share of eliminations that were valid", True),
    ("gate_missed_rate", "Unstable patients not escalated first", False),
    ("false_escalation_rate", "Stable patients escalated", False),
    ("order_violations_per_case", "Ordering violations per case", False),
    ("unnecessary_tests_per_case", "Unnecessary tests per case", False),
    ("tests_per_case", "Tests per case", None),
    ("spend", "Spend per case (USD)", False),
    ("overspend_ratio", "Spend vs cheapest safe route", False),
    ("abstain_rate", "Declared undeterminable", None),
    ("timeout_rate", "Closed without a diagnosis", False),
    ("illegal_moves_per_case", "Illegal moves per case", False),
    ("errors", "Doctor errors", False),
    ("cost_usd", "Model cost (USD)", False),
    ("seconds_per_rollout", "Seconds per rollout", False),
]


def _dig(d: dict[str, Any], key: str) -> Any:
    for part in key.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for key, label, higher in COMPARE_ROWS:
        va, vb = _dig(a["summary"], key), _dig(b["summary"], key)
        if va is None and vb is None:
            continue
        winner = None
        if higher is not None and va is not None and vb is not None and va != vb:
            winner = "a" if (va > vb) == higher else "b"
        rows.append({"key": key, "label": label, "a": va, "b": vb, "higher_is_better": higher, "winner": winner})
    wins = Counter(r["winner"] for r in rows if r["winner"])
    keys = ("id", "doctor", "model", "preset", "mode", "n", "done", "status", "started")
    return {
        "a": {k: a[k] for k in keys}, "b": {k: b[k] for k in keys}, "rows": rows,
        "wins": {"a": wins.get("a", 0), "b": wins.get("b", 0)},
        "same_preset": a["preset"] == b["preset"],
        "same_seed": a["config"].get("seed") is not None and a["config"].get("seed") == b["config"].get("seed"),
    }


def presets() -> list[dict[str, Any]]:
    return [p.as_dict() for p in PRESETS.values()]
