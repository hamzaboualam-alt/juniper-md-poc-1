"""Acute chest pain. Dataset situation chest_pain (AHA/ACC 2021, ESC 2024)."""
from __future__ import annotations

from . import CaseTemplate, Clause, Hypothesis, OrderRule, Shortcut, Test, World

TESTS = {
    "history_exam": Test("history_exam", "Focused history and exam", "history_exam", {"done": "Findings recorded"}, "desk", "chest_pain.s1"),
    "ecg": Test("ecg", "12-lead ECG", "ecg", {
        "normal": "Sinus rhythm, no ischemic or dynamic change",
        "ischemic": "Ischemic change (ST depression / T inversion), dynamic on repeat",
        "diffuse_st": "Widespread ST elevation with PR depression",
    }, "bedside", "chest_pain.s2"),
    "cxr": Test("cxr", "Chest radiograph", "cxr", {
        "normal": "Normal film",
        "infiltrate": "Lobar consolidation",
        "pneumothorax": "Absent vascular markings with a visible pleural line",
        "wide_mediastinum": "Widened mediastinum",
    }, "radiology", "chest_pain.s3"),
    "troponin": Test("troponin", "Serial high-sensitivity troponin", "troponin", {
        "negative": "Both draws below the 99th percentile, no delta",
        "positive": "Rising troponin above the 99th percentile",
    }, "lab", "chest_pain.s4"),
    "perc": Test("perc", "PERC rule", "score", {
        "negative": "All eight PERC criteria met: PE can be ruled out without testing",
        "positive": "At least one criterion not met: PERC does not apply",
    }, "desk", "chest_pain.s5", requires=("history_exam",)),
    "wells": Test("wells", "Wells score for PE", "score", {
        "unlikely": "Wells 4 or less: PE unlikely",
        "likely": "Wells above 4: PE likely",
    }, "desk", "chest_pain.s5", requires=("history_exam",)),
    "addrs": Test("addrs", "Aortic dissection detection risk score (ADD-RS)", "score", {
        "low": "ADD-RS 0 or 1",
        "high": "ADD-RS 2 or 3",
    }, "desk", "chest_pain.s5", requires=("history_exam",)),
    "ddimer": Test("ddimer", "D-dimer", "ddimer", {
        "negative": "Below the age-adjusted cutoff",
        "positive": "Above the cutoff",
    }, "lab", "chest_pain.s6"),
    "ctpa": Test("ctpa", "CT pulmonary angiography", "ctpa", {
        "negative": "No pulmonary embolus",
        "positive": "Filling defect: pulmonary embolism",
    }, "imaging", "chest_pain.s7"),
    "cta_aorta": Test("cta_aorta", "ECG-gated CT angiography of the aorta", "cta_aorta", {
        "negative": "No intimal flap, no aortic syndrome",
        "dissection": "Intimal flap: aortic dissection",
    }, "imaging", "chest_pain.s7"),
    "echo": Test("echo", "Echocardiography", "echo", {
        "normal": "Normal; no effusion",
        "effusion": "New pericardial effusion",
    }, "imaging", "chest_pain.s7"),
}

NEG = {"ecg": "normal", "cxr": "normal", "troponin": "negative", "perc": "positive", "wells": "unlikely",
       "addrs": "low", "ddimer": "negative", "ctpa": "negative", "cta_aorta": "negative", "echo": "normal"}

