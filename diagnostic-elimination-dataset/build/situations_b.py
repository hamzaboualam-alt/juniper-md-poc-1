from situations_a import L0, G, H, E, ST, R, RULES, GAP

DYSPNEA = {
 "id": "dyspnea", "title": "Acute shortness of breath", "setting": "Emergency department", "population": "Adults",
 "priority": "Among the top ED reasons for visit in NHAMCS fact sheets.", "priority_source": "nhamcs_2011",
 "lead_guidelines": ["nice_cg187", "ash_vte"], "status": "partial",
 "layer0": [
  L0("Complaint", "New or worsening breathlessness.", None),
  L0("History", "Known heart failure, lung disease, VTE risk factors.", None),
  L0("Exam", "Pain on inspiration and one-sided absent breath sounds point to pneumothorax; fever, localized pleuritic pain and dullness point to pneumonia.", "tw_cp_exam"),
  L0("First tests", "ECG, chest radiograph, natriuretic peptide.", None)],
 "gate": [
  G(True, "Respiratory failure or instability", "Resuscitate first; the elimination route assumes a stabilized patient.", None),
  G(False, "Stable", "Work through heart, lung and clot causes in parallel.", None)],
 "gate_note": "Gate wording is a structural convention, not taken from a source.", "gate_note_source": None,
 "hypotheses": [
  H("ahf", "Acute heart failure", "Heart failure", "must_not_miss", "Known heart disease", "partial", None),
  H("pe", "Pulmonary embolism", "PE", "must_not_miss", "Fast heart rate, dyspnea", "sourced", "aafp_cp"),
  H("acs", "Acute coronary syndrome", "ACS", "must_not_miss", "Dyspnea as anginal equivalent", "partial", "aha_cp_top"),
  H("ptx", "Pneumothorax", "Pneumothorax", "must_not_miss", "Pain on inspiration, absent breath sounds", "partial", "tw_cp_exam"),
  H("pna", "Pneumonia", "Pneumonia", "other", "Fever, localized pleuritic pain", "partial", "tw_cp_exam"),
  H("copd", "COPD or asthma exacerbation", "COPD/asthma", "other", "Known lung disease", "stub", None)],
 "steps": [
  ST("History and exam", "First minutes", "Sets which causes are plausible.", {
   "ptx": E("steer", "Dyspnea, pain on inspiration, one-sided absent breath sounds.", "tw_cp_exam"),
   "pna": E("steer", "Fever, localized pleuritic pain, dullness, egophony.", "tw_cp_exam"),
   "pe": E("steer", "Fast heart rate and dyspnea.", "aafp_cp"),
   "acs": E("steer", "Shortness of breath counts as an anginal equivalent.", "aha_cp_top")}),
  ST("12-lead ECG", "Early", "Screens for ischemia.", {
   "acs": E("blind", "Ischemic change escalates; one normal ECG does not rule ACS out.", "iatrox_cp")}),
  ST("Chest radiograph", "Early", "Finds lung causes and changes PE probability.", {
   "ptx": E("rule", "Normal film with distress, pleuritic pain and hypoxia excludes pneumothorax.", "rcem_cxr"),
   "pna": E("conf", "Infiltrate confirms; a normal film makes pneumonia unlikely.", "rcem_cxr"),
   "pe": E("steer", "A normal film in a hypoxic, distressed patient raises PE probability.", "rcem_cxr"),
   "ahf": E("steer", "With echocardiography and judgment, helps in the natriuretic peptide grey zone.", "np_elderly")}),
  ST("Natriuretic peptide", "Single measurement in new suspected heart failure", "Rule-out test for heart failure.", {
   "ahf": E("rule", "BNP below 100 ng/L or NT-proBNP below 300 ng/L rules out heart failure.", "nice_cg187")}),
  ST("PE route", "In parallel if PE is open", "Wells or PERC, then D-dimer or CTPA (see chest pain).", {
   "pe": E("rule", "Low pre-test probability with negative D-dimer, or negative CTPA.", "ash_vte")}),
  ST("Echocardiography", "If heart failure is not ruled out", "Confirms the cardiac abnormality.", {
   "ahf": E("conf", "Transthoracic echo confirms cardiac abnormalities.", "iatrox_ahf")})],
 "rules": {
  "ahf": RULES("NICE CG187 (thresholds match ESC 2021).",
   [R("BNP below 100 ng/L or NT-proBNP below 300 ng/L in new suspected acute heart failure.", "nice_cg187")],
   [R("The rule-out threshold in older patients, obesity or prior heart failure: false negatives of 1 in 10 to 1 in 5.", "np_ml"),
    R("NT-proBNP rule-out above age 75: negative predictive value fell to about 88% in one cohort.", "np_elderly")]),
  "pe": RULES("ASH 2018 and ESC summaries.",
   [R("Low pre-test probability and negative D-dimer.", "ash_vte"), R("Negative CTPA.", "evi_wells")],
   [R("D-dimer when probability is high.", "ash_vte")]),
  "acs": RULES("See chest pain situation.", [R("Low-risk class with non-ischemic ECG and negative serial troponin.", "aha_cp_top")], [R("One normal ECG.", "iatrox_cp")]),
  "ptx": RULES("Educational summary.", [R("Normal chest radiograph with distress, pleuritic pain and hypoxia.", "rcem_cxr")], [R("Exam alone.", "tw_cp_exam")]),
  "pna": RULES("Educational summary.", [R("Normal chest radiograph makes it unlikely.", "rcem_cxr")], [R("Exam alone.", "tw_cp_exam")]),
  "copd": RULES("Not yet researched.", [], [], "No route sourced; GOLD and GINA guidance would be the next sources.")},
 "gaps": [
  GAP("Grey zone", "Between rule-out and rule-in natriuretic peptide thresholds, about half of older patients have heart failure; echo and judgment decide.", "np_elderly"),
  GAP("Unsourced gate", "The stabilization gate and the COPD/asthma branch need sourcing.", None)]
}

