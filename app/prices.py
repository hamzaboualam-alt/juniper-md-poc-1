"""Test prices: what a US hospital charges, not what Medicare pays.

Figures are gross charges (hospital plus professional fee) taken from hospital
price-transparency pages, so a patient without insurance would be billed these
amounts. The primary source is Cheshire Medical Center's standard charge list
(valid 1 Jul 2025 to 30 Sep 2026); where Cheshire does not list a service the
figure comes from another hospital's published list or an aggregator of
published cash prices, and the entry is marked approximate:

- Cheshire Medical Center (Dartmouth Health), standard charges: ECG $539,
  chest X-ray 2 views $594, head CT without contrast $3,134, abdominal CT with
  contrast $4,255, MRI brain without contrast $5,547, MRI pelvis without and
  with contrast $7,762, complete echocardiogram $4,621, pelvic ultrasound
  complete $1,485, transvaginal ultrasound $1,251, glucose $52, blood pregnancy
  test $86.
- National Jewish Health, prices as of 1 Jul 2026 (hospital plus professional):
  CT angiography chest 71275 $3,266.
- Turquoise Health, average published cash price across facilities: CTA head
  $2,198, CTA neck $2,196.
- Spanish Peaks Regional Health Center lab charges: troponin $124 per draw,
  NT-proBNP $161.
- Intermountain Health (Northglenn), D-dimer $302.45.
- HonorHealth average lab pricing: blood culture $211 per set, lactate $131.
- Lumbar puncture 62270: $1,726 total (hospital $1,585 plus physician $141),
  the national aggregate reported by PayerPrice for July 2026; no hospital
  chargemaster line for the bedside code was found.

For reference, Medicare's national global amounts (CMS October 2026 files)
run 10 to 30 times lower: ECG $15.36, chest X-ray $33.07, head CT $106.55,
CTPA $280.57, MRI brain $195.40, echo $196.73, lumbar puncture $165.00. The
game grades spend against the cheapest safe route computed from the same
table, so the scale only matters for the clinic-day fees (ShiftRules).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    cpt: str
    label: str
    usd: float
    minutes: int  # wall-clock minutes until the result is back
    approximate: bool = False


PRICES: dict[str, Price] = {
    "history_exam": Price("-", "Focused history and physical examination", 0.0, 10),
    "neuro_exam": Price("-", "Full neurological examination", 0.0, 10),
    "score": Price("-", "Clinical decision rule applied at the bedside", 0.0, 2),
    "ecg": Price("93000", "12-lead ECG with interpretation", 539.00, 10),
    "cxr": Price("71046", "Chest radiograph, 2 views", 594.00, 30),
    "troponin": Price("84484 x2", "High-sensitivity troponin, serial (two draws)", 248.00, 120, approximate=True),
    "ddimer": Price("85379", "D-dimer, quantitative", 302.00, 45, approximate=True),
    "bnp": Price("83880", "Natriuretic peptide (BNP / NT-proBNP)", 161.00, 45, approximate=True),
    "glucose": Price("82962", "Bedside glucose", 52.00, 2),
    "lactate": Price("83605", "Blood lactate", 131.00, 30, approximate=True),
    "hcg": Price("84702", "Serum beta-hCG, quantitative", 86.00, 30),
    "cultures": Price("87040 x2", "Blood cultures, two sets", 422.00, 5, approximate=True),
    "ctpa": Price("71275", "CT pulmonary angiography", 3266.00, 60),
    "cta_aorta": Price("71275 + 74174", "ECG-gated CT angiography, neck to pelvis", 7521.00, 60, approximate=True),
    "echo": Price("93306", "Transthoracic echocardiography with Doppler", 4621.00, 45),
    "ct_head": Price("70450", "Noncontrast CT head", 3134.00, 30),
    "cta_head_neck": Price("70496 + 70498", "CT angiography head and neck", 4394.00, 45, approximate=True),
    "mri_brain": Price("70551", "MRI brain", 5547.00, 90),
    "lp": Price("62270", "Lumbar puncture with CSF analysis", 1726.00, 60, approximate=True),
    "pelvic_us": Price("76856 + 76830", "Pelvic ultrasound, transabdominal and transvaginal, with Doppler", 2736.00, 45),
    "ct_abd": Price("74177", "CT abdomen and pelvis with IV contrast", 4255.00, 60, approximate=True),
    "mri_pelvis": Price("72197", "MRI pelvis without and with contrast", 7762.00, 90),
}
