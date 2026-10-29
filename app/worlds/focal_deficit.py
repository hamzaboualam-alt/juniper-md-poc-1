"""Acute focal neurologic deficit, suspected stroke. Dataset situation focal_deficit (AHA/ASA 2026)."""
from __future__ import annotations

from . import CaseTemplate, Clause, Hypothesis, OrderRule, Shortcut, Test, World

TESTS = {
    "history_exam": Test("history_exam", "History, time last known well, exam", "history_exam", {"done": "Findings recorded"}, "desk", "focal_deficit.s1"),
    "glucose": Test("glucose", "Bedside glucose", "glucose", {
        "normal": "Glucose in range",
        "low": "Severe hypoglycemia",
        "high": "Severe hyperglycemia",
    }, "bedside", "focal_deficit.s1"),
    "correct_glucose": Test("correct_glucose", "Correct the glucose and re-examine", "glucose", {
        "deficit_resolved": "Deficit resolved after correction",
        "deficit_persists": "Disabling deficit persists after correction",
        "not_applicable": "Glucose was normal; nothing to correct",
    }, "bedside", "focal_deficit.s1", requires=("glucose",)),
    "ct_head": Test("ct_head", "Noncontrast CT head", "ct_head", {
        "no_hemorrhage": "No hemorrhage; no or mild early ischemic change",
        "hemorrhage": "Intraparenchymal hemorrhage",
    }, "imaging", "focal_deficit.s2"),
    "ecg_troponin": Test("ecg_troponin", "Baseline ECG and troponin", "troponin", {
        "unremarkable": "Sinus rhythm, troponin negative",
        "af": "Atrial fibrillation, troponin negative",
    }, "lab", "focal_deficit.s3"),
    "cta_head_neck": Test("cta_head_neck", "CT angiography and perfusion", "cta_head_neck", {
        "negative": "No large vessel occlusion, no perfusion deficit",
        "occlusion": "Large vessel occlusion with salvageable penumbra",
    }, "imaging", "focal_deficit.s4"),
}

NEG = {"glucose": "normal", "correct_glucose": "not_applicable", "ct_head": "no_hemorrhage", "ecg_troponin": "unremarkable", "cta_head_neck": "negative"}

HYPOTHESES = {
    "ais": Hypothesis("ais", "Acute ischemic stroke", "must_not_miss", NEG | {"cta_head_neck": "occlusion"},
        eliminate_when=(Clause({"ct_head": "no_hemorrhage", "cta_head_neck": "negative"}, "No occlusion or perfusion deficit on vascular imaging and no infarct on CT, with a mimic that explains the deficit.", "aha_asa_2026", inferred=True, findings=("witnessed seizure",)),),
        do_not_rely=(
            Shortcut({"ct_head": "no_hemorrhage"}, "Mild early ischemic change on CT as a reason to withhold thrombolysis.", "aha_asa_2026"),
        ),
        confirmed_by={"cta_head_neck": "occlusion"},
        no_rule_note="Stroke is confirmed or treated, not eliminated, in this route."),
    "ich": Hypothesis("ich", "Intracranial hemorrhage", "must_not_miss", NEG | {"ct_head": "hemorrhage"},
        eliminate_when=(Clause({"ct_head": "no_hemorrhage"}, "Noncontrast CT or MRI without hemorrhage (class 1, level A).", "aha_asa_2026"),),
        confirmed_by={"ct_head": "hemorrhage"}),
    "hypo": Hypothesis("hypo", "Hypoglycemia or severe hyperglycemia (stroke mimic)", "must_not_miss", NEG | {"glucose": "low", "correct_glucose": "deficit_resolved"},
        eliminate_when=(
            Clause({"glucose": "normal"}, "Normal bedside glucose.", "aha_asa_2026"),
            Clause({"correct_glucose": "deficit_persists"}, "A disabling deficit persisting after glucose correction; thrombolysis is still recommended then.", "aha_asa_2026"),
        ),
        confirmed_by={"correct_glucose": "deficit_resolved"}),
    "mimic": Hypothesis("mimic", "Other stroke mimic (seizure, migraine)", "other", NEG,
        remainder=True, no_rule_note="Seizure, migraine and other mimics are not sourced; it is what is left when imaging shows no stroke."),
}

ROUTE = ("history_exam", "glucose", "correct_glucose", "ct_head", "cta_head_neck", "ecg_troponin")

ORDER_RULES = (
    OrderRule("ecg_troponin", "ct_head", None, "Baseline ECG and troponin must not delay brain imaging and reperfusion.", "aha_asa_2026", findings=("within the treatment window",)),
    OrderRule("cta_head_neck", "ct_head", None, "Noncontrast imaging to exclude hemorrhage comes before vascular imaging and any reperfusion decision.", "aha_asa_2026"),
)

CASES = (
    CaseTemplate("ais_lvo_in_window", "ais", 71, "female",
        "My husband noticed my face drooping and my words came out wrong, about an hour ago.",
        ("sudden left-sided weakness", "aphasia", "last known well 70 minutes ago", "within the treatment window", "atrial fibrillation on exam"),
        results={"ecg_troponin": "af"}, unstable=True,
        tempts="ordering ECG and troponin before the scan", decoy=None,
        note="Stroke pathway immediately: glucose, CT within 25 minutes, then CTA; baseline tests must not delay it."),
    CaseTemplate("ich", "ich", 64, "male",
        "Sudden headache and my right arm went weak half an hour ago.",
        ("sudden right-sided weakness", "severe headache", "hypertension", "vomiting", "last known well 30 minutes ago", "within the treatment window"),
        unstable=True,
        tempts="assuming ischemic stroke", decoy="ais",
        note="CT shows the hemorrhage; thrombolysis would be catastrophic."),
    CaseTemplate("hypo_mimic", "hypo", 58, "male",
        "He's confused and his left side isn't working, he's diabetic.",
        ("left-sided weakness", "confusion", "insulin-treated diabetes", "sweating", "last known well 40 minutes ago", "within the treatment window"),
        unstable=True,
        tempts="imaging before the glucose", decoy="ais",
        note="Glucose is severely low and the deficit resolves with correction."),
    CaseTemplate("hypo_then_stroke", "ais", 69, "female",
        "She's diabetic, got confused and now can't move her right side.",
        ("right-sided weakness", "insulin-treated diabetes", "last known well 50 minutes ago", "within the treatment window"),
        results={"glucose": "low", "correct_glucose": "deficit_persists", "cta_head_neck": "occlusion"}, unstable=True,
        tempts="stopping at the low glucose", decoy="hypo",
        note="Glucose is low but the disabling deficit persists after correction: that is a stroke, and thrombolysis is still recommended."),
    CaseTemplate("mimic_postictal", "mimic", 35, "male",
        "He had a fit and now his arm is weak.",
        ("witnessed seizure", "right arm weakness improving", "known epilepsy", "last known well 90 minutes ago", "within the treatment window"),
        unstable=True,
        tempts="treating a postictal deficit as a stroke", decoy="ais",
        note="Glucose normal, no hemorrhage, no occlusion: the improving deficit after a witnessed seizure is the mimic."),
)

WORLD = World(
    situation="focal_deficit",
    title="Acute focal neurologic deficit",
    presentation="An adult arrives with sudden weakness, numbness or speech loss.",
    tests=TESTS,
    hypotheses=HYPOTHESES,
    cases=CASES,
    route=ROUTE,
    order_rules=ORDER_RULES,
)
