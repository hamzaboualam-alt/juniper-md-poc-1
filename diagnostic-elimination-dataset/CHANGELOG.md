# Changelog

## 0.2.0 (2026-10-21): verification pass

### Guideline versions checked

| Situation | Guideline used in 0.1.0 | Finding | Action |
|---|---|---|---|
| focal_deficit | AHA/ASA 2019 update | Replaced by the 2026 AHA/ASA guideline (published January 2026) | Glucose and imaging steps rewritten from 2026 recommendation text |
| fever_sepsis | Surviving Sepsis Campaign 2021 | Replaced by the 2026 edition (published March 2026) | Screening, certainty grading and time-limited investigation rewritten; lactate and procalcitonin still cite 2021 and are flagged |
| chest_pain (dissection) | ADD-RS sources only | 2024 ESC aortic guideline found | ESC 2024 recommendations added; US/Europe divergence recorded |
| others | — | Not version-checked in this pass | Listed as a known limit |

### Inferred rules resolved (7 → 2)

| Situation / hypothesis | 0.1.0 | 0.2.0 |
|---|---|---|
| focal_deficit / hemorrhage | Inferred from CT's role (2019) | Explicit 2026 recommendation: CT or MRI excludes hemorrhage (class 1, level A) |
| focal_deficit / glucose mimic | Review article | 2026 guideline: check glucose before thrombolysis; persistent deficit after correction still warrants treatment |
| leg_swelling / DVT | Inferred from ultrasound's role | Explicit stopping rules: negative whole-leg scan, negative serial proximal scans, or negative D-dimer after a negative proximal scan |
| lower_abdominal_pain / appendicitis | Inferred from CT accuracy | Quantified: negative CT leaves about 4% probability at 43% prevalence (Cochrane) |
| flank_pain / stone | Inferred from CT accuracy | Quantified: pooled CT sensitivity 94–100%; low-dose CT LR− about 0.04 |
| flank_pain / other abdominal cause | Inferred | Removed: CT detected only 74% of alternative causes in one study; now a "do not rely" warning |
| chest_pain / dissection (negative CT) | Inferred, MDCalc | Still inferred, now cites ESC 2024 first-line imaging recommendation |
| syncope / cardiac | Inferred | Still inferred; the ESC class I, level B discharge recommendation is verified, the inference is treating discharge as elimination |

### Other changes
- 16 sources added; 3 superseded sources (`acc_stroke_2019`, `ijem_stroke`, `ssc_2021_pmc`) kept in the registry for audit but no longer cited.
- New step evidence: Cochrane appendicitis numbers, CT alternative-diagnosis yield in flank pain, ESC 2024 ADD-RS algorithm.
- New gaps: distal DVT relevance, pediatric stroke, 2021 sepsis leftovers.
