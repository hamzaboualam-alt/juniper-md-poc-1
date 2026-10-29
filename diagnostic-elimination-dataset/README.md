# Diagnosis-by-elimination routes: dataset v0.2.0

A structured, source-linked dataset of how clinicians eliminate hypotheses for 12 common presenting situations. Each situation follows the same four layers used in the companion viewer:

| Layer | Meaning | Where in the data |
|---|---|---|
| 0 | The patient situation: complaint, history, exam, first tests | `layer0` |
| Gate | Emergency or not, before any differential | `gate`, `gate_note` |
| 1 | Candidate hypotheses, ordered by danger | `hypotheses` (`tier` = `must_not_miss` or `other`) |
| 2 | Elimination route: ordered steps and what each does to each hypothesis | `steps[].effects`, `rules` |
| 3 | Evidence: a source on every claim, plus extra step evidence | `source` fields, `steps[].evidence`, `sources` |

Research prototype assembled from public guideline documents and their summaries. **Not clinical guidance.** Every threshold must be checked against the current original guideline before any real use.

## Situations

Chosen by ED visit frequency (CDC NHAMCS fact sheets list abdominal pain, chest pain, fever, headache and shortness of breath as the leading reasons for visit), then by the availability of a diagnostic guideline.

| id | Situation | Lead source |
|---|---|---|
| chest_pain | Acute chest pain | AHA/ACC 2021, ESC 2024 (aortic) |
| dyspnea | Acute shortness of breath | NICE CG187, ASH 2018 |
| lower_abdominal_pain | Acute lower abdominal or pelvic pain | ACR Appropriateness Criteria |
| headache | Acute nontraumatic headache | ACEP 2019, SNNOOP10 |
| fever_sepsis | Fever in an adult, suspected sepsis | Surviving Sepsis Campaign 2026 |
| syncope | Syncope | ACC/AHA/HRS 2017, ESC 2018 |
| ugib | Upper GI bleeding | ACG 2021 |
| leg_swelling | Unilateral leg swelling, suspected DVT | ASH 2018 |
| dizziness | Acute dizziness or vertigo | SAEM GRACE-3 2023 |
| focal_deficit | Acute focal deficit, suspected stroke | AHA/ASA 2026 |
| low_back_pain | Acute low back pain | ACR Appropriateness Criteria |
| flank_pain | Acute flank pain, suspected stone | ACR Appropriateness Criteria |

## Files

- `dataset.json`: everything in one file (sources, effect types, situations).
- `situations/<id>.json`: one file per situation.
- `csv/`: the same data as relational tables, joined on `situation_id`, `hypothesis_id`, `step_id` and `source_id`:
  `situations`, `layer0_inputs`, `gate_branches`, `hypotheses`, `steps`, `step_effects`, `step_evidence`, `elimination_rules`, `gaps`, `sources`.
- `validation_report.json`: counts and the list of items with no source.
- `CHANGELOG.md`: what the verification pass changed and why.
- `build/`: the Python files that generate everything. Edit the situation files, then run `python3 build.py out` to validate and rebuild.

## Key fields

**Step effects** (`step_effects.csv`, `steps[].effects`) use four types:

| type | label | meaning |
|---|---|---|
| `rule` | Can eliminate | A result of this step can remove the hypothesis |
| `conf` | Can confirm | A result can establish the hypothesis |
| `steer` | Shifts suspicion | Changes probability, decides nothing alone |
| `blind` | Cannot decide it | Commonly relied on, but does not decide this hypothesis |

**Elimination rules** (`elimination_rules.csv`, `rules`):

- `eliminate_when`: the result that lets a clinician cross the hypothesis off.
- `do_not_rely`: shortcuts the sources warn against.
- `no_rule_note`: written when no exclusion rule was found, so absence is explicit rather than silent.
- `inferred = true`: the rule follows from a stated test accuracy or role but is not written as an exclusion rule in the source. Treat these as weaker.

**Statuses** on hypotheses: `sourced` (route found), `partial` (some steps sourced), `stub` (named only).

**Source tiers** in `sources.csv`: `primary_guideline`, `primary_guideline_summary`, `systematic_review`, `primary_study`, `secondary_summary`, `educational`, `local_adaptation`, `epidemiology`, `textbook`. Many rules come from secondary summaries of guidelines; upgrading them to the primary text is the main next step.

## Known limits

- **Version drift.** Version 0.2.0 moved stroke to the 2026 AHA/ASA guideline and sepsis to the 2026 Surviving Sepsis Campaign guideline (see `CHANGELOG.md`). The sepsis lactate and procalcitonin steps still cite 2021. The other situations' lead guidelines were not version-checked in this pass; `last_verified` is 2026-10-21.
- **Unsourced items.** 19 items (mostly gap notes, the dyspnea gate and some Layer 0 labels) carry no source and are listed in `validation_report.json`.
- **Parallel work-ups.** Real patients often have several must-not-miss hypotheses open at once. No source found says how to prioritize between them; the steps here are ordered within each situation only.
- **Populations.** Adults only, mostly emergency settings, mostly US and European guidance.
- **Textbook use.** *Symptom to Diagnosis* (Stern, Cifu, Altkorn) informed the situation format only; none of its content is reproduced.
- **Inferred and stub content.** 2 elimination rules remain inferred (dissection after negative CT, cardiac syncope after low-risk discharge); 10 hypotheses are stubs.

## Extending

1. Add sources to `build/sources.py` with a tier.
2. Add or edit a situation in `build/situations_*.py` using the helper functions.
3. Run `python3 build.py out`. The build fails on unknown sources, effects pointing at unknown hypotheses, or hypotheses with neither a rule nor a note.
