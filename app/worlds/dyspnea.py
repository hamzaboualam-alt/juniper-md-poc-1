"""Acute shortness of breath. Dataset situation dyspnea (NICE CG187, ASH 2018)."""
from __future__ import annotations

from . import CaseTemplate, Clause, Hypothesis, OrderRule, Shortcut, Test, World

TESTS = {
    "history_exam": Test("history_exam", "History and exam", "history_exam", {"done": "Findings recorded"}, "desk", "dyspnea.s1"),
    "ecg": Test("ecg", "12-lead ECG", "ecg", {
        "normal": "Sinus rhythm, no ischemic change",
        "ischemic": "Ischemic change, dynamic on repeat",
        "sinus_tach": "Sinus tachycardia, no ischemic change",
    }, "bedside", "dyspnea.s2"),
    "cxr": Test("cxr", "Chest radiograph", "cxr", {
        "normal": "Normal film",
        "congestion": "Pulmonary venous congestion and interstitial edema",
        "infiltrate": "Lobar consolidation",
        "pneumothorax": "Visible pleural line, absent vascular markings",
        "hyperinflated": "Hyperinflated lungs, flattened diaphragms, no consolidation",
    }, "radiology", "dyspnea.s3"),
    "bnp": Test("bnp", "Natriuretic peptide", "bnp", {
        "low": "NT-proBNP below 300 ng/L (BNP below 100 ng/L)",
        "grey": "NT-proBNP between the rule-out and rule-in thresholds",
        "high": "NT-proBNP well above the rule-in threshold",
    }, "lab", "dyspnea.s4"),
    "troponin": Test("troponin", "Serial high-sensitivity troponin", "troponin", {
        "negative": "Both draws below the 99th percentile",
        "positive": "Rising troponin above the 99th percentile",
    }, "lab", "dyspnea.s2"),
    "wells": Test("wells", "Wells score for PE", "score", {
        "unlikely": "Wells 4 or less: PE unlikely",
        "likely": "Wells above 4: PE likely",
    }, "desk", "dyspnea.s5", requires=("history_exam",)),
    "ddimer": Test("ddimer", "D-dimer", "ddimer", {
        "negative": "Below the age-adjusted cutoff",
        "positive": "Above the cutoff",
    }, "lab", "dyspnea.s5"),
    "ctpa": Test("ctpa", "CT pulmonary angiography", "ctpa", {
        "negative": "No pulmonary embolus",
        "positive": "Filling defect: pulmonary embolism",
    }, "imaging", "dyspnea.s5"),
    "echo": Test("echo", "Echocardiography", "echo", {
        "normal": "Normal ventricular function, no significant valve disease",
        "reduced_ef": "Reduced ejection fraction with raised filling pressures",
    }, "imaging", "dyspnea.s6"),
}

NEG = {"ecg": "normal", "cxr": "normal", "bnp": "low", "troponin": "negative", "wells": "unlikely", "ddimer": "negative", "ctpa": "negative", "echo": "normal"}

HYPOTHESES = {
    "ahf": Hypothesis("ahf", "Acute heart failure", "must_not_miss", NEG | {"cxr": "congestion", "bnp": "high", "echo": "reduced_ef"},
        eliminate_when=(
            Clause({"bnp": "low"}, "BNP below 100 ng/L or NT-proBNP below 300 ng/L rules out heart failure in new suspected heart failure.", "nice_cg187",
                   unless_findings=("age over 75", "known heart failure", "obesity")),
            Clause({"echo": "normal"}, "Normal echocardiography settles the grey zone.", "nice_cg187", inferred=True),
        ),
        do_not_rely=(
            Shortcut({"bnp": "low"}, "The rule-out threshold in older patients, obesity or prior heart failure: false negatives of 1 in 10 to 1 in 5.", "bnp_elderly", findings=("age over 75",)),
            Shortcut({"bnp": "low"}, "The rule-out threshold in obesity or known heart failure.", "bnp_elderly", findings=("known heart failure",)),
        ),
        confirmed_by={"echo": "reduced_ef"}),
    "pe": Hypothesis("pe", "Pulmonary embolism", "must_not_miss", NEG | {"ecg": "sinus_tach", "wells": "likely", "ddimer": "positive", "ctpa": "positive"},
        eliminate_when=(
            Clause({"wells": "unlikely", "ddimer": "negative"}, "Low pre-test probability and negative D-dimer.", "ash_vte"),
            Clause({"ctpa": "negative"}, "Negative CTPA.", "ash_vte"),
        ),
        do_not_rely=(Shortcut({"wells": "likely", "ddimer": "negative"}, "D-dimer when probability is high.", "ash_vte"),),
        confirmed_by={"ctpa": "positive"}),
    "acs": Hypothesis("acs", "Acute coronary syndrome", "must_not_miss", NEG | {"troponin": "positive"},
        eliminate_when=(Clause({"ecg": ("normal", "sinus_tach"), "troponin": "negative"}, "Low-risk class with non-ischemic ECG and negative serial troponin.", "aha_cp_top"),),
        do_not_rely=(Shortcut({"ecg": ("normal", "sinus_tach")}, "One normal ECG.", "iatrox_cp"),),
        confirmed_by={"troponin": "positive"}),
    "ptx": Hypothesis("ptx", "Pneumothorax", "must_not_miss", NEG | {"cxr": "pneumothorax"},
        eliminate_when=(Clause({"cxr": ("normal", "congestion", "infiltrate", "hyperinflated")}, "A chest radiograph without a pneumothorax.", "aafp_cp"),),
        do_not_rely=(Shortcut({"history_exam": "done"}, "Exam alone.", "aafp_cp"),),
        confirmed_by={"cxr": "pneumothorax"}),
    "pna": Hypothesis("pna", "Pneumonia", "other", NEG | {"cxr": "infiltrate", "ddimer": "positive"},
        eliminate_when=(Clause({"cxr": ("normal", "hyperinflated", "congestion")}, "A film without consolidation makes pneumonia unlikely.", "aafp_cp"),),
        do_not_rely=(Shortcut({"history_exam": "done"}, "Exam alone.", "aafp_cp"),),
        confirmed_by={"cxr": "infiltrate"}),
    "copd": Hypothesis("copd", "COPD or asthma exacerbation", "other", NEG | {"cxr": "hyperinflated"},
        remainder=True, no_rule_note="No route sourced; it is the working diagnosis once heart, clot and lung emergencies are excluded."),
}

