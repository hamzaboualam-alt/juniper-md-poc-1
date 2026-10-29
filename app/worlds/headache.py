"""Acute nontraumatic headache. Dataset situation headache (ACEP 2019, SNNOOP10, Ottawa SAH rule)."""
from __future__ import annotations

from . import CaseTemplate, Clause, Hypothesis, OrderRule, Shortcut, Test, World

TESTS = {
    "history_exam": Test("history_exam", "Red-flag history (SNNOOP10)", "history_exam", {"done": "Findings recorded"}, "desk", "headache.s1"),
    "neuro_exam": Test("neuro_exam", "Neurologic exam", "neuro_exam", {
        "normal": "Alert, no focal deficit, no papilledema",
        "deficit": "Focal deficit or decreased consciousness",
        "papilledema": "Papilledema, otherwise intact",
    }, "bedside", "headache.s2"),
    "ottawa": Test("ottawa", "Ottawa SAH rule", "score", {
        "negative": "None of the six features: rule negative",
        "positive": "At least one feature present: investigate",
    }, "desk", "headache.s3", requires=("history_exam", "neuro_exam")),
    "ct_head": Test("ct_head", "Noncontrast head CT", "ct_head", {
        "normal": "No hemorrhage, no mass",
        "sah": "Subarachnoid blood",
        "mass": "Space-occupying lesion with edema",
    }, "imaging", "headache.s4"),
    "lp": Test("lp", "Lumbar puncture", "lp", {
        "normal": "Clear CSF, normal cell count and protein, no xanthochromia",
        "xanthochromia": "Xanthochromia and red cells in all tubes",
        "bacterial": "Turbid CSF, neutrophils, low glucose, organisms on Gram stain",
    }, "bedside", "headache.s5"),
    "cta_head": Test("cta_head", "CT angiography of the head", "cta_head_neck", {
        "negative": "No aneurysm, no vascular lesion",
        "aneurysm": "Saccular aneurysm",
    }, "imaging", "headache.s5"),
}

NEG = {"neuro_exam": "normal", "ottawa": "negative", "ct_head": "normal", "lp": "normal", "cta_head": "negative"}

HYPOTHESES = {
    "sah": Hypothesis("sah", "Subarachnoid hemorrhage", "must_not_miss", NEG | {"ottawa": "positive", "ct_head": "sah", "lp": "xanthochromia", "cta_head": "aneurysm"},
        eliminate_when=(
            Clause({"ottawa": "negative", "neuro_exam": "normal"}, "Ottawa SAH rule negative in an alert patient with a normal neuro exam and peak within 1 hour.", "acep_headache", findings=("peak within 1 hour",)),
            Clause({"ct_head": "normal", "neuro_exam": "normal"}, "Normal noncontrast CT within 6 hours of onset with a normal neuro exam.", "acep_headache", findings=("within 6 hours of onset",)),
            Clause({"ct_head": "normal", "lp": ("normal", "bacterial")}, "CSF without xanthochromia after a negative CT in a patient still at risk.", "acep_headache"),
            Clause({"ct_head": "normal", "cta_head": "negative"}, "Negative CTA after a negative CT in a patient still at risk.", "acep_headache"),
        ),
        do_not_rely=(
            Shortcut({"ottawa": "negative"}, "The Ottawa rule outside its population: abnormal neuro exam or a slower peak.", "acep_headache", findings=("peak over 1 hour",)),
            Shortcut({"ct_head": "normal"}, "A normal CT alone when more than 6 hours have passed since onset.", "acep_headache", findings=("over 6 hours since onset",)),
            Shortcut({"history_exam": "done"}, "A single sign or symptom.", "acep_headache"),
        ),
        confirmed_by={"ct_head": "sah", "lp": "xanthochromia"}),
    "men": Hypothesis("men", "Bacterial meningitis", "must_not_miss", NEG | {"lp": "bacterial"},
        eliminate_when=(
            Clause({"lp": ("normal", "xanthochromia")}, "Normal CSF examination.", "acep_headache", inferred=True),
            Clause({}, "No fever, no meningism and no systemic illness: meningitis is not in the picture.", "snnoop10", findings=("no fever", "no neck stiffness"), inferred=True),
        ),
        do_not_rely=(Shortcut({"ct_head": "normal"}, "A normal head CT as proof; CSF decides.", "acep_headache"),),
        confirmed_by={"lp": "bacterial"},
        no_rule_note="No formal exclusion rule sourced; diagnosis depends on CSF examination."),
    "sec": Hypothesis("sec", "Other secondary headache (mass, raised pressure, arterial)", "must_not_miss", NEG | {"neuro_exam": "papilledema", "ct_head": "mass"},
        eliminate_when=(
            Clause({"neuro_exam": "normal"}, "No SNNOOP10 red flag and a normal neurologic exam.", "snnoop10", findings=("no red flags",), inferred=True),
            Clause({"ct_head": "normal", "neuro_exam": "normal"}, "Normal imaging and a normal exam when a red flag prompted the scan.", "snnoop10", inferred=True),
        ),
        confirmed_by={"ct_head": "mass"},
        no_rule_note="No single elimination rule; each secondary cause needs its own route."),
    "prim": Hypothesis("prim", "Primary headache (migraine, tension-type)", "other", NEG,
        remainder=True, no_rule_note="Not eliminated; it is what remains when red flags are absent or answered."),
}