HYPOTHESES = {
    "acs": Hypothesis("acs", "Acute coronary syndrome", "must_not_miss", NEG | {"troponin": "positive"},
        eliminate_when=(Clause({"ecg": ("normal", "diffuse_st"), "troponin": "negative"}, "Low-risk class: non-ischemic ECG and negative serial high-sensitivity troponin.", "aha_cp_top"),),
        do_not_rely=(
            Shortcut({"ecg": "normal"}, "One normal ECG.", "iatrox_cp"),
            Shortcut({"cxr": ("normal", "infiltrate", "pneumothorax", "wide_mediastinum")}, "The chest radiograph.", "aha_cp_rec"),
        ),
        confirmed_by={"troponin": "positive", "ecg": "ischemic"}),
    "pe": Hypothesis("pe", "Pulmonary embolism", "must_not_miss", NEG | {"wells": "likely", "ddimer": "positive", "ctpa": "positive"},
        eliminate_when=(
            Clause({"perc": "negative"}, "Very low suspicion and all eight PERC criteria met.", "wikem_wells"),
            Clause({"wells": "unlikely", "ddimer": "negative"}, "Wells 4 or less and D-dimer below the age-adjusted cutoff.", "evi_wells"),
            Clause({"ctpa": "negative"}, "Negative CT pulmonary angiography.", "iatrox_pe"),
        ),
        do_not_rely=(
            Shortcut({"wells": "likely", "ddimer": "negative"}, "D-dimer when clinical probability is high.", "evi_wells"),
            Shortcut({"cxr": "normal"}, "A normal chest radiograph.", "aafp_cp"),
        ),
        confirmed_by={"ctpa": "positive"}),
    "ad": Hypothesis("ad", "Aortic dissection", "must_not_miss", NEG | {"addrs": "high", "ddimer": "positive", "cta_aorta": "dissection"},
        eliminate_when=(
            Clause({"addrs": "low", "ddimer": "negative"}, "ADD-RS 1 or less and D-dimer below 500 ng/mL: the work-up can stop (ADvISED, PROFUNDUS).", "advised"),
            Clause({"cta_aorta": "negative"}, "Negative ECG-gated contrast CT, the ESC 2024 first-line imaging.", "esc_aortic_2024", inferred=True),
        ),
        do_not_rely=(
            Shortcut({"ddimer": "negative"}, "D-dimer alone, without the risk score.", "mdcalc_addrs"),
            Shortcut({"addrs": "low"}, "ADD-RS of 0 or 1 as proof on its own.", "mdcalc_addrs"),
            Shortcut({"cxr": "normal"}, "Chest radiography.", "esc_aortic_2024"),
        ),
        confirmed_by={"cta_aorta": "dissection"}),
    "ptx": Hypothesis("ptx", "Pneumothorax", "other", NEG | {"cxr": "pneumothorax"},
        eliminate_when=(Clause({"cxr": ("normal", "infiltrate", "wide_mediastinum")}, "A chest radiograph without a pneumothorax.", "aafp_cp"),),
        do_not_rely=(Shortcut({"history_exam": "done"}, "Exam findings alone.", "aafp_cp"),),
        confirmed_by={"cxr": "pneumothorax"}),
    "pna": Hypothesis("pna", "Pneumonia", "other", NEG | {"cxr": "infiltrate", "ddimer": "positive"},
        eliminate_when=(Clause({"cxr": ("normal", "pneumothorax", "wide_mediastinum")}, "A chest radiograph without consolidation makes it unlikely.", "aafp_cp"),),
        do_not_rely=(Shortcut({"history_exam": "done"}, "Exam findings alone.", "aafp_cp"),),
        confirmed_by={"cxr": "infiltrate"}),
    "pc": Hypothesis("pc", "Pericardial disease", "other", NEG | {"ecg": "diffuse_st", "echo": "effusion"},
        eliminate_when=(Clause({"echo": "normal"}, "No effusion on echocardiography and no diffuse ST elevation: fewer than two of four criteria.", "aafp_cp", inferred=True),),
        do_not_rely=(Shortcut({"ecg": "normal"}, "A normal ECG: without ST elevation the diagnosis is easily missed.", "aafp_cp"),),
        confirmed_by={"echo": "effusion"},
        no_rule_note="No formal exclusion rule in the sources; diagnosis needs two of four criteria."),
    "nc": Hypothesis("nc", "Noncardiac chest pain (chest wall, reflux)", "other", NEG | {"perc": "negative"},
        remainder=True, no_rule_note="Not eliminated; it is what remains once the dangerous causes are excluded."),
}

ROUTE = ("history_exam", "ecg", "cxr", "troponin", "perc", "wells", "addrs", "ddimer", "ctpa", "cta_aorta", "echo")

ORDER_RULES = (
    OrderRule("ddimer", "wells", ("unlikely",), "D-dimer is a rule-out test for low or intermediate probability; at high probability go straight to imaging.", "evi_wells", findings=("tachycardia", "recent immobilisation")),
)

