"""Acute lower abdominal or pelvic pain. Dataset situation lower_abdominal_pain (ACR Appropriateness Criteria)."""
from __future__ import annotations

from . import CaseTemplate, Clause, Hypothesis, OrderRule, Shortcut, Test, World

TESTS = {
    "history_exam": Test("history_exam", "History and exam", "history_exam", {"done": "Findings recorded"}, "desk", "lower_abdominal_pain.s1"),
    "hcg": Test("hcg", "Serum beta-hCG", "hcg", {
        "negative": "Negative",
        "positive": "Positive",
    }, "lab", "lower_abdominal_pain.s2"),
    "pelvic_us": Test("pelvic_us", "Pelvic ultrasound with Doppler", "pelvic_us", {
        "normal": "Normal ovaries with flow, no free fluid, intrauterine findings normal",
        "ectopic": "Empty uterus with an adnexal mass and free fluid",
        "no_flow": "Enlarged ovary with absent Doppler flow",
        "cyst": "Simple ovarian cyst, normal flow",
        "inconclusive": "Appendix not visualised; no gynecologic abnormality",
        "iup": "Intrauterine pregnancy, normal adnexa",
    }, "imaging", "lower_abdominal_pain.s3"),
    "ct_abd": Test("ct_abd", "CT abdomen and pelvis with contrast", "ct_abd", {
        "negative": "No appendicitis, no bowel pathology, no stone",
        "appendicitis": "Dilated appendix with periappendiceal stranding",
        "diverticulitis": "Sigmoid diverticulitis with pericolic stranding",
        "stone": "Ureteral calculus with hydronephrosis",
    }, "imaging", "lower_abdominal_pain.s4"),
    "mri_pelvis": Test("mri_pelvis", "MRI pelvis", "mri_pelvis", {
        "negative": "Normal appendix",
        "appendicitis": "Inflamed appendix",
    }, "imaging", "lower_abdominal_pain.s3"),
}

NEG = {"hcg": "negative", "pelvic_us": "normal", "ct_abd": "negative", "mri_pelvis": "negative"}

HYPOTHESES = {
    "ectopic": Hypothesis("ectopic", "Ectopic pregnancy", "must_not_miss", NEG | {"hcg": "positive", "pelvic_us": "ectopic"},
        eliminate_when=(
            Clause({"hcg": "negative"}, "A negative serum beta-hCG essentially excludes acute ectopic pregnancy.", "acr_pelvic_2023"),
            Clause({"pelvic_us": "iup"}, "An intrauterine pregnancy on ultrasound.", "acr_pelvic_2023", inferred=True),
        ),
        confirmed_by={"pelvic_us": "ectopic"}),
    "appy": Hypothesis("appy", "Appendicitis", "must_not_miss", NEG | {"ct_abd": "appendicitis", "mri_pelvis": "appendicitis", "pelvic_us": "inconclusive"},
        eliminate_when=(
            Clause({"ct_abd": ("negative", "diverticulitis", "stone")}, "CT without appendicitis in an adult: probability falls to about 4% (Cochrane). A strong reduction, not certainty.", "cochrane_appy"),
            Clause({"mri_pelvis": "negative"}, "Normal appendix on MRI when CT is not appropriate (pregnancy).", "acr_rlq", inferred=True),
        ),
        do_not_rely=(Shortcut({"pelvic_us": "inconclusive"}, "A single inconclusive ultrasound in pregnancy; MRI follows.", "acr_rlq"),),
        confirmed_by={"ct_abd": "appendicitis", "mri_pelvis": "appendicitis"}),
    "torsion": Hypothesis("torsion", "Ovarian torsion", "must_not_miss", NEG | {"pelvic_us": "no_flow"},
        eliminate_when=(Clause({"pelvic_us": ("normal", "cyst", "iup", "inconclusive", "ectopic")}, "Ovaries with preserved Doppler flow.", "acr_pelvic_2023", inferred=True),),
        do_not_rely=(Shortcut({"ct_abd": "negative"}, "A negative CT: CT is not the study for the adnexa.", "acr_pelvic_2023"),),
        confirmed_by={"pelvic_us": "no_flow"},
        no_rule_note="No explicit exclusion rule extracted; ultrasound with Doppler is the first study."),
    "divert": Hypothesis("divert", "Diverticulitis", "other", NEG | {"ct_abd": "diverticulitis"},
        eliminate_when=(Clause({"ct_abd": ("negative", "appendicitis", "stone")}, "No colonic inflammation on contrast CT.", "acr_rlq", inferred=True),),
        confirmed_by={"ct_abd": "diverticulitis"}),
    "gyn": Hypothesis("gyn", "Ovarian cyst or pelvic inflammatory disease", "other", NEG | {"pelvic_us": "cyst"},
        eliminate_when=(Clause({"pelvic_us": ("normal", "inconclusive", "iup", "ectopic", "no_flow")}, "No cyst or tubo-ovarian complex on ultrasound.", "acr_pelvic_2023", inferred=True),),
        confirmed_by={"pelvic_us": "cyst"}),
    "stone": Hypothesis("stone", "Ureteral stone", "other", NEG | {"ct_abd": "stone"},
        eliminate_when=(Clause({"ct_abd": ("negative", "appendicitis", "diverticulitis")}, "No calculus on CT.", "acr_flank", inferred=True),),
        confirmed_by={"ct_abd": "stone"}),
}

