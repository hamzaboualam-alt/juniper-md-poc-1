# Diagnosis Room: diagnosis by elimination

A game in which a doctor, human, rule-based or Claude, works a patient's
differential down to one diagnosis by ordering tests and crossing hypotheses
off with the results that justify it. The grader judges the final answer, the
elimination process against guideline rules, and what the work-up cost.

## Where the medicine comes from

`diagnostic-elimination-dataset/` is a source-linked dataset of how
clinicians eliminate hypotheses for 12 presenting situations (dataset v0.2.0,
assembled from public guidelines; research prototype, not clinical guidance).
It gives, per situation, the hypotheses with a must-not-miss tier, the ordered
work-up steps, what each step does to each hypothesis, the elimination rules,
and the shortcuts the sources warn against.

The five richest situations are playable: acute chest pain, acute shortness of
breath, acute lower abdominal or pelvic pain, acute nontraumatic headache,
and acute focal deficit (suspected stroke). For each, `app/worlds/<situation>.py`
adds what the dataset's prose does not carry:

- the result each test returns for each true condition,
- machine-checkable elimination rules and "do not rely" shortcuts, each naming
  the dataset source it was derived from (`inferred` marks the weaker ones),
- ordering rules the sources state (pregnancy test before CT, CT before LP with
  a deficit, no D-dimer at high probability),
- case variants built to tempt one specific mistake (36 in all, 28 of them with
  a decoy the opening picture points at).

Test prices are hospital gross charges, what a patient without insurance is
billed, taken from published price-transparency lists (`app/prices.py`, with
the source of every figure in its docstring). Cheshire Medical Center's
standard charges are the main source; items it does not list come from other
hospitals or aggregated cash prices and are marked approximate. They run 10
to 30 times above Medicare rates, so a head CT is $3,134 and a CT pulmonary
angiogram $3,266. Minutes are the time until a result is back.

## How a case is graded

The doctor never sees the hypothesis board. They get the complaint, the chart
and a test menu, and must say what could be going on in their own words
(`propose`), order tests, cross conditions off citing results (`eliminate`),
escalate when the patient is unstable, and commit (`diagnose` or
`undeterminable`). The grader maps their wording to the world's hypotheses
(`app/worlds/aliases.py`, longest phrase wins) and scores:

- **Outcome.** Right diagnosis, or "cannot determine" with the dangerous
  causes excluded (partial credit). A diagnosis the board does not recognise is
  a commitment graded wrong, not a rejected move.
- **The differential.** Which must-not-miss conditions came up at all
  (differential recall), whether the true condition was ever on the list, and
  whether the first proposal came before any paid test. A dangerous cause that
  never came up is reported as `never_considered`, which is worse than
  proposed-and-left-open.
- **Eliminations.** Every must-not-miss hypothesis other than the truth must
  be crossed off by a valid rule, citing the results that satisfy it, unless a
  confirming result establishes the diagnosis. An elimination resting on a
  shortcut the sources warn against, or on no result, counts against. So does
  working an unstable patient up instead of escalating, and an ordering
  violation.
- **Cost.** Spend is compared with the cheapest route that safely reaches the
  answer, computed per case by brute force over the test menu.

Process = 0.5 × share of dangerous causes validly eliminated + 0.3 ×
differential recall + 0.2 × timing (1 if the differential came before tests,
0.5 after, 0 never), minus 0.25 per unsafe elimination, 0.25 for a missed
gate and 0.1 per ordering violation. Score = 0.5 × outcome + 0.3 × process +
0.2 × cost efficiency. The grader is identical across presets; presets hide
prices, restrict the case pool to decoys, or put a clinic day on the clock.

## Run

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # once, if uv is missing
uv sync
uv run uvicorn app.main:app --reload
```

- Game: http://localhost:8000. The patient arrives and you pick who takes
  them: Claude, the guideline doctor, or you. With a model doctor the screen
  follows its moves (chart, the differential it builds, each station and
  result, the verdict); the hidden board is revealed only at the verdict.
- Evaluation dashboard: http://localhost:8000/eval

Export `ANTHROPIC_API_KEY` to enable the Claude doctor (`claude-opus-5-5` by
default; `DOCTOR_MODEL`, `DOCTOR_EFFORT`). Each move runs with adaptive thinking
on and `display: "summarized"`, so the model's reasoning summary is captured
with the move and shown next to the one-line rationale: expand "reasoning" in
the event log, the watching strip, and the evaluation drill-down. The rule-based
baseline knows the board: it proposes the full differential, follows the
guideline route and solves every case cleanly. It gives no reasoning. It is the
floor and the proof of solvability.

Clinic-day mode puts six patients from any situation in a waiting room with
an 8-hour clock; test minutes and prices are real, earnings follow the preset's
fees and penalties (correct +10,000, wrong -10,000 or -20,000 if urgent, unseen
-2,500 or -10,000 if urgent), and spend is subtracted.

## Evaluation

`POST /api/eval/runs {doctor, model, preset, n, seed}` plays `n` rollouts in
the background into `data/evals.sqlite`. The dashboard shows outcome, thinking
process (shortcuts, unsupported eliminations, dangerous causes cleared,
escalation, ordering violations, tests that could not change the board), spend
against the safe route, clean rate by situation and by temptation, confusions,
and a per-case timeline with every elimination's validity. Two runs can be
compared side by side and exported as HTML or JSON.

## Tests

```bash
uv run python -m pytest
```