LOWER_ABDO = {
 "id": "lower_abdominal_pain", "title": "Acute lower abdominal or pelvic pain", "setting": "Emergency department", "population": "Adults, including women of reproductive age",
 "priority": "Abdominal pain is the leading ED reason for visit in NHAMCS fact sheets.", "priority_source": "nhamcs_2011",
 "lead_guidelines": ["acr_rlq", "acr_pelvic_2023"], "status": "partial",
 "layer0": [
  L0("Complaint", "Pain in the lower abdomen or pelvis; its location narrows the list.", "aafp_pelvic"),
  L0("Pregnancy status", "Urine or serum beta-hCG is the first step in women who could be pregnant.", "hopkins_pelvic"),
  L0("Exam clues", "Migration from the umbilicus to the right lower quadrant suggests appendicitis; left lower quadrant tenderness suggests diverticulitis.", "aafp_pelvic"),
  L0("Patient group", "Adult, child or pregnant; this changes which imaging comes first.", "acr_rlq")],
 "gate": [
  G(True, "Positive pregnancy test with pain", "Ectopic pregnancy must be considered; ultrasound first.", "acr_pelvic_narr"),
  G(False, "Not pregnant", "Choose imaging by suspected source: gynecologic or not.", "acr_pelvic_2023")],
 "gate_note": "Urgent causes to consider first in women of reproductive age include ectopic pregnancy, ruptured ovarian cyst, ovarian torsion, appendicitis and pelvic inflammatory disease.",
 "gate_note_source": "aafp_pelvic",
 "hypotheses": [
  H("ectopic", "Ectopic pregnancy", "Ectopic", "must_not_miss", "Positive hCG, pelvic pain", "sourced", "acr_pelvic_narr"),
  H("appy", "Appendicitis", "Appendicitis", "must_not_miss", "Pain migrating to the right lower quadrant", "sourced", "aafp_pelvic"),
  H("torsion", "Ovarian torsion", "Torsion", "must_not_miss", "One-sided pelvic pain", "partial", "aafp_pelvic"),
  H("divert", "Diverticulitis", "Diverticulitis", "other", "Left lower quadrant tenderness", "partial", "aafp_pelvic"),
  H("gyn", "Ovarian cyst or pelvic inflammatory disease", "Cyst or PID", "other", "Suspected gynecologic source", "partial", "aafp_pelvic"),
  H("stone", "Ureteral stone", "Stone", "other", "Flank pain radiating; see flank pain", "partial", "aafp_pelvic")],
 "steps": [
  ST("History and exam", "First minutes", "Location and migration of pain narrow the list.", {
   "appy": E("steer", "Periumbilical pain migrating to the right lower quadrant.", "aafp_pelvic"),
   "divert": E("steer", "Left lower quadrant tenderness.", "aafp_pelvic"),
   "torsion": E("steer", "Right- or left-sided pelvic pain keeps torsion on the list.", "aafp_pelvic"),
   "stone": E("steer", "Right-sided pelvic pain can also be a stone.", "aafp_pelvic")}),
  ST("Pregnancy test", "Before imaging, in anyone who could be pregnant", "Decides whether pregnancy causes are possible and which imaging is safe.", {
   "ectopic": E("rule", "A negative serum beta-hCG essentially excludes acute ectopic pregnancy.", "acr_pelvic_narr")}),
  ST("Pelvic ultrasound with Doppler", "Suspected gynecologic cause, or pregnant", "Transabdominal plus transvaginal ultrasound is the usual first imaging.", {
   "ectopic": E("conf", "First-line imaging when hCG is positive.", "acr_pelvic_2023"),
   "torsion": E("conf", "Ultrasound with Doppler is the initial study for gynecologic causes.", "acr_pelvic_2023"),
   "gyn": E("conf", "Characterizes cysts and complications of pelvic inflammatory disease.", "hopkins_pelvic"),
   "appy": E("steer", "First choice in children and pregnancy; often inconclusive in pregnancy, then MRI.", "acr_rlq")}),
  ST("Contrast CT", "Nonpregnant adults with a suspected non-gynecologic cause", "Most accurate test for appendicitis and other bowel causes.", {
   "appy": E("rule", "CT is the most accurate study for appendicitis and its alternatives.", "acr_rlq"),
   "divert": E("conf", "CT with IV contrast is best for gastrointestinal causes such as diverticulitis.", "hopkins_pelvic")})],
 "rules": {
  "ectopic": RULES("ACR Appropriateness Criteria.", [R("Negative serum beta-hCG.", "acr_pelvic_narr")], []),
  "appy": RULES("ACR criteria for test choice; Cochrane diagnostic review for accuracy.",
   [R("Negative CT in an adult: at a 43% prevalence the probability of appendicitis falls to about 4% (Cochrane review). A strong reduction, not certainty.", "cochrane_appy")],
   [R("A single inconclusive ultrasound in pregnancy; most are inconclusive, so MRI follows.", "acr_rlq")]),
  "torsion": RULES("Partly sourced.", [], [], "No explicit exclusion rule extracted; ultrasound with Doppler is the first study."),
  "divert": RULES("Partly sourced.", [], [], "No explicit exclusion rule extracted."),
  "gyn": RULES("Partly sourced.", [], [], "No explicit exclusion rule extracted."),
  "stone": RULES("See flank pain situation.", [], [], "Route lives in the flank pain situation.")},
 "gaps": [
  GAP("Upper abdominal pain", "Right upper quadrant and epigastric pain are not covered; ultrasound is the usual first test for right upper quadrant pain.", "hosp_abd_imaging"),
  GAP("Operator dependence", "Ultrasound performance depends on operator training.", "hosp_abd_imaging"),
  GAP("Clinical scores", "Scores such as Alvarado were not sourced in this pass.", None)]
}

