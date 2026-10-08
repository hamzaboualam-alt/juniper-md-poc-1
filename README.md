# Diagnosis Room

A sequential-diagnosis game built on DDXPlus, with a human, a rule-based
baseline or Claude playing the doctor, and an evaluation dashboard.

A synthetic patient walks in with one complaint. The doctor asks questions
from a bank of 223, the patient answers from its record, the doctor commits a
diagnosis, and the answer is graded against the label that came with the
patient. No medical knowledge is needed to read the result.

Patients come from [DDXPlus](https://arxiv.org/abs/2205.09148) (English
release, CC-BY): ~134k synthetic patients, 49 conditions, each with its true
condition, its full symptom/history record and a rule-based reference
differential.

## Run

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # once, if uv is missing
uv sync
uv run scripts/fetch_data.py                       # 19 MB from figshare, once
uv run uvicorn app.main:app --reload
```

- Game: http://localhost:8000
- Evaluation dashboard: http://localhost:8000/eval

Set `DDX_LIMIT=5000` to load fewer patients during development.

## Claude as the doctor

Export `ANTHROPIC_API_KEY` before starting the server. The purple buttons and
the "Claude" doctor in the dashboard then work. Model `claude-opus-5-5` by
default (`DOCTOR_MODEL`), effort `medium` (`DOCTOR_EFFORT`).

The rule-based baseline needs no key. It keeps the conditions consistent with
every positive answer and asks the question that splits them most evenly. It
is the floor any model should clear.

## Difficulty presets

Every lever raises the cost of reaching the answer; none changes the answer,
so the grader is the same for every preset.

| Preset | Questions | Case pool | Patient unsure | Candidate list |
|---|---|---|---|---|
| warmup | 20 | any | 0% | shown |
| standard | 12 | any | 0% | shown |
| hard | 8 | misleading | 25% | hidden |
| brutal | 6 | misleading | 35% | hidden |

- **Question budget**: fewer turns to separate the candidates.
- **Misleading cases**: patients whose own reference differential ranks another
  condition first and gives the truth under 25%. About 22% of DDXPlus.
- **Patient unsure**: a share of questions first get "I'm not sure"; asking
  again gets the answer, at the cost of a turn. Deterministic per case.
- **Hidden candidate list**: the doctor must name the condition in free text;
  it is normalised against the 49 names, and an unrecognised name is a miss.

Presets live in `app/difficulty.py`.

## Evaluation

`POST /api/eval/runs {doctor, preset, n, seed}` plays `n` cases in the
background and stores every trajectory in `data/evals.sqlite`. The dashboard
shows per run: top-1 and top-3 accuracy, mean rank of the truth, score,
questions per case, clues uncovered, premature closure (wrong commit before
half the budget), budget exhaustion, abstention, repeated questions,
unrecognised names, accuracy split by easy versus misleading cases, tokens and
cost, accuracy by true condition, the most common confusions, and a
per-case drill-down with the full transcript.

## Tests

```bash
uv run python -m pytest
```