ROUTE = ("history_exam", "ecg", "cxr", "bnp", "troponin", "wells", "ddimer", "ctpa", "echo")

ORDER_RULES = (
    OrderRule("ddimer", "wells", ("unlikely",), "D-dimer only at low probability; at high probability image.", "ash_vte", findings=("tachycardia", "recent surgery")),
)

CASES = (
    CaseTemplate("ahf_classic", "ahf", 72, "male",
        "I can't lie flat any more and my legs have swollen up.",
        ("orthopnea", "bilateral leg edema", "raised jugular venous pressure", "bibasal crackles", "known hypertension"),
        tempts="ordering CTPA for every breathless patient", decoy="pe",
        note="Congestion on the film and a high natriuretic peptide; echo confirms."),
    CaseTemplate("ahf_elderly_low_bnp", "ahf", 81, "female",
        "I've been getting more and more breathless over the week.",
        ("age over 75", "mild leg edema", "obesity", "bibasal crackles", "known hypertension"),
        results={"bnp": "low", "cxr": "congestion"},
        tempts="ruling out heart failure on a low natriuretic peptide above age 75", decoy="copd",
        note="The rule-out threshold fails in the elderly; the film shows congestion and echo shows the reduced ejection fraction."),
    CaseTemplate("pe_hypoxic_clear_film", "pe", 49, "female",
        "I suddenly couldn't breathe properly at work this morning.",
        ("dyspnea", "tachycardia", "hypoxia", "distress", "recent surgery", "clear chest on auscultation"),
        tempts="D-dimer at high probability", decoy=None,
        note="Clear film in a hypoxic distressed patient raises PE probability; Wells is likely, CTPA is the test."),
    CaseTemplate("acs_anginal_equivalent", "acs", 64, "female",
        "I've been breathless on exertion for two days, no pain really.",
        ("exertional dyspnea", "diabetes", "sweating episodes", "normal oxygen saturation"),
        tempts="dismissing the anginal equivalent", decoy="copd",
        note="Dyspnea as the anginal equivalent; the serial troponin is positive."),
    CaseTemplate("ptx_young", "ptx", 22, "male",
        "Sharp pain on the right and I'm struggling to breathe since an hour ago.",
        ("pleuritic pain", "absent breath sounds right", "distress", "hypoxia", "tall thin build"),
        tempts="the full cardiac work-up before a film", decoy="pe",
        note="The film settles it."),
    CaseTemplate("pna_febrile", "pna", 58, "male",
        "Fever, cough and I'm short of breath since three days.",
        ("fever", "productive cough", "localized pleuritic pain", "dullness to percussion", "tachycardia"),
        results={"ddimer": "positive", "wells": "likely"},
        tempts="a positive D-dimer dragging the work-up to CTPA", decoy="pe",
        note="Consolidation on the film explains the picture; the D-dimer is raised by infection."),
    CaseTemplate("copd_exacerbation", "copd", 66, "male",
        "My usual breathing has got a lot worse since my cold.",
        ("known COPD", "wheeze", "prolonged expiration", "smoker", "normal cardiac exam"),
        tempts="over-testing a patient whose history explains the picture", decoy=None,
        note="Normal ECG and troponin, low natriuretic peptide, hyperinflated film without consolidation: the exacerbation is what remains."),
)

WORLD = World(
    situation="dyspnea",
    title="Acute shortness of breath",
    presentation="An adult arrives breathless.",
    tests=TESTS,
    hypotheses=HYPOTHESES,
    cases=CASES,
    route=ROUTE,
    order_rules=ORDER_RULES,
)