CASES = (
    CaseTemplate("acs_atypical", "acs", 61, "female",
        "I've had a tightness across my chest since this morning, it comes and goes.",
        ("pressure-like pain", "sweating", "mild chest wall tenderness", "diabetes", "smoker", "normal vital signs"),
        results={"ecg": "normal"},
        tempts="premature closure on noncardiac chest pain", decoy="nc",
        note="Chest wall tenderness and a normal ECG tempt an early benign call; the serial troponin is positive."),
    CaseTemplate("acs_unstable", "acs", 67, "male",
        "Crushing chest pain for forty minutes, I feel faint.",
        ("ongoing crushing pain", "sweating", "hypotension", "hemodynamically unstable", "smoker", "hypertension"),
        results={"ecg": "ischemic"}, unstable=True,
        tempts="working the differential instead of escalating", decoy=None,
        note="Ongoing ischemic discomfort with dynamic ECG change and instability: emergency escalation first."),
    CaseTemplate("pe_likely", "pe", 44, "female",
        "Sharp pain on the right when I breathe in, and I can't catch my breath.",
        ("pleuritic pain", "tachycardia", "dyspnea", "recent immobilisation", "calf swelling", "hypoxia"),
        tempts="D-dimer at high probability", decoy=None,
        note="Wells is likely; a negative D-dimer would be meaningless here, the route is CTPA."),
    CaseTemplate("pe_unlikely_positive_ddimer", "pe", 38, "male",
        "Chest discomfort and I get winded on the stairs since last week.",
        ("mild pleuritic pain", "mild tachycardia", "dyspnea", "normal oxygen saturation"),
        results={"wells": "unlikely", "perc": "positive", "ddimer": "positive"},
        tempts="stopping at a low Wells score", decoy="nc",
        note="Wells unlikely but PERC fails and D-dimer is positive, so CTPA is still needed."),
    CaseTemplate("ad_classic", "ad", 58, "male",
        "It felt like something tore in my chest, the pain went straight through to my back.",
        ("abrupt tearing pain", "pain radiating to the back", "blood pressure differential between arms", "hypertension"),
        tempts="chasing ACS and ignoring the aorta", decoy="acs",
        note="ADD-RS is 2 or more: imaging regardless of D-dimer."),
    CaseTemplate("ad_subtle", "ad", 52, "female",
        "A sudden sharp chest pain an hour ago, better now but still there.",
        ("abrupt onset pain", "normal pulses", "hypertension", "normal vital signs"),
        results={"addrs": "low", "ddimer": "positive", "cxr": "normal"},
        tempts="treating a low ADD-RS as proof", decoy="nc",
        note="ADD-RS 1 with a positive D-dimer cannot stop the work-up; CT finds the dissection."),
    CaseTemplate("ptx_tall", "ptx", 24, "male",
        "Sudden stabbing pain on the left and I'm short of breath.",
        ("pleuritic pain", "dyspnea", "absent breath sounds left", "tall thin build", "distress"),
        tempts="cardiac work-up before the film", decoy="pe",
        note="One chest radiograph settles it."),
    CaseTemplate("pna_febrile", "pna", 70, "female",
        "Pain in my right side when I breathe, and I've had fever and a cough for three days.",
        ("fever", "productive cough", "localized pleuritic pain", "dullness to percussion right base", "tachycardia"),
        results={"ddimer": "positive", "wells": "likely"},
        tempts="a positive D-dimer dragging the work-up to CTPA", decoy="pe",
        note="Infection raises the D-dimer; the film shows consolidation and the Wells route is not needed once pneumonia explains the picture."),
    CaseTemplate("pc_positional", "pc", 33, "male",
        "Sharp pain in the middle of my chest, worse lying down and better when I sit forward.",
        ("positional pain", "pleuritic pain", "friction rub", "recent viral illness", "normal vital signs"),
        tempts="calling it ACS on the ST elevation", decoy="acs",
        note="Diffuse ST elevation with PR depression and a positional rub; troponin negative; echo shows the effusion."),
    CaseTemplate("nc_young", "nc", 29, "female",
        "My chest has been sore for two days, it hurts when I press on it.",
        ("reproducible chest wall tenderness", "pain with movement", "no risk factors", "normal vital signs", "age under 50"),
        tempts="over-testing a low-risk patient", decoy=None,
        note="PERC negative, ECG and troponin negative: noncardiac is what remains, and imaging adds nothing."),
)

WORLD = World(
    situation="chest_pain",
    title="Acute chest pain",
    presentation="An adult walks into the emergency department with chest pain.",
    tests=TESTS,
    hypotheses=HYPOTHESES,
    cases=CASES,
    route=ROUTE,
    order_rules=ORDER_RULES,
)
