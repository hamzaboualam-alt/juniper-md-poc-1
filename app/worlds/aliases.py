"""How the grader reads what the doctor writes. The doctor never sees the
board, so hypotheses arrive as free text ("PE", "a clot in the lung",
"pulmonary embolism"); each world maps the phrasings it recognises to its
hypothesis ids. Matching is longest-phrase-wins, so "hemorrhagic stroke" beats
"stroke" and lands on the bleed, not the infarct.
"""
from __future__ import annotations

import re

ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "chest_pain": {
        "acs": ("acs", "acute coronary", "coronary syndrome", "myocardial infarction", "heart attack", "mi", "nstemi", "stemi", "unstable angina", "angina", "cardiac ischemia", "cardiac ischaemia", "ischemic heart", "coronary"),
        "pe": ("pe", "pulmonary embol", "embolism", "embolus", "clot in the lung", "lung clot", "vte", "thromboembol"),
        "ad": ("ad", "aortic dissection", "dissection", "acute aortic", "aortic syndrome", "aneurysm rupture"),
        "ptx": ("ptx", "pneumothorax", "collapsed lung"),
        "pna": ("pna", "pneumonia", "chest infection", "lung infection"),
        "pc": ("pc", "pericard", "myocarditis", "tamponade"),
        "nc": ("nc", "noncardiac", "non cardiac", "musculoskeletal", "chest wall", "costochondritis", "reflux", "gerd", "esophag", "oesophag", "anxiety", "panic", "benign chest pain"),
    },
    "dyspnea": {
        "ahf": ("ahf", "heart failure", "chf", "pulmonary edema", "pulmonary oedema", "cardiogenic", "decompensated", "cardiac failure", "fluid overload"),
        "pe": ("pe", "pulmonary embol", "embolism", "embolus", "clot in the lung", "lung clot", "vte", "thromboembol"),
        "acs": ("acs", "acute coronary", "coronary syndrome", "myocardial infarction", "heart attack", "mi", "nstemi", "stemi", "unstable angina", "angina", "cardiac ischemia", "cardiac ischaemia", "coronary"),
        "ptx": ("ptx", "pneumothorax", "collapsed lung"),
        "pna": ("pna", "pneumonia", "chest infection", "lung infection"),
        "copd": ("copd", "asthma", "bronchospasm", "exacerbation", "obstructive", "airway disease", "bronchitis", "emphysema"),
    },
    "lower_abdominal_pain": {
        "ectopic": ("ectopic", "tubal pregnancy", "extrauterine"),
        "appy": ("appy", "appendic"),
        "torsion": ("torsion", "adnexal torsion", "twisted ovary"),
        "divert": ("divert", "diverticul"),
        "gyn": ("gyn", "ovarian cyst", "cyst", "pelvic inflammatory", "pid", "tubo ovarian", "gynecolog", "gynaecolog", "salping", "endometriosis", "mittelschmerz"),
        "stone": ("stone", "renal colic", "ureteral", "ureteric", "nephrolith", "urolith", "kidney stone", "calculus", "colic"),
    },
    "headache": {
        "sah": ("sah", "subarachnoid", "aneurysm", "aneurysmal", "hemorrhage", "haemorrhage", "bleed", "intracranial bleed"),
        "men": ("men", "mening", "encephalitis", "cns infection", "central nervous system infection"),
        "sec": ("sec", "secondary headache", "mass", "tumor", "tumour", "raised intracranial", "intracranial pressure", "idiopathic intracranial", "venous sinus thrombosis", "cvst", "arterial dissection", "cervical artery", "temporal arteritis", "giant cell", "hypertensive emergency", "space occupying", "lesion", "hydrocephalus"),
        "prim": ("prim", "primary headache", "migraine", "tension", "cluster", "medication overuse"),
    },
    "focal_deficit": {
        "ais": ("ais", "ischemic stroke", "ischaemic stroke", "stroke", "large vessel occlusion", "lvo", "cerebral infarct", "infarction", "tia", "transient ischemic", "transient ischaemic", "cva", "cerebrovascular"),
        "ich": ("ich", "intracranial hemorrhage", "intracranial haemorrhage", "intracerebral", "hemorrhagic stroke", "haemorrhagic stroke", "hemorrhage", "haemorrhage", "bleed", "subdural", "subarachnoid"),
        "hypo": ("hypo", "hypoglyc", "hyperglyc", "glucose", "blood sugar", "metabolic", "hypoglycemia", "hypoglycaemia"),
        "mimic": ("mimic", "seizure", "todd", "postictal", "post ictal", "migraine", "hemiplegic migraine", "conversion", "functional", "bell", "epilep"),
    },
}


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


def resolve(situation: str, text: str) -> str | None:
    """The hypothesis id the doctor's wording points at, or None when no
    phrasing this world recognises appears in it."""
    t = _norm(text)
    if not t:
        return None
    tokens = set(t.split())
    best: tuple[int, str] | None = None
    for hyp, phrases in ALIASES.get(situation, {}).items():
        for p in phrases:
            n = _norm(p)
            hit = (n in t) if len(n) >= 5 else (n in tokens)
            if hit and (best is None or len(n) > best[0]):
                best = (len(n), hyp)
    return best[1] if best else None