UGIB = {
 "id": "ugib", "title": "Upper gastrointestinal bleeding", "setting": "Emergency department and hospital", "population": "Adults with overt bleeding",
 "priority": "GI bleeding causes more than half a million US admissions a year.", "priority_source": "nursing_ugib",
 "lead_guidelines": ["acg_ugib"], "status": "partial",
 "layer0": [
  L0("Complaint", "Vomiting red blood or coffee-ground material, or black stools; bleeding from esophagus, stomach or duodenum.", "nursing_ugib"),
  L0("Vitals and labs", "Inputs for the Glasgow-Blatchford score.", "jhm_ugib")],
 "gate": [
  G(True, "Not very low risk", "Hospital care; endoscopy within 24 hours.", "acg_ugib"),
  G(False, "Very low risk (Glasgow-Blatchford 0 to 1)", "Outpatient follow-up rather than admission, if no other reason to stay.", "acg_ugib")],
 "gate_note": "This situation is mostly risk triage; the cause is found at endoscopy rather than eliminated step by step.",
 "gate_note_source": None,
 "hypotheses": [
  H("ulcer", "Peptic ulcer bleeding", "Ulcer", "must_not_miss", "Most common cause", "partial", "nursing_ugib"),
  H("other_ugi", "Other upper GI source (varices, tears, others)", "Other upper GI", "must_not_miss", "Not sourced", "stub", None),
  H("needs_intervention", "Bleeding that needs hospital intervention", "Needs intervention", "must_not_miss", "Unstable or high score", "sourced", "jhm_ugib")],
 "steps": [
  ST("Risk score", "In the ED", "Glasgow-Blatchford score.", {
   "needs_intervention": E("rule", "Score 0 to 1 identifies very-low-risk patients; the score is about 99% sensitive for need for intervention.", "jhm_ugib")}),
  ST("Endoscopy", "Within 24 hours for hospitalized patients", "Finds and treats the source.", {
   "ulcer": E("conf", "Endoscopic therapy for ulcers with active bleeding or a visible vessel.", "acg_ugib"),
   "other_ugi": E("conf", "Endoscopy identifies the source (non-ulcer routes not sourced).", None)}, "acg_ugib")],
 "rules": {
  "needs_intervention": RULES("ACG 2021, conditional recommendation, very low quality evidence.",
   [R("Glasgow-Blatchford score 0 to 1 with no other reason for admission.", "acg_ugib")],
   [R("The score without considering age, comorbidities and follow-up reliability.", "jhm_ugib")]),
  "ulcer": RULES("Diagnosed at endoscopy.", [], [], "No pre-endoscopy exclusion rule."),
  "other_ugi": RULES("Not yet researched.", [], [], "Variceal bleeding guidance (AASLD/Baveno) not sourced.")},
 "gaps": [GAP("Lower GI bleeding", "Lower GI bleeding has a separate ACG guideline, not included.", None)]
}