ROUTE = ("history_exam", "neuro_exam", "ottawa", "ct_head", "lp", "cta_head")

ORDER_RULES = (
    OrderRule("lp", "ct_head", None, "CT before lumbar puncture when there is a deficit, decreased consciousness or papilledema.", "acep_headache", findings=("focal deficit",)),
)

CASES = (
    CaseTemplate("sah_thunderclap_early", "sah", 46, "female",
        "The worst headache of my life hit me like a hammer two hours ago.",
        ("thunderclap onset", "peak within 1 hour", "within 6 hours of onset", "neck stiffness", "no fever"),
        results={"neuro_exam": "normal"},
        tempts="skipping imaging after a reassuring exam", decoy="prim",
        note="Ottawa positive; CT within 6 hours shows the blood."),
    CaseTemplate("sah_late_normal_ct", "sah", 52, "male",
        "A sudden awful headache yesterday evening that hasn't gone.",
        ("thunderclap onset", "peak within 1 hour", "over 6 hours since onset", "no fever", "no neck stiffness"),
        results={"ct_head": "normal", "lp": "xanthochromia", "cta_head": "aneurysm"},
        tempts="ruling out SAH on a normal CT more than 6 hours after onset", decoy="prim",
        note="CT is normal because it is late; the 6-hour rule does not apply. LP shows xanthochromia."),
    CaseTemplate("migraine_no_flags", "prim", 29, "female",
        "Another of my throbbing headaches, with the usual nausea and light sensitivity.",
        ("gradual onset", "peak over 1 hour", "no red flags", "known migraine", "no fever", "no neck stiffness"),
        tempts="imaging a patient with no red flags", decoy=None,
        note="No flags, normal exam: primary headache is what remains; CT adds nothing."),
    CaseTemplate("meningitis_febrile", "men", 20, "male",
        "Terrible headache, fever and my neck is stiff.",
        ("fever", "neck stiffness", "photophobia", "gradual onset", "peak over 1 hour"),
        results={"neuro_exam": "normal"},
        tempts="delaying the lumbar puncture for a CT", decoy="sah",
        note="Fever and meningism: CSF decides; a normal CT is not required before LP with a normal exam."),
    CaseTemplate("mass_progressive", "sec", 58, "male",
        "Headaches every morning for a month, worse when I cough, and I'm clumsy on the left.",
        ("progressive headache", "positional", "triggered by cough", "focal deficit", "onset after 65", "peak over 1 hour"),
        results={"neuro_exam": "deficit", "ct_head": "mass"},
        tempts="applying the SAH rule outside its population", decoy="prim",
        note="A deficit means the ACEP tools do not apply; CT shows the mass."),
    CaseTemplate("thunderclap_cleared", "prim", 38, "female",
        "A sudden severe headache during exercise this morning, easing now.",
        ("thunderclap onset", "peak within 1 hour", "within 6 hours of onset", "onset with exertion", "no fever", "no neck stiffness"),
        results={"neuro_exam": "normal", "ct_head": "normal"},
        tempts="going to LP or CTA after a CT that already rules SAH out", decoy="sah",
        note="Ottawa positive so imaging is right; normal CT within 6 hours with a normal exam rules SAH out, and nothing more is needed."),
)

WORLD = World(
    situation="headache",
    title="Acute nontraumatic headache",
    presentation="An adult arrives with a new or different headache.",
    tests=TESTS,
    hypotheses=HYPOTHESES,
    cases=CASES,
    route=ROUTE,
    order_rules=ORDER_RULES,
)