ROUTE = ("history_exam", "hcg", "pelvic_us", "ct_abd", "mri_pelvis")

ORDER_RULES = (
    OrderRule("ct_abd", "hcg", ("negative",), "Pregnancy status decides which imaging is safe: ultrasound first when hCG is positive.", "acr_pelvic_2023", findings=("female of reproductive age",)),
    OrderRule("pelvic_us", "hcg", None, "Pregnancy test before imaging in anyone who could be pregnant.", "acr_pelvic_2023", findings=("female of reproductive age",)),
)

CASES = (
    CaseTemplate("ectopic", "ectopic", 27, "female",
        "Pain low down on the right since last night, and some spotting.",
        ("female of reproductive age", "right pelvic pain", "vaginal spotting", "missed period", "mild tachycardia"),
        tempts="CT before the pregnancy test", decoy="appy",
        note="Positive hCG and pain: ultrasound first, which shows the ectopic."),
    CaseTemplate("appy_classic", "appy", 31, "male",
        "The pain started around my belly button and has moved down to the right.",
        ("pain migrating to the right lower quadrant", "fever", "rebound tenderness", "nausea"),
        tempts="imaging before the examination", decoy=None,
        note="CT confirms."),
    CaseTemplate("appy_female", "appy", 24, "female",
        "Pain on the right side low down, getting worse since yesterday.",
        ("female of reproductive age", "right lower quadrant tenderness", "nausea", "low-grade fever"),
        tempts="stopping at an ultrasound that did not see the appendix", decoy="torsion",
        note="hCG negative, ultrasound shows normal adnexa but cannot see the appendix; CT finds it."),
    CaseTemplate("appy_pregnant", "appy", 29, "female",
        "I'm 14 weeks pregnant and I've got a sharp pain on the right.",
        ("female of reproductive age", "known pregnancy", "right lower quadrant tenderness", "nausea"),
        results={"hcg": "positive", "pelvic_us": "iup"},
        tempts="relying on an inconclusive ultrasound, or ordering CT in pregnancy", decoy="ectopic",
        note="Ultrasound shows the intrauterine pregnancy and misses the appendix; MRI is the next study."),
    CaseTemplate("torsion_right", "torsion", 22, "female",
        "Sudden severe pain on the right, I was sick twice.",
        ("female of reproductive age", "sudden onset right pelvic pain", "vomiting", "adnexal tenderness"),
        results={"ct_abd": "negative"},
        tempts="calling it appendicitis and ruling out on a negative CT", decoy="appy",
        note="CT is negative for appendicitis but cannot clear the adnexa; Doppler ultrasound shows absent flow."),
    CaseTemplate("divert_left", "divert", 63, "female",
        "Pain on the lower left for two days and I've gone off food.",
        ("left lower quadrant tenderness", "low-grade fever", "constipation", "postmenopausal"),
        tempts="pelvic imaging first", decoy="gyn",
        note="Postmenopausal, left-sided: CT shows diverticulitis."),
    CaseTemplate("gyn_cyst", "gyn", 34, "female",
        "Dull ache low on the left for a week, worse with my period.",
        ("female of reproductive age", "left pelvic ache", "cyclical pain", "normal vital signs"),
        tempts="CT for a gynecologic picture", decoy="divert",
        note="hCG negative; ultrasound shows a simple cyst with normal flow."),
    CaseTemplate("stone_flank", "stone", 45, "male",
        "Terrible pain from my side down to my groin, in waves.",
        ("colicky flank pain radiating to the groin", "hematuria", "restlessness"),
        tempts="an appendicitis work-up for a stone picture", decoy="appy",
        note="CT shows the calculus."),
)

WORLD = World(
    situation="lower_abdominal_pain",
    title="Acute lower abdominal or pelvic pain",
    presentation="An adult arrives with pain low in the abdomen or pelvis.",
    tests=TESTS,
    hypotheses=HYPOTHESES,
    cases=CASES,
    route=ROUTE,
    order_rules=ORDER_RULES,
)