LEG = {
 "id": "leg_swelling", "title": "Unilateral leg swelling or pain (suspected DVT)", "setting": "ED or outpatient", "population": "Adults",
 "priority": "High-volume VTE presentation with a GRADE guideline.", "priority_source": None,
 "lead_guidelines": ["ash_vte"], "status": "partial",
 "layer0": [
  L0("Complaint", "One-sided leg swelling or pain.", "ash_slides"),
  L0("History", "Prior DVT or PE, cancer, recent immobilization; whether another diagnosis is as likely.", "ash_slides")],
 "gate": [
  G(True, "Breathlessness or chest pain", "Treat as suspected PE and use that route.", "ash_vte"),
  G(False, "Leg symptoms only", "Estimate pre-test probability, then test.", "ash_vte")],
 "gate_note": "Diagnostic strategy depends on the estimated pre-test probability.", "gate_note_source": "ash_vte",
 "hypotheses": [
  H("dvt", "Deep vein thrombosis", "DVT", "must_not_miss", "Swelling, risk factors", "sourced", "ash_slides"),
  H("alt", "Alternative diagnosis", "Alternative", "other", "Another cause as likely", "stub", "ash_slides")],
 "steps": [
  ST("Pre-test probability (Wells for DVT)", "First", "Low, intermediate or high; DVT prevalence about 10% or less, 25% and 50% or more.", {
   "dvt": E("steer", "Sets which test comes first.", "ash_vte_pmc"),
   "alt": E("steer", "An alternative diagnosis being as likely lowers the score.", "ash_slides")}),
  ST("Highly sensitive D-dimer", "Low pre-test probability", "Rule-out test.", {
   "dvt": E("rule", "Negative D-dimer at low pre-test probability: no further testing.", "ash_vte")}),
  ST("Compression ultrasound", "High probability, or positive D-dimer", "Proximal or whole-leg ultrasound.", {
   "dvt": E("rule", "Positive scan confirms; a negative whole-leg scan or negative serial proximal scans end the work-up.", "mdedge_dvt")})],
 "rules": {
  "dvt": RULES("ASH 2018 GRADE guideline (reviewed 2022).",
   [R("Low pre-test probability and negative highly sensitive D-dimer.", "ash_vte"),
    R("Negative whole-leg ultrasound, negative serial proximal ultrasound, or negative D-dimer after a negative proximal scan: no further testing.", "mdedge_dvt"),
    R("ASH 2018: at intermediate or high probability, proximal or whole-limb ultrasound first, with a one-week repeat after a negative scan in higher-prevalence groups.", "jama_vte")],
   [R("D-dimer as the first test at high probability; imaging is warranted.", "ash_vte"),
    R("A single negative proximal scan when the D-dimer is positive; repeat at one week or scan the whole leg.", "chest_at9_dvt")]),
  "alt": RULES("Not yet researched.", [], [], "Specific alternatives (cellulitis, ruptured Baker cyst) not sourced.")},
 "gaps": [GAP("Score cut-offs", "Exact Wells DVT cut-offs differ between versions; prevalence bands are used instead.", "ash_vte_pmc"),
  GAP("Distal DVT", "The clinical relevance of calf-vein clots found on ultrasound is uncertain.", "jama_vte")]
}
